#!/bin/sh
# Install the collodion AI assistant (Linux/macOS): creates a venv under
# darktable's config directory, installs the dt-ai-helper Python package
# into it, copies the Lua front-end into darktable's lua/ directory, and
# registers it in darktable's luarc if it isn't already there.
#
# Usage:
#   scripts/install.sh [--darktable-config-dir DIR] [--venv-dir DIR] [--python PY]
#
# Safe to re-run: every step below is idempotent (re-installing the
# package upgrades it in place, copying the Lua file overwrites the old
# copy, and the luarc "require" line is only appended if not already
# present).
#
# See README.md's "Install" section for the full picture, including what
# you still have to do by hand afterwards (set python_path / helper prefs
# inside darktable so the Lua side finds this venv).

set -eu

# ---------------------------------------------------------------------------
# Locate the repo (this script lives in <repo>/scripts/install.sh)
# ---------------------------------------------------------------------------
script_dir=$(cd "$(dirname "$0")" && pwd)
repo_root=$(cd "$script_dir/.." && pwd)

os_name=$(uname -s)

# ---------------------------------------------------------------------------
# Defaults (overridable via flags below)
# ---------------------------------------------------------------------------
python_bin="python3"
if [ "$os_name" = "Darwin" ]; then
  darktable_config_dir="$HOME/Library/Application Support/darktable"
else
  darktable_config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/darktable"
fi
venv_dir=""

usage() {
  cat <<EOF
Usage: $0 [--darktable-config-dir DIR] [--venv-dir DIR] [--python PY]

  --darktable-config-dir DIR  darktable's config directory
                               (default: $darktable_config_dir)
  --venv-dir DIR               where to create the helper's venv
                               (default: <darktable-config-dir>/ai-assistant-venv)
  --python PY                  python interpreter to build the venv with
                               (default: $python_bin)
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --darktable-config-dir)
      darktable_config_dir="$2"
      shift 2
      ;;
    --venv-dir)
      venv_dir="$2"
      shift 2
      ;;
    --python)
      python_bin="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [ -z "$venv_dir" ]; then
  venv_dir="$darktable_config_dir/ai-assistant-venv"
fi

if ! command -v "$python_bin" >/dev/null 2>&1; then
  echo "error: python interpreter '$python_bin' not found on PATH" >&2
  exit 1
fi

echo "collodion install"
echo "  repo root:              $repo_root"
echo "  darktable config dir:   $darktable_config_dir"
echo "  helper venv:            $venv_dir"
echo "  python interpreter:     $python_bin"
echo

# ---------------------------------------------------------------------------
# 1. Create (or reuse) the venv, install the helper package into it
# ---------------------------------------------------------------------------
if [ ! -d "$venv_dir" ]; then
  echo "==> creating venv at $venv_dir"
  "$python_bin" -m venv "$venv_dir"
else
  echo "==> reusing existing venv at $venv_dir"
fi

venv_python="$venv_dir/bin/python"
if [ ! -x "$venv_python" ]; then
  echo "error: venv creation did not produce $venv_python" >&2
  exit 1
fi

echo "==> installing dt-ai-helper into the venv (editable, from $repo_root/helper)"
"$venv_python" -m pip install --upgrade pip >/dev/null
"$venv_python" -m pip install -e "$repo_root/helper"

# ---------------------------------------------------------------------------
# 2. Copy the Lua front-end into darktable's lua/ directory
# ---------------------------------------------------------------------------
dt_lua_dir="$darktable_config_dir/lua"
mkdir -p "$dt_lua_dir"
echo "==> copying lua/dt-ai-assistant.lua to $dt_lua_dir/"
cp "$repo_root/lua/dt-ai-assistant.lua" "$dt_lua_dir/dt-ai-assistant.lua"

# ---------------------------------------------------------------------------
# 3. Register the script in darktable's luarc, if not already there
# ---------------------------------------------------------------------------
luarc="$darktable_config_dir/luarc"
require_line='require "dt-ai-assistant"'

mkdir -p "$darktable_config_dir"
touch "$luarc"

if grep -qF "$require_line" "$luarc" 2>/dev/null; then
  echo "==> $luarc already requires dt-ai-assistant, leaving it alone"
else
  echo "==> appending '$require_line' to $luarc"
  printf '\n%s\n' "$require_line" >> "$luarc"
fi

echo
echo "Done."
echo
echo "Next steps inside darktable's AI assistant preferences (lua options tab):"
echo "  - 'python interpreter'                -> $venv_python"
echo "  - or leave it empty and set 'helper launch command override' to:"
echo "      $venv_python -m dt_ai_helper.main"
echo "  - add at least one model preset (base URL / model / API key)"
echo "(Re)start darktable to load the plugin."
