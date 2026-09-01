--[[
    dt-ai-assistant.lua -- darktable AI Edit Assistant, Lua front-end.

    This file is part of collodion.

    collodion is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    collodion is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with collodion.  If not, see <http://www.gnu.org/licenses/>.

    ----------------------------------------------------------------------

    OVERVIEW

    Registers a sidebar ("lib") module in darktable's darkroom and lighttable
    views that lets the user chat with an LLM about the current image, run a
    histogram/EXIF based "Optimize" pass, run a vision-based "Analyze image"
    pass, and apply a returned .dtstyle recommendation. All the actual LLM
    work happens in a local Python helper process (dt-ai-helper); this file
    only ever talks to that helper over http://127.0.0.1:<port> using curl
    invoked through darktable.control.execute(), and never blocks the GTK
    main loop for longer than a single short curl round-trip.

    See darktableaiassistantplan.md for the full design. Sections referenced
    below (e.g. "§5.1") refer to that document.

    RUNTIME FILE / HELPER DISCOVERY (coordination with the Python helper,
    owned by a different worker -- see documentation/agent-insights/
    003-runtime-file-location.md for the authoritative, cross-checked
    contract):

      Linux:   $XDG_CACHE_HOME/dt-ai-helper/runtime.json (default ~/.cache/...)
      macOS:   ~/Library/Caches/dt-ai-helper/runtime.json
      Windows: %LOCALAPPDATA%\dt-ai-helper\runtime.json

      Contents: {"port": <int>, "token": "<string>", "pid": <int>}, mode 600.

    This file is written by the helper itself on startup (bind-port-0, so the
    port is only known once the process is up), so we must poll for it after
    launching the helper rather than assuming a fixed port.

    darktable Lua API target: 9.x (darktable 4.6+). Every call to an API that
    might not exist on older/newer darktable is wrapped in pcall so a single
    missing feature degrades gracefully instead of breaking the whole panel.
]]

local dt = require("darktable")

-- Best-effort version check; never fatal (pcall) since check_version() itself
-- may raise on very old darktable, and we would rather run degraded than not
-- load at all. darktable.configuration.check_version is documented to raise
-- an error on a mismatched *released* version and just warn on a dev build.
pcall(function()
  dt.configuration.check_version("dt-ai-assistant", { 9, 0, 0 })
end)

-- ===========================================================================
-- SECTION 0: small pure-Lua JSON encoder/decoder
--
-- darktable's bundled Lua has no JSON library and we do not want to vendor a
-- third-party dependency file (keeps this a single-file script, and avoids
-- any licensing ambiguity -- this implementation is original work licensed
-- under the same GPL-3.0-or-later as the rest of collodion).
--
-- Deliberately minimal: it supports everything the helper API contract
-- (plan §5.2) needs -- objects, arrays, strings, numbers, booleans, and
-- null -- and nothing else (no comments, no trailing commas). `null` decodes
-- to a private sentinel (json.null) rather than Lua nil, since assigning nil
-- to a table key removes it; callers that care about the distinction between
-- "absent" and "explicit null" can check for the sentinel, everyone else can
-- just treat a missing/sentinel field the same way.
-- ===========================================================================

local json = {}
json.null = setmetatable({}, { __tostring = function() return "null" end })

local function json_escape(s)
  local out = s:gsub('[%c"\\]', function(c)
    if c == '"' then return '\\"'
    elseif c == '\\' then return '\\\\'
    elseif c == '\n' then return '\\n'
    elseif c == '\r' then return '\\r'
    elseif c == '\t' then return '\\t'
    else return string.format('\\u%04x', string.byte(c))
    end
  end)
  return out
end

local function is_array(t)
  local n = 0
  for _ in pairs(t) do n = n + 1 end
  if n == 0 then return true end -- empty table encodes as [] (see json.object() below for {})
  for i = 1, n do
    if t[i] == nil then return false end
  end
  return true
end

-- Wrap a table so the encoder always treats it as a JSON object, even if
-- empty or if it happens to have only integer keys. Use this for things like
-- an always-object image_context that might legitimately be empty.
function json.object(t)
  t = t or {}
  return setmetatable(t, { __json_object = true })
end

local encode_value -- fwd decl

local function encode_table(t)
  local mt = getmetatable(t)
  local force_object = mt and mt.__json_object
  if not force_object and is_array(t) then
    local parts = {}
    for i = 1, #t do
      parts[i] = encode_value(t[i])
    end
    return "[" .. table.concat(parts, ",") .. "]"
  else
    local parts = {}
    for k, v in pairs(t) do
      if type(k) == "string" then
        parts[#parts + 1] = '"' .. json_escape(k) .. '":' .. encode_value(v)
      end
    end
    return "{" .. table.concat(parts, ",") .. "}"
  end
end

encode_value = function(v)
  local tv = type(v)
  if v == nil or v == json.null then
    return "null"
  elseif tv == "boolean" then
    return v and "true" or "false"
  elseif tv == "number" then
    if v ~= v or v == math.huge or v == -math.huge then return "null" end
    -- Emit integers without a trailing ".0" for readability/compactness.
    if math.floor(v) == v and math.abs(v) < 1e15 then
      return string.format("%d", v)
    end
    return tostring(v)
  elseif tv == "string" then
    return '"' .. json_escape(v) .. '"'
  elseif tv == "table" then
    return encode_table(v)
  else
    error("json.encode: cannot encode value of type " .. tv)
  end
end

function json.encode(v)
  return encode_value(v)
end

-- Minimal recursive-descent decoder.
local function json_decode_impl(s, i)
  local function skip_ws()
    while i <= #s do
      local c = s:sub(i, i)
      if c == " " or c == "\t" or c == "\n" or c == "\r" then
        i = i + 1
      else
        break
      end
    end
  end

  local parse_value -- fwd decl

  local function parse_string()
    i = i + 1 -- opening quote
    local buf = {}
    while true do
      local c = s:sub(i, i)
      if c == "" then error("json.decode: unterminated string") end
      if c == '"' then
        i = i + 1
        break
      elseif c == "\\" then
        local nc = s:sub(i + 1, i + 1)
        if nc == "n" then buf[#buf + 1] = "\n"
        elseif nc == "t" then buf[#buf + 1] = "\t"
        elseif nc == "r" then buf[#buf + 1] = "\r"
        elseif nc == "b" then buf[#buf + 1] = "\b"
        elseif nc == "f" then buf[#buf + 1] = "\f"
        elseif nc == "u" then
          local hex = s:sub(i + 2, i + 5)
          local cp = tonumber(hex, 16) or 63
          -- Only handle the common BMP/ASCII case; encode as UTF-8.
          if cp < 0x80 then
            buf[#buf + 1] = string.char(cp)
          elseif cp < 0x800 then
            buf[#buf + 1] = string.char(0xC0 + math.floor(cp / 0x40), 0x80 + (cp % 0x40))
          else
            buf[#buf + 1] = string.char(
              0xE0 + math.floor(cp / 0x1000),
              0x80 + (math.floor(cp / 0x40) % 0x40),
              0x80 + (cp % 0x40)
            )
          end
          i = i + 4
        else
          buf[#buf + 1] = nc
        end
        i = i + 2
      else
        buf[#buf + 1] = c
        i = i + 1
      end
    end
    return table.concat(buf)
  end

  local function parse_number()
    local start = i
    while i <= #s and s:sub(i, i):match("[%d%+%-%.eE]") do
      i = i + 1
    end
    return tonumber(s:sub(start, i - 1))
  end

  local function parse_object()
    i = i + 1 -- '{'
    local obj = json.object({})
    skip_ws()
    if s:sub(i, i) == "}" then i = i + 1; return obj end
    while true do
      skip_ws()
      if s:sub(i, i) ~= '"' then error("json.decode: expected string key at " .. i) end
      local key = parse_string()
      skip_ws()
      if s:sub(i, i) ~= ":" then error("json.decode: expected ':' at " .. i) end
      i = i + 1
      skip_ws()
      local val = parse_value()
      obj[key] = val
      skip_ws()
      local c = s:sub(i, i)
      if c == "," then
        i = i + 1
      elseif c == "}" then
        i = i + 1
        break
      else
        error("json.decode: expected ',' or '}' at " .. i)
      end
    end
    return obj
  end

  local function parse_array()
    i = i + 1 -- '['
    local arr = {}
    skip_ws()
    if s:sub(i, i) == "]" then i = i + 1; return arr end
    while true do
      skip_ws()
      arr[#arr + 1] = parse_value()
      skip_ws()
      local c = s:sub(i, i)
      if c == "," then
        i = i + 1
      elseif c == "]" then
        i = i + 1
        break
      else
        error("json.decode: expected ',' or ']' at " .. i)
      end
    end
    return arr
  end

  parse_value = function()
    skip_ws()
    local c = s:sub(i, i)
    if c == '"' then
      return parse_string()
    elseif c == "{" then
      return parse_object()
    elseif c == "[" then
      return parse_array()
    elseif c == "t" and s:sub(i, i + 3) == "true" then
      i = i + 4; return true
    elseif c == "f" and s:sub(i, i + 4) == "false" then
      i = i + 5; return false
    elseif c == "n" and s:sub(i, i + 3) == "null" then
      i = i + 4; return json.null
    elseif c:match("[%d%-]") then
      return parse_number()
    else
      error("json.decode: unexpected character " .. tostring(c) .. " at " .. i)
    end
  end

  skip_ws()
  local v = parse_value()
  return v
end

-- Returns nil, err on failure instead of raising, since decode is always
-- called on network/subprocess output that may be empty/garbled.
function json.decode(s)
  if s == nil or s == "" then return nil, "empty input" end
  local ok, result = pcall(json_decode_impl, s, 1)
  if not ok then return nil, result end
  return result
end

-- ===========================================================================
-- SECTION 1: small OS/file utilities
-- ===========================================================================

local running_os = dt.configuration.running_os -- "linux" | "macos" | "windows"
local is_windows = (running_os == "windows")

local function read_file(path)
  local f = io.open(path, "rb")
  if not f then return nil end
  local content = f:read("*a")
  f:close()
  return content
end

local function write_file(path, content)
  local f = io.open(path, "wb")
  if not f then return false end
  f:write(content)
  f:close()
  return true
end

local tmp_seq = 0
local function tmp_file(suffix)
  tmp_seq = tmp_seq + 1
  local dir = dt.configuration.tmp_dir or "."
  return dir .. "/dt_ai_assistant_" .. tostring(os.time()) .. "_" .. tostring(tmp_seq) .. "_" .. suffix
end

-- Quote a path/argument for embedding in a shell command line. We only ever
-- feed this our own generated temp paths and user-configured executable
-- paths, never arbitrary untrusted strings, so a simple double-quote wrap is
-- sufficient for both POSIX sh and Windows cmd.exe.
local function shq(str)
  return '"' .. tostring(str) .. '"'
end

-- Run a shell command via darktable.control.execute (documented as "run a
-- command in a shell while not blocking darktable" -- i.e. it yields to
-- darktable's scheduler instead of freezing the GTK main loop, but the
-- calling Lua coroutine does wait for the command to finish). Used for
-- short, bounded commands only (curl with --max-time, stat, etc). Long-lived
-- processes (the helper itself) must background/detach themselves so this
-- call returns immediately -- see launch_helper() below.
local function run_shell(cmd)
  return dt.control.execute(cmd)
end

-- ===========================================================================
-- SECTION 2: preferences (darktable.preferences.register)
-- Shown in darktable's "lua options" preference tab.
-- ===========================================================================

local PREF_SCRIPT = "dt-ai-assistant"
local NUM_PRESETS = 5

local default_python = is_windows and "python" or "python3"

dt.preferences.register(
  PREF_SCRIPT, "helper_command_override", "string",
  "AI assistant: helper launch command override",
  "Advanced: full command line used to launch the dt-ai-helper process. " ..
  "Leave empty to use '<python path> -m dt_ai_helper.main'.",
  ""
)

dt.preferences.register(
  PREF_SCRIPT, "python_path", "string",
  "AI assistant: python interpreter",
  "Python interpreter used to launch the helper when no launch command " ..
  "override is set (must have dt-ai-helper installed, e.g. via " ..
  "'pip install -e helper/.').",
  default_python
)

dt.preferences.register(
  PREF_SCRIPT, "preview_max_edge", "integer",
  "AI assistant: preview max edge (px)",
  "Longest edge, in pixels, of the JPEG preview exported for Optimize " ..
  "and Analyze image requests.",
  1024, 256, 4096
)

dt.preferences.register(
  PREF_SCRIPT, "request_timeout", "integer",
  "AI assistant: request timeout (s)",
  "Maximum seconds to wait for a single curl call to the local helper, " ..
  "and the overall budget used to give up polling a job as timed out.",
  60, 5, 600
)

dt.preferences.register(
  PREF_SCRIPT, "allow_cloud_upload", "bool",
  "AI assistant: allow image upload to cloud endpoints",
  "When off, Analyze image (vision) refuses to send the preview image to " ..
  "any preset whose base URL is not on localhost/127.0.0.1. Local " ..
  "endpoints (e.g. Ollama) are always allowed.",
  false
)

dt.preferences.register(
  PREF_SCRIPT, "active_preset_index", "integer",
  "AI assistant: active model preset (internal)",
  "Index of the currently selected model preset. Normally set from the " ..
  "panel's combobox, not edited here.",
  1, 1, NUM_PRESETS
)

for i = 1, NUM_PRESETS do
  dt.preferences.register(
    PREF_SCRIPT, "preset" .. i .. "_name", "string",
    "AI assistant: preset " .. i .. " name",
    "Display name for model preset slot " .. i .. ". Leave empty to disable this slot.",
    ""
  )
  dt.preferences.register(
    PREF_SCRIPT, "preset" .. i .. "_base_url", "string",
    "AI assistant: preset " .. i .. " base URL",
    "OpenAI-compatible base URL, e.g. https://api.openai.com/v1, " ..
    "http://127.0.0.1:11434/v1 (Ollama), etc.",
    ""
  )
  dt.preferences.register(
    PREF_SCRIPT, "preset" .. i .. "_api_key", "string",
    "AI assistant: preset " .. i .. " API key",
    "API key for this preset, if required. Stored in darktable's Lua " ..
    "preferences (not encrypted at rest).",
    ""
  )
  dt.preferences.register(
    PREF_SCRIPT, "preset" .. i .. "_model", "string",
    "AI assistant: preset " .. i .. " model name",
    "Model identifier to send as the 'model' field, e.g. gpt-5.2, " ..
    "qwen3-vl, meta-llama/llama-4-scout.",
    ""
  )
  dt.preferences.register(
    PREF_SCRIPT, "preset" .. i .. "_supports_vision", "bool",
    "AI assistant: preset " .. i .. " supports vision",
    "Enable if this model/endpoint accepts image inputs (required for " ..
    "Analyze image).",
    false
  )
end

local function pref_read(name, ptype)
  return dt.preferences.read(PREF_SCRIPT, name, ptype)
end

local function pref_write(name, ptype, value)
  dt.preferences.write(PREF_SCRIPT, name, ptype, value)
end

-- Reads all configured (non-empty-name) presets fresh from preferences.
-- Presets are edited in darktable's preference screen; re-reading on every
-- use (rather than caching at load time) is what makes "swapping presets
-- requires no restart" true (plan Phase 1 acceptance).
local function read_presets()
  local presets = {}
  for i = 1, NUM_PRESETS do
    local name = pref_read("preset" .. i .. "_name", "string")
    if name and name ~= "" then
      presets[#presets + 1] = {
        index = i,
        name = name,
        base_url = pref_read("preset" .. i .. "_base_url", "string"),
        api_key = pref_read("preset" .. i .. "_api_key", "string"),
        model = pref_read("preset" .. i .. "_model", "string"),
        supports_vision = pref_read("preset" .. i .. "_supports_vision", "bool"),
      }
    end
  end
  return presets
end

-- ===========================================================================
-- SECTION 3: runtime file discovery (see 003-runtime-file-location.md)
-- ===========================================================================

local function getenv(name)
  local v = os.getenv(name)
  if v == nil or v == "" then return nil end
  return v
end

local function home_dir()
  return getenv("HOME") or getenv("USERPROFILE") or "."
end

-- Mirrors helper/dt_ai_helper/main.py:default_runtime_dir() exactly -- do
-- not change one side without the other (see agent-insights 003).
local function default_runtime_dir()
  if running_os == "macos" then
    return home_dir() .. "/Library/Caches/dt-ai-helper"
  elseif is_windows then
    local base = getenv("LOCALAPPDATA") or (home_dir() .. "/AppData/Local")
    return base .. "/dt-ai-helper"
  else
    local base = getenv("XDG_CACHE_HOME") or (home_dir() .. "/.cache")
    return base .. "/dt-ai-helper"
  end
end

local function runtime_file_path()
  return default_runtime_dir() .. "/runtime.json"
end

-- ===========================================================================
-- SECTION 4: module state
-- ===========================================================================

local state = {
  port = nil,
  token = nil,
  helper_pid = nil,
  helper_status = "stopped", -- "stopped" | "starting" | "running" | "error"
  last_error = nil,
  transcript_lines = {},
  last_style_file = nil,
  last_style_summary = nil,
  history_epoch = {}, -- image.id -> integer, bumped by "Clear"
  widgets = {},
}

local MAX_TRANSCRIPT_LINES = 400

-- ===========================================================================
-- SECTION 5: helper lifecycle (launch, health check, heartbeat)
-- ===========================================================================

local function helper_launch_command()
  local override = pref_read("helper_command_override", "string")
  if override and override ~= "" then
    return override
  end
  local python_path = pref_read("python_path", "string")
  if not python_path or python_path == "" then python_path = default_python end
  return python_path .. " -m dt_ai_helper.main"
end

-- Launch the helper detached from darktable, so that the shell command we
-- invoke via dt.control.execute() returns immediately instead of waiting for
-- the (long-lived) server to exit. We write a tiny platform-native launcher
-- script to darktable's tmp_dir and execute *that* -- this mirrors the
-- pattern used by darktable-org/lua-scripts' lib/dtutils.system.lua for
-- Windows (batch file avoids known quoting problems with
-- dt.control.execute on Windows) and extends the same approach to
-- Linux/macOS for symmetry and to get proper backgrounding via nohup+disown.
local function launch_helper()
  local log_file = default_runtime_dir() .. "/helper.log"
  -- Pass --runtime-file explicitly rather than relying on the Python side's
  -- own default_runtime_file() resolving to the same path we poll below --
  -- both sides currently compute the same default independently (see
  -- agent-insights 003), which is a drift hazard if only one side's default
  -- ever changes. Appended to the launch command unconditionally, including
  -- when helper_command_override is set: dt_ai_helper.main's CLI accepts
  -- --runtime-file however it's invoked, and an override that truly can't
  -- take extra arguments is already an advanced/unsupported configuration.
  local cmd = helper_launch_command() .. " --runtime-file " .. shq(runtime_file_path())

  if is_windows then
    local bat = tmp_file("launch.bat")
    local mkdir_cmd = 'if not exist "' .. default_runtime_dir():gsub("/", "\\") .. '" mkdir "' ..
      default_runtime_dir():gsub("/", "\\") .. '"'
    local script = "@echo off\r\n" .. mkdir_cmd .. "\r\n" ..
      'start "" /B ' .. cmd .. ' >> "' .. log_file:gsub("/", "\\") .. '" 2>&1\r\n' ..
      "exit /b 0\r\n"
    write_file(bat, script)
    run_shell(shq(bat))
    os.remove(bat)
  else
    local sh = tmp_file("launch.sh")
    local script = "#!/bin/sh\n" ..
      'mkdir -p "' .. default_runtime_dir() .. '"\n' ..
      "nohup " .. cmd .. ' >> "' .. log_file .. '" 2>&1 < /dev/null &\n' ..
      "disown 2>/dev/null\n" ..
      "exit 0\n"
    write_file(sh, script)
    run_shell("sh " .. shq(sh))
    os.remove(sh)
  end
end

-- Reads {port, token, pid} from the runtime file, if present and parseable.
local function read_runtime_file()
  local raw = read_file(runtime_file_path())
  if not raw then return nil end
  local data = json.decode(raw)
  if type(data) ~= "table" then return nil end
  local port = tonumber(data.port)
  local token = data.token
  if type(token) ~= "string" or not port then return nil end
  return { port = port, token = token, pid = tonumber(data.pid) }
end

local function set_status_label()
  local w = state.widgets.status_label
  if not w then return end
  local text
  if state.helper_status == "running" then
    local presets = read_presets()
    local idx = pref_read("active_preset_index", "integer")
    local model_name = "(no preset configured)"
    for _, p in ipairs(presets) do
      if p.index == idx then model_name = p.name; break end
    end
    text = "AI assistant -- helper running (model: " .. model_name .. ")"
  elseif state.helper_status == "starting" then
    text = "AI assistant -- starting helper..."
  elseif state.helper_status == "error" then
    text = "AI assistant -- helper error: " .. tostring(state.last_error)
  else
    text = "AI assistant -- helper stopped"
  end
  pcall(function() w.label = text end)
end

-- GET/POST against the helper. `body` nil means GET. Returns decoded JSON
-- table, or nil + error string. All requests: JSON body via temp file
-- (avoids shell-quoting issues, notably on Windows), curl -s --max-time,
-- Bearer auth header (plan §5.1 item 5).
local function helper_request(method, path, body)
  if not state.port or not state.token then
    return nil, "helper not connected"
  end
  local timeout = pref_read("request_timeout", "integer") or 60
  local resp_file = tmp_file("resp.json")
  local url = "http://127.0.0.1:" .. tostring(state.port) .. path
  local cmd_parts = {
    "curl", "-s", "--max-time", tostring(timeout),
    "-H", shq("Authorization: Bearer " .. state.token),
  }
  local body_file = nil
  if body ~= nil then
    body_file = tmp_file("body.json")
    write_file(body_file, json.encode(body))
    table.insert(cmd_parts, "-H")
    table.insert(cmd_parts, shq("Content-Type: application/json"))
    table.insert(cmd_parts, "-X")
    table.insert(cmd_parts, method or "POST")
    table.insert(cmd_parts, "--data-binary")
    table.insert(cmd_parts, "@" .. shq(body_file))
  elseif method and method ~= "GET" then
    table.insert(cmd_parts, "-X")
    table.insert(cmd_parts, method)
  end
  table.insert(cmd_parts, "-o")
  table.insert(cmd_parts, shq(resp_file))
  table.insert(cmd_parts, shq(url))

  run_shell(table.concat(cmd_parts, " "))

  local raw = read_file(resp_file)
  os.remove(resp_file)
  if body_file then os.remove(body_file) end

  if not raw or raw == "" then
    return nil, "no response from helper (is it running?)"
  end
  local decoded, err = json.decode(raw)
  if not decoded then
    return nil, "invalid response from helper: " .. tostring(err)
  end
  return decoded
end

local function health_check()
  local resp, err = helper_request("GET", "/health", nil)
  if resp and resp.status == "ok" then
    state.helper_status = "running"
    state.last_error = nil
    return true
  end
  state.last_error = err or "unhealthy"
  return false
end

-- Attempts to (re)connect to an already-running helper by reading the
-- runtime file and health-checking it; launches a fresh helper if that
-- fails. Safe to call repeatedly (e.g. on every panel action) since it's a
-- no-op once state.port/state.token are populated and healthy.
local function ensure_helper_running()
  if state.helper_status == "running" and state.port and health_check() then
    return true
  end

  local rt = read_runtime_file()
  if rt then
    state.port = rt.port
    state.token = rt.token
    state.helper_pid = rt.pid
    if health_check() then
      set_status_label()
      return true
    end
  end

  -- No usable runtime file yet (or it's stale/dead) -- launch and wait
  -- briefly for it to appear. This runs inside a button callback / dispatch
  -- coroutine, so control.sleep here is safe and non-blocking to the GTK
  -- main loop per plan §5.1/§5.3.
  state.helper_status = "starting"
  set_status_label()
  launch_helper()

  for _ = 1, 20 do -- up to ~10s
    dt.control.sleep(500)
    rt = read_runtime_file()
    if rt then
      state.port = rt.port
      state.token = rt.token
      state.helper_pid = rt.pid
      if health_check() then
        set_status_label()
        return true
      end
    end
  end

  state.helper_status = "error"
  state.last_error = state.last_error or "helper did not start in time"
  set_status_label()
  return false
end

-- Heartbeat: keeps the helper alive (it self-exits ~10 min after the last
-- beat, per plan §3). Runs for the lifetime of darktable via
-- darktable.control.dispatch, checking darktable.control.ending so it exits
-- cleanly on shutdown instead of looping forever.
local HEARTBEAT_INTERVAL_MS = 120000 -- ~2 minutes, per task spec

local function heartbeat_loop()
  while not dt.control.ending do
    dt.control.sleep(HEARTBEAT_INTERVAL_MS)
    if dt.control.ending then break end
    if state.port and state.token then
      helper_request("POST", "/heartbeat", json.object({}))
    end
  end
end

-- ===========================================================================
-- SECTION 6: transcript / status UI helpers
-- ===========================================================================

local function refresh_transcript_widget()
  local w = state.widgets.transcript
  if not w then return end
  while #state.transcript_lines > MAX_TRANSCRIPT_LINES do
    table.remove(state.transcript_lines, 1)
  end
  pcall(function() w.text = table.concat(state.transcript_lines, "\n") end)
end

local function append_transcript(who, text)
  text = tostring(text)
  local prefix = who and (who .. ": ") or ""
  for line in (text .. "\n"):gmatch("(.-)\n") do
    state.transcript_lines[#state.transcript_lines + 1] = prefix .. line
    prefix = "" -- only the first physical line gets the "You:"/"AI:" prefix
  end
  refresh_transcript_widget()
end

-- ===========================================================================
-- SECTION 7: image context collection (plan §5.1 item 2/3, §5.2)
-- ===========================================================================

local function current_image()
  local images = dt.gui.action_images
  if images and images[1] then return images[1] end
  return nil
end

-- Best-effort attempt to make darktable flush the current history stack to
-- the XMP sidecar before we read it, so the assistant sees up-to-date edit
-- state. The action path and its availability are version-dependent (plan
-- §2 item 4), hence the pcall: on any darktable release where this action
-- doesn't exist, or gui.action itself errors, we just skip the flush and
-- rely on whatever's already on disk (the helper independently guards
-- against stale/missing XMP by falling back to library.db, per plan §7.2).
local function attempt_sidecar_flush()
  pcall(function()
    dt.gui.action("lib/copy_history/write sidecar files", 0, "", "activate", 1)
  end)
end

local function build_exif(image)
  return {
    iso = image.exif_iso,
    aperture = image.exif_aperture,
    exposure = image.exif_exposure,
    focal_length = image.exif_focal_length,
    maker = image.exif_maker,
    model = image.exif_model,
    datetime = image.exif_datetime_taken,
  }
end

-- Builds the `image_context` object from plan §5.2. Lua supplies what it can
-- read directly from the Lua API (EXIF, sidecar path, the image's own
-- change_timestamp); the helper is authoritative for actually parsing the
-- sidecar and for the xmp-vs-db freshness decision, since it can stat files
-- with full os.path precision on all three platforms without an extra
-- shell-out from Lua. This is a deliberate simplification of plan §5.1 item
-- 3's "compare sidecar mtime against change_timestamp" -- documented in
-- documentation/agent-insights/004-xmp-freshness-check-split.md.
local function build_image_context(image, include_edit_state)
  local ctx = json.object({
    filepath = image.path .. "/" .. image.filename,
    sidecar = image.sidecar,
    exif = build_exif(image),
    change_timestamp = image.change_timestamp,
    rating = image.rating,
  })
  if not include_edit_state then
    ctx.sidecar = nil
    ctx.change_timestamp = nil
  end
  return ctx
end

-- ===========================================================================
-- SECTION 8: preview export (Optimize / Analyze image)
-- ===========================================================================

-- Exports a downscaled JPEG preview of `image` to darktable's tmp_dir at the
-- configured max edge. format:write_image() is a blocking call but carries
-- the `implicit_yield` attribute in the Lua API docs (like
-- control.execute/control.sleep), meaning it yields to darktable's
-- scheduler rather than freezing the UI -- safe to call directly from a
-- button callback.
--
-- NOTE: as of Lua API 9.3.0 (darktable 4.8.x), write_image() returns false
-- on *success* (a documented API quirk/inversion). Rather than branch on
-- api_version_minor to interpret the boolean correctly, we verify success by
-- checking that the output file actually exists, which is version-agnostic.
local function export_preview(image)
  local ok, format = pcall(dt.new_format, "jpeg")
  if not ok or not format then return nil, "could not create jpeg exporter" end

  local max_edge = pref_read("preview_max_edge", "integer") or 1024
  pcall(function() format.max_width = max_edge end)
  pcall(function() format.max_height = max_edge end)
  pcall(function() format.quality = 92 end)

  local out_path = tmp_file("preview_" .. tostring(image.id) .. ".jpg")
  local export_ok = pcall(function() format:write_image(image, out_path, false) end)
  if not export_ok then return nil, "preview export failed" end

  local f = io.open(out_path, "rb")
  if not f then return nil, "preview export did not produce a file" end
  f:close()
  return out_path
end

-- ===========================================================================
-- SECTION 9: job submission + polling (plan §5.1 item 2, §5.3)
-- ===========================================================================

-- Submits a job to `path` (one of /chat, /optimize, /vision) and polls
-- GET /jobs/<id> every ~700ms until it reaches a terminal state or the
-- configured request_timeout budget is exceeded. Must be called from a
-- context where darktable.control.sleep is safe (button callbacks / a
-- dispatch coroutine) -- never called at file-load time.
local POLL_INTERVAL_MS = 700

local function submit_and_poll(path, payload)
  local submit_resp, err = helper_request("POST", path, payload)
  if not submit_resp then
    return nil, err
  end
  local job_id = submit_resp.job_id
  if not job_id then
    return nil, "helper did not return a job_id"
  end

  local timeout = pref_read("request_timeout", "integer") or 60
  local budget_ms = timeout * 1000 + 15000 -- generous extra margin over one curl's own timeout
  local waited_ms = 0

  while waited_ms < budget_ms do
    dt.control.sleep(POLL_INTERVAL_MS)
    waited_ms = waited_ms + POLL_INTERVAL_MS
    local job, jerr = helper_request("GET", "/jobs/" .. job_id, nil)
    if job then
      if job.status == "done" then
        return job
      elseif job.status == "error" then
        return nil, job.error or "job failed"
      end
      -- "queued" / "running": keep polling
    elseif jerr then
      -- Transient poll failure (e.g. one dropped curl call) -- keep trying
      -- until the overall budget is exhausted rather than giving up on the
      -- first hiccup.
    end
  end
  return nil, "timed out waiting for a response"
end

-- ===========================================================================
-- SECTION 10: action handlers
-- ===========================================================================

local function active_preset()
  local presets = read_presets()
  local idx = pref_read("active_preset_index", "integer")
  for _, p in ipairs(presets) do
    if p.index == idx then return p end
  end
  return presets[1] -- fall back to the first configured preset, if any
end

local function history_id_for(image)
  local epoch = state.history_epoch[image.id] or 0
  return tostring(image.id) .. ":" .. tostring(epoch)
end

local function is_localhost(url)
  if type(url) ~= "string" then return false end
  return url:match("://127%.0%.0%.1") ~= nil or url:match("://localhost") ~= nil
    or url:match("://%[::1%]") ~= nil
end

-- Pushes the preset's connection details to the helper's /config so the
-- next job uses the model the user picked in the combobox. Cheap and
-- idempotent; called before every request rather than only on combobox
-- change, so editing a preset's fields in the preferences screen and
-- re-sending "just works" without an explicit "apply" step.
local function sync_active_preset()
  local preset = active_preset()
  if not preset then return nil, "no model preset configured (see AI assistant preferences)" end
  helper_request("POST", "/config", json.object({
    name = preset.name,
    base_url = preset.base_url,
    api_key = (preset.api_key ~= "" and preset.api_key or nil),
    model = preset.model,
    supports_vision = preset.supports_vision,
  }))
  return preset
end

local function handle_job_result(job)
  if job.answer then
    append_transcript("AI", job.answer)
  end
  if job.style and job.style.file then
    state.last_style_file = job.style.file
    state.last_style_summary = job.style.summary
    if job.style.summary then
      append_transcript("AI", "[style ready] " .. job.style.summary)
    end
    local btn = state.widgets.apply_style_btn
    if btn then pcall(function() btn.sensitive = true end) end
  end
end

local function do_send()
  local image = current_image()
  if not image then
    append_transcript(nil, "(select or hover an image first)")
    return
  end
  local message = state.widgets.entry.text
  if not message or message == "" then return end
  append_transcript("You", message)
  state.widgets.entry.text = ""

  if not ensure_helper_running() then
    append_transcript(nil, "(helper unavailable: " .. tostring(state.last_error) .. ")")
    return
  end
  local preset, perr = sync_active_preset()
  if not preset then
    append_transcript(nil, "(" .. perr .. ")")
    return
  end

  local include_state = state.widgets.include_state_check.value
  local payload = json.object({
    message = message,
    history_id = history_id_for(image),
  })
  if include_state then
    attempt_sidecar_flush()
    payload.image_context = build_image_context(image, true)
  end

  append_transcript(nil, "...")
  local job, err = submit_and_poll("/chat", payload)
  state.transcript_lines[#state.transcript_lines] = nil -- drop the "..." placeholder
  if not job then
    append_transcript(nil, "(error: " .. tostring(err) .. ")")
    refresh_transcript_widget()
    return
  end
  handle_job_result(job)
end

local function do_optimize()
  local image = current_image()
  if not image then
    append_transcript(nil, "(select or hover an image first)")
    return
  end
  if not ensure_helper_running() then
    append_transcript(nil, "(helper unavailable: " .. tostring(state.last_error) .. ")")
    return
  end
  local preset, perr = sync_active_preset()
  if not preset then
    append_transcript(nil, "(" .. perr .. ")")
    return
  end

  append_transcript(nil, "Optimize: exporting preview...")
  local preview_path, exp_err = export_preview(image)
  if not preview_path then
    state.transcript_lines[#state.transcript_lines] = nil
    append_transcript(nil, "(preview export failed: " .. tostring(exp_err) .. ")")
    refresh_transcript_widget()
    return
  end
  state.transcript_lines[#state.transcript_lines] = "Optimize: analyzing..."
  refresh_transcript_widget()

  attempt_sidecar_flush()
  local payload = json.object({
    image_context = build_image_context(image, true),
    preview_path = preview_path,
  })
  local job, err = submit_and_poll("/optimize", payload)
  os.remove(preview_path)
  state.transcript_lines[#state.transcript_lines] = nil
  if not job then
    append_transcript(nil, "(optimize error: " .. tostring(err) .. ")")
    refresh_transcript_widget()
    return
  end
  handle_job_result(job)
end

local function do_analyze()
  local image = current_image()
  if not image then
    append_transcript(nil, "(select or hover an image first)")
    return
  end
  if not ensure_helper_running() then
    append_transcript(nil, "(helper unavailable: " .. tostring(state.last_error) .. ")")
    return
  end
  local preset, perr = sync_active_preset()
  if not preset then
    append_transcript(nil, "(" .. perr .. ")")
    return
  end
  if not preset.supports_vision then
    append_transcript(nil, "(active preset '" .. preset.name .. "' is not marked as vision-capable)")
    return
  end
  -- Privacy gate (plan §5.4/§11): image bytes only ever leave the machine on
  -- a vision request, and only when the endpoint is localhost or the user
  -- has explicitly opted in. Enforced here (not just in the helper) so the
  -- preview is never even sent when refused.
  if not is_localhost(preset.base_url) and not pref_read("allow_cloud_upload", "bool") then
    append_transcript(nil,
      "(refused: '" .. preset.name .. "' is a cloud endpoint and " ..
      "'allow image upload to cloud endpoints' is off -- enable it in " ..
      "preferences to use Analyze image with this preset)")
    return
  end

  append_transcript(nil, "Analyze image: exporting preview...")
  local preview_path, exp_err = export_preview(image)
  if not preview_path then
    state.transcript_lines[#state.transcript_lines] = nil
    append_transcript(nil, "(preview export failed: " .. tostring(exp_err) .. ")")
    refresh_transcript_widget()
    return
  end
  state.transcript_lines[#state.transcript_lines] = "Analyze image: analyzing..."
  refresh_transcript_widget()

  local include_state = state.widgets.include_state_check.value
  if include_state then attempt_sidecar_flush() end
  local message = state.widgets.entry.text
  if message == "" then message = nil end
  state.widgets.entry.text = ""

  local payload = json.object({
    message = message,
    preview_path = preview_path,
    -- The helper's privacy gate (plan §5.4/§11) is evaluated per-request
    -- against whichever preset is active, and has no other channel to see
    -- this user-level consent toggle (see agent-insights 010/011) -- send
    -- the pref's current value on every /vision call, not just the local
    -- refusal check above.
    allow_upload = pref_read("allow_cloud_upload", "bool"),
  })
  if include_state then
    payload.image_context = build_image_context(image, true)
  end
  local job, err = submit_and_poll("/vision", payload)
  os.remove(preview_path)
  state.transcript_lines[#state.transcript_lines] = nil
  if not job then
    append_transcript(nil, "(analyze error: " .. tostring(err) .. ")")
    refresh_transcript_widget()
    return
  end
  handle_job_result(job)
end

-- Imports the last returned .dtstyle and applies it to the current image.
-- darktable.styles.import()/apply() are the sanctioned "apply edits" path
-- per plan §2 item 8; both are wrapped in pcall since dt_style_t plumbing
-- differences across darktable versions are exactly the kind of thing the
-- plan asks us to degrade gracefully around rather than assume.
local function do_apply_style()
  local image = current_image()
  if not image then
    append_transcript(nil, "(select or hover an image first)")
    return
  end
  if not state.last_style_file then
    append_transcript(nil, "(no style available yet -- run Optimize or Analyze first)")
    return
  end
  local ok, style_or_err = pcall(dt.styles.import, state.last_style_file)
  if not ok then
    append_transcript(nil, "(could not import style: " .. tostring(style_or_err) .. ")")
    return
  end
  local style = style_or_err
  if style == nil then
    -- Some darktable versions may not return the imported style object
    -- directly; fall back to scanning the styles list for the most
    -- recently added ai-assistant style.
    local ok2, list = pcall(function() return dt.styles end)
    if ok2 and list then
      for _, s in ipairs(list) do
        if tostring(s.name):match("^ai%-assistant/") then style = s end -- last match wins (most recent)
      end
    end
  end
  if style == nil then
    append_transcript(nil, "(style imported but could not be located to apply -- check darktable's styles panel)")
    return
  end
  local apply_ok, apply_err = pcall(dt.styles.apply, style, image)
  if not apply_ok then
    append_transcript(nil, "(could not apply style: " .. tostring(apply_err) .. ")")
    return
  end
  append_transcript(nil, "Applied style" .. (state.last_style_summary and (": " .. state.last_style_summary) or "."))
end

local function do_clear()
  local image = current_image()
  if image then
    state.history_epoch[image.id] = (state.history_epoch[image.id] or 0) + 1
  end
  state.transcript_lines = {}
  state.last_style_file = nil
  state.last_style_summary = nil
  refresh_transcript_widget()
  local btn = state.widgets.apply_style_btn
  if btn then pcall(function() btn.sensitive = false end) end
end

-- ===========================================================================
-- SECTION 11: widget tree (plan §5.1)
-- ===========================================================================

local function build_model_combobox()
  local presets = read_presets()
  local active_idx = pref_read("active_preset_index", "integer") or 1
  local labels = {}
  local slot_of = {} -- combobox position -> preset slot index
  local selected_pos = 1
  for pos, p in ipairs(presets) do
    labels[pos] = p.name
    slot_of[pos] = p.index
    if p.index == active_idx then selected_pos = pos end
  end
  if #labels == 0 then labels = { "(no presets configured)" } end

  local combobox = dt.new_widget("combobox") {
    label = "model",
    value = selected_pos,
    table.unpack(labels),
  }
  combobox.changed_callback = function(w)
    local pos = w.selected
    local slot = slot_of[pos]
    if slot then
      pref_write("active_preset_index", "integer", slot)
      set_status_label()
    end
  end
  return combobox
end

local function build_widgets()
  local status_label = dt.new_widget("section_label") { label = "AI assistant -- helper stopped" }

  local transcript = dt.new_widget("text_view") {
    text = "",
    editable = false,
    tooltip = "Conversation with the AI assistant for the current image.",
  }

  local entry = dt.new_widget("entry") {
    placeholder = "Ask about this edit, e.g. \"make the sky more dramatic\"...",
    editable = true,
    tooltip = "The darktable Lua API does not expose an Enter-to-submit " ..
      "callback for text entries, so use the Send button.",
  }

  local send_btn = dt.new_widget("button") { label = "Send" }
  local optimize_btn = dt.new_widget("button") { label = "Optimize" }
  local analyze_btn = dt.new_widget("button") { label = "Analyze image" }
  local apply_style_btn = dt.new_widget("button") { label = "Apply style", sensitive = false }
  local clear_btn = dt.new_widget("button") { label = "Clear" }

  local button_box = dt.new_widget("box") {
    orientation = "horizontal",
    send_btn, optimize_btn, analyze_btn, apply_style_btn, clear_btn,
  }

  local model_combobox = build_model_combobox()

  local include_state_check = dt.new_widget("check_button") {
    label = "include my current edit state in context",
    value = true,
    tooltip = "Sends EXIF + the enabled-module list parsed from the XMP " ..
      "sidecar (or library.db fallback) along with your message.",
  }

  state.widgets = {
    status_label = status_label,
    transcript = transcript,
    entry = entry,
    send_btn = send_btn,
    optimize_btn = optimize_btn,
    analyze_btn = analyze_btn,
    apply_style_btn = apply_style_btn,
    clear_btn = clear_btn,
    model_combobox = model_combobox,
    include_state_check = include_state_check,
  }

  -- Wrap each handler in pcall so a bug in one request never leaves the
  -- panel's buttons permanently unresponsive or crashes darktable's Lua
  -- runtime; failures are still surfaced to the user via print_error + the
  -- transcript.
  local function guarded(fn)
    return function()
      local ok, err = pcall(fn)
      if not ok then
        dt.print_error("dt-ai-assistant: " .. tostring(err))
        append_transcript(nil, "(internal error: " .. tostring(err) .. ")")
      end
    end
  end

  send_btn.clicked_callback = guarded(do_send)
  optimize_btn.clicked_callback = guarded(do_optimize)
  analyze_btn.clicked_callback = guarded(do_analyze)
  apply_style_btn.clicked_callback = guarded(do_apply_style)
  clear_btn.clicked_callback = guarded(do_clear)

  return dt.new_widget("box") {
    orientation = "vertical",
    status_label,
    transcript,
    entry,
    button_box,
    model_combobox,
    include_state_check,
  }
end

-- ===========================================================================
-- SECTION 12: registration
-- ===========================================================================

local main_widget = build_widgets()

dt.register_lib(
  "ai_assistant",       -- plugin_name (unique)
  "AI assistant",        -- user-visible name
  true,                  -- expandable
  false,                 -- resettable
  {
    [dt.gui.views.darkroom] = { "DT_UI_CONTAINER_PANEL_RIGHT_CENTER", 100 },
    [dt.gui.views.lighttable] = { "DT_UI_CONTAINER_PANEL_RIGHT_CENTER", 100 },
  },
  main_widget,
  nil, -- view_enter
  nil  -- view_leave
)

-- Try to pick up an already-running helper (e.g. left over from a previous
-- darktable session that hasn't idled out yet) without blocking startup;
-- if none is found we just show "stopped" until the user's first action
-- triggers ensure_helper_running(). We deliberately do NOT launch the
-- helper eagerly at script-load time: launching involves control.sleep
-- polling loops that are only meant to run inside coroutine-friendly
-- contexts, and luarc/script load time is documented as one where long
-- operations should be dispatched rather than run inline.
dt.control.dispatch(function()
  ensure_helper_running()
end)

-- Heartbeat for the lifetime of darktable (plan: "self-terminates after N
-- minutes without a heartbeat so it never outlives darktable").
dt.control.dispatch(heartbeat_loop)

-- Best-effort cleanup marker; we do not attempt to kill the helper on exit
-- because darktable may be relaunched shortly after (e.g. crash-restart)
-- and reusing an already-warm helper is preferable. The helper's own
-- heartbeat watchdog (~10 min, see helper/dt_ai_helper/main.py) guarantees
-- it never outlives darktable for long.
pcall(function()
  dt.register_event("dt-ai-assistant", "exit", function()
    state.helper_status = "stopped"
  end)
end)

-- ===========================================================================
-- script_manager compatibility (optional; harmless if script_manager is not
-- used to load this file). See examples/moduleExample.lua in
-- darktable-org/lua-scripts for the convention this follows.
-- ===========================================================================

local script_data = {}
script_data.metadata = {
  name = "dt-ai-assistant",
  purpose = "AI edit assistant chat/optimize/vision panel backed by a local helper",
  author = "collodion contributors",
  help = "https://github.com/collodion/collodion",
}
script_data.destroy = function()
  pcall(function() dt.gui.libs["ai_assistant"].visible = false end)
end
script_data.restart = function()
  pcall(function() dt.gui.libs["ai_assistant"].visible = true end)
end
script_data.destroy_method = "hide"
script_data.show = script_data.restart

return script_data

-- vim: shiftwidth=2 expandtab tabstop=2 cindent syntax=lua
