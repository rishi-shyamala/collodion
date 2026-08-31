"""``image_context`` enrichment (plan §5.2) and its prompt serialization.

Lua sends a partial ``image_context``: ``filepath``, ``sidecar`` (path),
``exif``, and (per
``documentation/agent-insights/004-xmp-freshness-check-split.md``) the
image's raw ``change_timestamp`` -- it does *not* decide xmp-vs-db itself,
because darktable's bundled Lua has no portable ``stat()`` call. This module
is where that decision actually happens: it parses the sidecar via
``xmp.py``, falls back to ``dbfallback.py`` when the sidecar is missing,
stale, or unparseable (and a db path/image id are available), and produces
the ``enabled_modules``/``iop_order`` portion of the full ``image_context``
shape from plan §5.2.

It also renders the resolved ``image_context`` as the ``CURRENT EDIT
STATE`` text block that ``prompts.build_chat_messages`` appends to the
user's message (plan §5.5).

Friction note (for whoever reads this before touching ``xmp.py``/
``dbfallback.py``): both modules expose a single ``read_edit_state`` entry
point that unconditionally reads their one source (sidecar file, or
``library.db``) and returns the same output shape -- there's no shared "give
me whichever source is freshest" function to call into. That decision has
to live somewhere, and per the ownership map it isn't this worker's place
to add it to ``xmp.py`` itself, so it lives here instead, built on top of
both modules' public functions.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from . import dbfallback, xmp

#: How much slack to give a sidecar's mtime vs. the image's change_timestamp
#: before calling it "stale". A few seconds absorbs filesystem timestamp
#: granularity and the gap between darktable finishing a write and Lua
#: reading `change_timestamp`, without meaningfully weakening the check.
DEFAULT_STALENESS_GRACE_SECONDS = 5.0

_EMPTY_EDIT_STATE: dict[str, Any] = {
    "history_source": "none",
    "enabled_modules": [],
    "iop_order": [],
}


def _parse_change_timestamp(value: Any) -> float | None:
    """Best-effort parse of the Lua-supplied ``change_timestamp``.

    Documented as a Unix timestamp on ``dt_lua_image_t``, but Lua's JSON
    encoding may hand it back as a string (or omit it entirely on older
    darktable versions) -- accept both, and treat anything unparseable as
    "unknown" rather than raising.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def sidecar_is_fresh(sidecar_path: str | Path, change_timestamp: Any) -> bool:
    """True if ``sidecar_path``'s mtime is at/after the image's edit time.

    No ``change_timestamp`` supplied means we can't tell -- trust the
    sidecar rather than refusing to use it (darktable versions predating
    Lua exposing ``change_timestamp`` still write sidecars correctly).
    """
    ts = _parse_change_timestamp(change_timestamp)
    if ts is None:
        return True
    try:
        mtime = os.path.getmtime(sidecar_path)
    except OSError:
        return False
    return mtime >= ts - DEFAULT_STALENESS_GRACE_SECONDS


def resolve_edit_state(
    raw_context: dict[str, Any],
    *,
    db_path: str | Path | None = None,
    image_id: int | None = None,
) -> dict[str, Any]:
    """Resolve ``history_source``/``enabled_modules``/``iop_order`` for one image.

    Preference order: a fresh, parseable sidecar; ``library.db`` (only if
    both ``db_path`` and ``image_id`` are given -- Lua does not currently
    send either in ``image_context``, so this is an opt-in path for a future
    worker who wires it up); a stale-but-parseable sidecar (name-only value
    beats nothing); otherwise an explicit empty edit state. This function
    never raises -- a chat turn with "include edit state" on should still
    get an answer even when nothing is decodable yet.
    """
    sidecar = raw_context.get("sidecar")
    change_timestamp = raw_context.get("change_timestamp")

    if sidecar and Path(sidecar).is_file():
        if sidecar_is_fresh(sidecar, change_timestamp):
            try:
                return xmp.read_edit_state(sidecar)
            except xmp.XmpParseError:
                pass  # fall through to db / stale-sidecar / empty

    if db_path is not None and image_id is not None:
        try:
            return dbfallback.read_edit_state(db_path, image_id)
        except Exception:
            pass  # fall through -- a stale sidecar still beats nothing

    if sidecar and Path(sidecar).is_file():
        try:
            return xmp.read_edit_state(sidecar)
        except xmp.XmpParseError:
            pass

    return dict(_EMPTY_EDIT_STATE)


def build_image_context(raw_context: dict[str, Any], **resolve_kwargs: Any) -> dict[str, Any]:
    """Merge Lua-supplied fields with the resolved edit state (plan §5.2 shape)."""
    edit_state = resolve_edit_state(raw_context, **resolve_kwargs)
    context: dict[str, Any] = {
        "filepath": raw_context.get("filepath"),
        "sidecar": raw_context.get("sidecar"),
        "exif": raw_context.get("exif") or {},
    }
    context.update(edit_state)
    if "histogram" in raw_context:
        # Passed through untouched -- produced by histogram.py (W6), not us.
        context["histogram"] = raw_context["histogram"]
    return context


# ---------------------------------------------------------------------------
# CURRENT EDIT STATE serializer (consumed by prompts.build_chat_messages)
# ---------------------------------------------------------------------------


def _format_module(module: dict[str, Any]) -> str:
    op = module.get("op", "?")
    label = module.get("label") or op
    header = f"- {label} ({op})" if label and label != op else f"- {op}"

    decoded = module.get("params_decoded")
    if decoded:
        settings = ", ".join(f"{k}={v}" for k, v in decoded.items())
        return f"{header}: {settings}"

    note = module.get("note")
    if note:
        return f"{header}: {note}"
    return f"{header}: (enabled, values unavailable)"


def render_edit_state_block(image_context: dict[str, Any] | None) -> str | None:
    """Render a resolved ``image_context`` as the ``CURRENT EDIT STATE`` block.

    Returns ``None`` when there's nothing meaningful to show (no
    ``image_context``, or a resolved-but-empty edit state) so callers can
    omit the section entirely instead of injecting an empty header.
    """
    if not image_context:
        return None
    modules = image_context.get("enabled_modules") or []
    if not modules:
        return None

    lines = ["CURRENT EDIT STATE"]
    source = image_context.get("history_source")
    if source:
        lines.append(f"(history source: {source})")

    exif = image_context.get("exif") or {}
    exif_bits = ", ".join(f"{k}={v}" for k, v in exif.items() if v is not None)
    if exif_bits:
        lines.append(f"exif: {exif_bits}")

    iop_order = image_context.get("iop_order")
    if iop_order:
        lines.append("processing order: " + " -> ".join(iop_order))

    lines.append("enabled modules:")
    lines.extend(_format_module(module) for module in modules)
    return "\n".join(lines)
