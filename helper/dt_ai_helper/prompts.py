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
    "recommend module settings. The histogram statistics are computed from "
    "a display-referred sRGB preview export, not the raw scene-referred "
    "sensor data -- treat them as directional approximations. A "
    "deterministic rule layer has already flagged a set of ISSUE TAGS "
    "(e.g. highlights_clipped, low_contrast, high_iso_noise); ground your "
    "assessment in those tags and the raw numbers, and use the MODULE "
    "LIBRARY excerpts retrieved for those tags to name real modules and "
    "sliders. Respond with strict JSON only, matching exactly this shape: "
    '{"assessment": str, "recommendations": [{"module": str, "why": str, '
    '"settings": [{"control": str, "value": str}], "priority": int}]}. '
    "\"module\" must be a module's internal op name (e.g. \"filmicrgb\", "
    '"exposure", "denoiseprofile") as it appears in the MODULE LIBRARY '
    'excerpts, not its display name. "priority" is an integer where 1 is '
    "the most important recommendation to apply first. Only reference "
    "modules and controls that appear in the provided MODULE LIBRARY "
    "excerpts. Do not include any text outside the JSON object."
)


def optimize_system_prompt() -> str:
    return OPTIMIZE_SYSTEM_PROMPT


#: Issue tag -> extra retrieval terms, so the synthesized query reaches the
#: right module-library files even when the tag's own wording doesn't
#: literally appear in the corpus (plan §5.5: "retrieval query synthesized
#: from detected issue tags"). Falls through ``rag.py``'s own synonym map
#: too, so this only needs to cover gaps that map isn't aware of.
_ISSUE_TAG_QUERY_TERMS: dict[str, str] = {
    "underexposed": "underexposed too dark exposure brightness",
    "overexposed": "overexposed too bright exposure highlights",
    "highlights_clipped": "highlights clipped blown out reconstruction filmic rolloff",
    "shadows_clipped": "shadows clipped crushed blacks lift shadows tone equalizer",
    "low_contrast": "low contrast flat filmic contrast curve",
    "flat_midtones": "flat midtones contrast local contrast clarity",
    "color_cast_red": "color cast red white balance temperature calibration",
    "color_cast_blue": "color cast blue white balance temperature calibration",
    "color_cast_cyan": "color cast cyan white balance temperature calibration",
    "color_cast_yellow": "color cast yellow white balance temperature calibration",
    "low_saturation": "low saturation dull colors vibrance saturation",
    "high_iso_noise": "high iso noise denoise profiled noise reduction",
    "no_denoise_enabled": "denoise profiled noise reduction",
    "no_sharpening_enabled": "sharpen sharpening diffuse local contrast",
    "long_exposure_hot_pixels_check": "hot pixels long exposure noise",
    "ultra_wide_lens_correction_check": "lens correction distortion ultra wide angle",
}


def optimize_retrieval_query(issue_tags: list[str]) -> str:
    """Synthesize a RAG query from deterministic issue tags (plan §5.5/§6).

    Each tag expands to a short phrase of the terms a photographer/the RAG
    corpus would actually use (e.g. ``highlights_clipped`` ->
    "highlights clipped blown out reconstruction filmic rolloff"), rather
    than the raw underscored tag string, so ``rag.get_retriever()`` has
    real words to match against. Unrecognized tags fall back to their
    underscore-stripped form so a new rule always contributes *something*
    to the query instead of silently vanishing.
    """
    terms: list[str] = []
    for tag in issue_tags:
        terms.append(_ISSUE_TAG_QUERY_TERMS.get(tag, tag.replace("_", " ")))
    return " ".join(terms)


def build_optimize_messages(
    *,
    histogram_summary: str,
    exif_summary: str,
    issue_tags: list[str] | None = None,
    edit_state_block: str | None = None,
    module_library_block: str | None = None,
) -> list[dict[str, Any]]:
    """Assemble the full ``messages`` list for one ``/optimize`` call.

    Order: system prompt, then a user message containing (in order) the
    histogram summary, the EXIF summary, an ``ISSUE TAGS`` line (when any
    were detected), the current edit state block, and the retrieved
    MODULE LIBRARY excerpts. ``issue_tags`` here is purely for display in
    the prompt -- the caller (api.py) is expected to have already used
    :func:`optimize_retrieval_query` on the same tags to build
    ``module_library_block``.
    """
    parts = [histogram_summary, exif_summary]
    if issue_tags:
        parts.append("ISSUE TAGS\n" + ", ".join(issue_tags))
    if edit_state_block:
        parts.append(edit_state_block)
    if module_library_block:
        parts.append(module_library_block)
    return [
        {"role": "system", "content": optimize_system_prompt()},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def render_recommendation_text(recommendation: dict[str, Any]) -> str:
    """Render a strict-JSON optimize recommendation as readable transcript text.

    Plan §5.5: the structured JSON is "rendered as readable text for the
    transcript and kept structured for ``/style``" -- this is that
    rendering. Recommendations are shown in ascending ``priority`` order
    (missing/unparseable priority sorts last, stable otherwise).
    """
    assessment = recommendation.get("assessment", "").strip()
    recs = recommendation.get("recommendations", []) or []

    def _priority_key(rec: dict[str, Any]) -> tuple[int, int]:
        try:
            return (int(rec.get("priority", 999)), 0)
        except (TypeError, ValueError):
            return (999, 0)

    ordered = sorted(enumerate(recs), key=lambda pair: (*_priority_key(pair[1]), pair[0]))

    lines: list[str] = []
    if assessment:
        lines.append(assessment)
        lines.append("")

    for _, rec in ordered:
        module = rec.get("module", "?")
        why = rec.get("why", "").strip()
        priority = rec.get("priority")
        header = f"{module}" if priority is None else f"{module} (priority {priority})"
        lines.append(f"- {header}")
        if why:
            lines.append(f"  why: {why}")
        for setting in rec.get("settings", []) or []:
            control = setting.get("control", "?")
            value = setting.get("value", "?")
            lines.append(f"  * {control} -> {value}")

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Vision (plan §5.5, third bullet) -- Phase 4, owned by W6.
# ---------------------------------------------------------------------------

VISION_DESCRIBE_SYSTEM_PROMPT = (
    "You are looking at a downscaled preview of a photograph inside "
    "darktable. Describe the subject, the lighting and its direction, any "
    "color casts, the overall tonal range, and any composition issues you "
    "observe, in plain language a photographer would use (e.g. "
    "'backlit portrait, warm color cast, blown-out sky, subject's face is "
    "a stop underexposed relative to the background'). Do not recommend "
    "darktable modules or settings yet -- that happens in a second pass "
    "once your description has been used to look up the relevant modules. "
    "If the user asked a specific question below, address it as part of "
    "your description."
)

VISION_RECOMMEND_SYSTEM_PROMPT = (
    "You previously described a photograph; that description follows as "
    "IMAGE DESCRIPTION below. Given that description and the provided "
    "MODULE LIBRARY excerpts (retrieved for the issues you named), map "
    "each observation to concrete module suggestions: which module, which "
    "section/slider, and a plausible starting value or direction. Only "
    "reference modules and controls that appear in the provided excerpts "
    "-- never invent a module or slider name that isn't in that context. "
    "Give steps as: module name -> section -> slider -> suggested "
    "value/range. If nothing in the excerpts addresses an observation, say "
    "so rather than guessing."
)


def vision_describe_system_prompt() -> str:
    return VISION_DESCRIBE_SYSTEM_PROMPT


def vision_recommend_system_prompt() -> str:
    return VISION_RECOMMEND_SYSTEM_PROMPT


def build_vision_describe_messages(
    *,
    user_message: str | None = None,
    edit_state_block: str | None = None,
) -> list[dict[str, Any]]:
    """Text portion of pass 1's user message (plan §5.5's "describe" pass).

    The vision content part (image + this text) is attached by the caller
    via ``llm.build_vision_content``, which also enforces the
    localhost-or-consent privacy guard -- this function only builds the
    text, so it can be unit-tested without any image bytes or guard logic.
    """
    parts: list[str] = []
    if user_message:
        parts.append(user_message)
    else:
        parts.append("Describe this image.")
    if edit_state_block:
        parts.append(edit_state_block)
    return [
        {"role": "system", "content": vision_describe_system_prompt()},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def build_vision_recommend_messages(
    *,
    description: str,
    module_library_block: str | None = None,
) -> list[dict[str, Any]]:
    """Text-only pass 2 (plan §5.5's "recommend" pass) -- no image attached.

    Retrieval for this pass targets whatever issues pass 1's own
    description named (the caller runs ``rag`` against ``description``
    before calling this), "keeps retrieval relevant" per plan §5.5.
    """
    parts = [f"IMAGE DESCRIPTION\n\n{description}"]
    if module_library_block:
        parts.append(module_library_block)
    return [
        {"role": "system", "content": vision_recommend_system_prompt()},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
