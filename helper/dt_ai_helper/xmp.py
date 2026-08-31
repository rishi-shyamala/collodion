"""XMP sidecar parser for darktable history stacks.

Implements plan `darktableaiassistantplan.md` §7.1: parses the
`darktable:history` sequence out of a `.xmp` sidecar, truncates it at
`darktable:history_end`, collapses multiple history entries down to the
last one per `(operation, multi_priority)`, decodes each entry's
`darktable:params` blob via the per-op codecs in `params_codec/`, and
returns the `enabled_modules` / `iop_order` portion of `image_context`
(plan §5.2).

Encoding of `darktable:params` / `darktable:blendop_params` text values is
documented and verified against darktable's own encoder/decoder in
`documentation/agent-insights/005-xmp-params-encoding.md` - read that
before touching `decode_params_blob`.

XML shape note: real darktable sidecars encode each `darktable:history`
`rdf:li` entry's fields as XML *attributes* on the `<rdf:li>` element
(e.g. `<rdf:li darktable:operation="exposure" darktable:enabled="1" .../>`).
This parser also accepts the equivalent child-element form
(`<rdf:li><darktable:operation>exposure</darktable:operation>...</rdf:li>`)
defensively, since we have not yet validated against a real
darktable-produced XMP in this environment (no darktable install available
here - see the insights doc for the outstanding manual-validation task).
"""

from __future__ import annotations

import base64
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .params_codec import decode_params

_DT_NS = "http://darktable.sf.net/"
_RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

NAMESPACES = {
    "x": "adobe:ns:meta/",
    "rdf": _RDF_NS,
    "dc": "http://purl.org/dc/elements/1.1/",
    "xmp": "http://ns.adobe.com/xap/1.0/",
    "exif": "http://ns.adobe.com/exif/1.0/",
    "darktable": _DT_NS,
}

_DT = f"{{{_DT_NS}}}"
_RDF = f"{{{_RDF_NS}}}"


class XmpParseError(ValueError):
    """The file is not parseable as XML at all.

    A missing/malformed *darktable* history section is not an error - it
    just yields an empty `enabled_modules` list - but a file that isn't
    valid XML at all raises this so callers can distinguish "no edits" from
    "not actually a sidecar".
    """


@dataclass
class HistoryEntry:
    num: int
    operation: str
    enabled: bool
    modversion: int
    multi_name: str
    multi_priority: int
    blendop_version: int
    params_raw: str | None
    blendop_params_raw: str | None

    @property
    def key(self) -> tuple[str, int]:
        return (self.operation, self.multi_priority)


#: darktable's own compress-vs-plain-hex cutoff (`COMPRESS_THRESHOLD` in
#: `src/common/exif.cc`), compared against the *uncompressed* byte length.
#: Shared with `styles.py` (which encodes `op_params`/`blendop_params` for
#: `.dtstyle` files via the exact same `dt_exif_xmp_encode` routine XMP
#: sidecars use - see `src/common/styles.c::dt_style_encode`) and with
#: `tests/fixtures/make_fixtures.py`.
COMPRESS_THRESHOLD = 100


def encode_params_blob(raw: bytes) -> str:
    """Encode raw struct bytes the way darktable writes `darktable:params`/
    `darktable:blendop_params` (and, via the same `dt_exif_xmp_encode`
    routine, `.dtstyle` `op_params`/`blendop_params` - see
    `src/common/styles.c::dt_style_encode`): plain lowercase hex at or
    below `COMPRESS_THRESHOLD` raw bytes, `gz` + 2-digit expansion factor +
    base64(zlib-compressed bytes) above it. This is the encode twin of
    `decode_params_blob` - see agent-insights 005 for the verified
    algorithm.
    """
    if len(raw) > COMPRESS_THRESHOLD:
        compressed = zlib.compress(raw)
        factor = min(len(raw) // max(len(compressed), 1) + 1, 99)
        return f"gz{factor:02d}" + base64.b64encode(compressed).decode("ascii")
    return raw.hex()


def decode_params_blob(text: str | None) -> bytes | None:
    """Decode a `darktable:params`/`darktable:blendop_params` text value.

    Two encodings (see agent-insights 005 for the verification):
      - `gz` + a 2-digit decimal expansion-factor + base64(zlib-compressed
        bytes) - darktable's `compress()`/`uncompress()` zlib wrapper, i.e.
        Python's default (non-raw) `zlib.decompress`.
      - otherwise: plain lowercase hex of the raw struct bytes.

    Returns `None` (never raises) if `text` is empty or malformed.
    """
    if not text:
        return None
    text = text.strip()
    if text.startswith("gz"):
        try:
            compressed = base64.b64decode(text[4:])
            return zlib.decompress(compressed)
        except Exception:
            return None
    try:
        return bytes.fromhex(text)
    except ValueError:
        return None


def _get_field(li: ET.Element, name: str) -> str | None:
    tag = f"{_DT}{name}"
    if tag in li.attrib:
        return li.attrib[tag]
    child = li.find(tag)
    if child is not None:
        return child.text
    return None


def _find_seq(parent: ET.Element) -> ET.Element | None:
    for tag in ("Seq", "Bag", "Alt"):
        el = parent.find(f"{_RDF}{tag}")
        if el is not None:
            return el
    return None


def _find_attr_anywhere(root: ET.Element, name: str) -> str | None:
    """Find `darktable:<name>` either as a standalone element's text, or as
    an attribute on any `rdf:Description` (both are valid RDF/XML
    serializations of the same property)."""
    tag = f"{_DT}{name}"
    el = root.find(f".//{tag}")
    if el is not None and el.text is not None:
        return el.text
    for desc in root.iter(f"{_RDF}Description"):
        if tag in desc.attrib:
            return desc.attrib[tag]
    return None


def _read_history_entries(root: ET.Element) -> list[HistoryEntry]:
    history_el = root.find(f".//{_DT}history")
    if history_el is None:
        return []
    seq = _find_seq(history_el)
    if seq is None:
        return []

    entries: list[HistoryEntry] = []
    for i, li in enumerate(seq.findall(f"{_RDF}li")):
        num_s = _get_field(li, "num")
        operation = _get_field(li, "operation") or ""
        enabled_s = _get_field(li, "enabled")
        modversion_s = _get_field(li, "modversion")
        multi_priority_s = _get_field(li, "multi_priority")
        blendop_version_s = _get_field(li, "blendop_version")

        entries.append(
            HistoryEntry(
                num=int(num_s) if num_s is not None else i,
                operation=operation,
                enabled=enabled_s not in (None, "0", "false", "False"),
                modversion=int(modversion_s) if modversion_s is not None else 0,
                multi_name=_get_field(li, "multi_name") or "",
                multi_priority=int(multi_priority_s) if multi_priority_s is not None else 0,
                blendop_version=int(blendop_version_s) if blendop_version_s is not None else 1,
                params_raw=_get_field(li, "params"),
                blendop_params_raw=_get_field(li, "blendop_params"),
            )
        )
    return entries


def _read_history_end(root: ET.Element, default: int) -> int:
    text = _find_attr_anywhere(root, "history_end")
    if text is None:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def _read_iop_order_pairs(root: ET.Element) -> list[tuple[str, int]]:
    """Parse `darktable:iop_order_list`, a flat comma-separated
    `operation,instance,operation,instance,...` text value (see
    `dt_ioppr_serialize_text_iop_order_list` in src/common/iop_order.c)."""
    text = _find_attr_anywhere(root, "iop_order_list")
    if not text:
        return []
    parts = [p.strip() for p in text.split(",")]
    pairs: list[tuple[str, int]] = []
    for i in range(0, len(parts) - 1, 2):
        op = parts[i]
        if not op:
            continue
        try:
            instance = int(parts[i + 1])
        except ValueError:
            instance = 0
        pairs.append((op, instance))
    return pairs


def _collapse_history(entries: list[HistoryEntry], history_end: int) -> list[HistoryEntry]:
    """Truncate at `history_end` (items at/after it are undone) and keep
    only the last entry per `(operation, multi_priority)`, preserving the
    order modules were first introduced in the stack."""
    active = [e for e in entries if e.num < history_end]
    best: dict[tuple[str, int], HistoryEntry] = {}
    order: list[tuple[str, int]] = []
    for e in active:
        if e.key not in best:
            order.append(e.key)
        best[e.key] = e
    return [best[k] for k in order]


def parse_xmp_bytes(data: bytes) -> dict[str, Any]:
    """Parse raw XMP sidecar bytes into the `enabled_modules`/`iop_order`
    portion of `image_context` (plan §5.2)."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise XmpParseError(str(exc)) from exc

    entries = _read_history_entries(root)
    history_end = _read_history_end(root, default=len(entries))
    iop_order_pairs = _read_iop_order_pairs(root)
    order_index = {pair: i for i, pair in enumerate(iop_order_pairs)}

    active = _collapse_history(entries, history_end)
    active.sort(key=lambda e: order_index.get(e.key, len(order_index) + e.num))

    enabled_modules = []
    for e in active:
        if not e.enabled:
            continue
        raw_bytes = decode_params_blob(e.params_raw)
        decoded = decode_params(e.operation, e.modversion, raw_bytes) if raw_bytes else None

        module: dict[str, Any] = {
            "op": e.operation,
            "label": e.multi_name or e.operation,
            "enabled": e.enabled,
            "multi_name": e.multi_name,
            "multi_priority": e.multi_priority,
            "modversion": e.modversion,
            "params_decoded": decoded,
            "raw_params": e.params_raw,
        }
        if decoded is None and raw_bytes is not None:
            module["note"] = f"decoder not available for {e.operation} modversion {e.modversion}"
        enabled_modules.append(module)

    iop_order = [op for op, _instance in iop_order_pairs] or [e.operation for e in active]

    return {
        "history_source": "xmp",
        "enabled_modules": enabled_modules,
        "iop_order": iop_order,
    }


def read_edit_state(path: str | Path) -> dict[str, Any]:
    """Read and parse a `.xmp` sidecar file on disk.

    This is the entry point Lua-triggered helper endpoints should call to
    populate the `enabled_modules`/`iop_order` fields of `image_context`.
    """
    data = Path(path).read_bytes()
    return parse_xmp_bytes(data)
