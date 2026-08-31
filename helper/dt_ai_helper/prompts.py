"""System prompts and message assembly for chat / optimize / vision (plan §5.5).

``build_chat_messages`` is the fully-implemented Phase 1 piece this worker
(W5) owns. ``build_optimize_messages`` and the vision prompt functions are
intentionally minimal stubs -- Phase 3/4 (W6) owns their full logic (rule-tag
driven retrieval queries, two-pass describe/recommend) -- but they exist
here, with the shape described in plan §5.5, so callers can be written
against a stable interface today and W6 can fill them in without renaming
anything.
"""

from __future__ import annotations

from typing import Any

#: darktable version the assistant claims to be embedded in, for the system
#: prompt's opening sentence. Not read from the running darktable instance
#: (Lua doesn't send one yet) -- a fixed, honest "4.6+" per plan §5.1.
DEFAULT_DT_VERSION = "4.6+"

# ---------------------------------------------------------------------------
# Chat (plan §5.5, first bullet) -- Phase 1, fully owned by this worker.
# ---------------------------------------------------------------------------

CHAT_SYSTEM_PROMPT_TEMPLATE = (
    "You are an assistant embedded in darktable {dt_version}, helping a "
    "photographer improve a specific edit. Only reference modules and "
    "controls that appear in the provided MODULE LIBRARY excerpts or in the "
    "CURRENT EDIT STATE below -- never invent a module or slider name that "
    "isn't in that context. Give steps as: module name -> section -> slider "
    "-> suggested value/range. Prefer a scene-referred workflow (filmic rgb "
    "or sigmoid, color balance rgb, tone equalizer) unless the current edit "
    "state shows display-referred modules already in use, in which case "
    "work within that existing workflow instead of proposing a switch "
    "unprompted. If the provided context doesn't cover what's being asked, "
    "say so plainly rather than guessing at slider names."
)


def chat_system_prompt(*, dt_version: str = DEFAULT_DT_VERSION) -> str:
    return CHAT_SYSTEM_PROMPT_TEMPLATE.format(dt_version=dt_version)


def build_chat_messages(
    *,
    user_message: str,
    history: list[dict[str, Any]] | None = None,
    edit_state_block: str | None = None,
    module_library_block: str | None = None,
    dt_version: str = DEFAULT_DT_VERSION,
) -> list[dict[str, Any]]:
    """Assemble the full ``messages`` list for one ``/chat`` turn.

    Order: system prompt, then prior turns (already trimmed to the history
    budget by the caller), then this turn's user message with the two
    context blocks -- ``CURRENT EDIT STATE`` and ``MODULE LIBRARY`` -- appended
    verbatim. The blocks are attached to *this* user message rather than the
    system prompt so they stay fresh every turn (the edit state and the RAG
    hits for the latest question both change turn to turn) while the
    server-side history above them stays untouched.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": chat_system_prompt(dt_version=dt_version)}
    ]
    messages.extend(history or [])

    parts = [user_message]
    if edit_state_block:
        parts.append(edit_state_block)
    if module_library_block:
        parts.append(module_library_block)
    messages.append({"role": "user", "content": "\n\n".join(parts)})
    return messages


# ---------------------------------------------------------------------------
# Optimize (plan §5.5, second bullet / §6) -- Phase 3, owned by W6.
# ---------------------------------------------------------------------------

OPTIMIZE_SYSTEM_PROMPT = (
    "You are an assistant embedded in darktable, analyzing an image's "
    "histogram statistics, EXIF metadata, and current edit state to "
    "recommend module settings. Respond with strict JSON only, matching "
    'this shape: {"assessment": str, "recommendations": [{"module": str, '
    '"why": str, "settings": [{"control": str, "value": str}], "priority": '
    "int}]}. Only reference modules and controls that appear in the "
    "provided MODULE LIBRARY excerpts."
)


def optimize_system_prompt() -> str:
    return OPTIMIZE_SYSTEM_PROMPT


def optimize_retrieval_query(issue_tags: list[str]) -> str:
    """Synthesize a RAG query from deterministic issue tags (plan §5.5/§6).

    Stub: the real tag vocabulary (``highlights_clipped``, ``low_contrast``,
    ...) is produced by ``histogram.py``'s rule layer, which is W6's Phase 3
    work. This just joins whatever tags it's given so the retrieval call
    site can be written today.
    """
    return " ".join(issue_tags)


def build_optimize_messages(
    *,
    histogram_summary: str,
    exif_summary: str,
    edit_state_block: str | None = None,
    module_library_block: str | None = None,
) -> list[dict[str, Any]]:
    """Minimal message assembly for ``/optimize``.

    W6 owns the full prompt content (deterministic issue tags, structured
    settings contract details); this exists so the seam is stable and other
    code can call it without waiting on Phase 3.
    """
    parts = [histogram_summary, exif_summary]
    if edit_state_block:
        parts.append(edit_state_block)
    if module_library_block:
        parts.append(module_library_block)
    return [
        {"role": "system", "content": optimize_system_prompt()},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


# ---------------------------------------------------------------------------
# Vision (plan §5.5, third bullet) -- Phase 4, owned by W6.
# ---------------------------------------------------------------------------

VISION_DESCRIBE_SYSTEM_PROMPT = (
    "You are looking at a downscaled preview of a photograph inside "
    "darktable. Describe the subject, lighting, color casts, and any "
    "composition issues you observe in plain language. Do not recommend "
    "modules or settings yet -- that happens in a second pass."
)

VISION_RECOMMEND_SYSTEM_PROMPT = (
    "Given your own description of the image and the provided MODULE "
    "LIBRARY excerpts, map each observation to concrete module suggestions. "
    "Only reference modules and controls that appear in the provided "
    "excerpts."
)


def vision_describe_system_prompt() -> str:
    return VISION_DESCRIBE_SYSTEM_PROMPT


def vision_recommend_system_prompt() -> str:
    return VISION_RECOMMEND_SYSTEM_PROMPT
