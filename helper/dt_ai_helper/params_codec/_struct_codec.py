"""Shared helper for struct-based darktable IOP params codecs.

darktable's XMP `darktable:params` (and `darktable:blendop_params`) blobs are
raw memory dumps of the module's C ``dt_iop_<op>_params_t`` struct, taken
verbatim from the process's address space and base64/hex-encoded (see
``documentation/agent-insights/005-xmp-params-encoding.md``). Every field in
every struct covered by this package is 4 bytes wide on all platforms
darktable targets:

- ``float`` -> 4 bytes
- ``int`` / C ``enum`` (introspection enums are backed by ``int``) -> 4 bytes
- ``gboolean`` (glib typedef for ``int``) -> 4 bytes

Because every field is 4-byte and the structs contain no 8-byte members
(``double``, pointers) ahead of trailing scalar fields, there is no compiler
padding to account for in any of the Tier-1 layouts: the struct's on-disk
layout is exactly the field list in declaration order. If a future op needs
mixed-width fields, this helper will need padding-aware layout support -
don't assume it just works.

Each op module (``exposure.py``, ``filmicrgb.py``, ...) declares, per
``modversion``, an ordered list of ``FieldSpec`` mirroring the C struct field
order and builds a ``VersionedStructCodec`` from it. That object is the
entire implementation of the module's ``decode``/``encode``.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FieldSpec:
    """One field of a `dt_iop_..._params_t` struct.

    kind:
      'f' -> float32
      'i' -> int32
      'b' -> gboolean stored as int32, decoded to a Python bool

    shape: for array fields (e.g. ``float a[3]`` or ``float x[6][7]``), the
    C array dimensions in declaration order. Empty tuple for scalars.

    enum: optional {int_value: label} map. When present, decode returns the
    label (falling back to the raw int for unknown values so an unexpected
    value never raises), and encode accepts either the label or the int.
    """

    name: str
    kind: str
    shape: tuple[int, ...] = ()
    enum: dict[int, str] | None = None

    @property
    def count(self) -> int:
        n = 1
        for d in self.shape:
            n *= d
        return n

    @property
    def struct_code(self) -> str:
        code = "f" if self.kind == "f" else "i"
        return code * self.count

    def decode_scalar(self, raw: float | int) -> Any:
        if self.kind == "b":
            return bool(raw)
        if self.enum is not None:
            return self.enum.get(int(raw), int(raw))
        return raw

    def encode_scalar(self, value: Any) -> float | int:
        if self.kind == "b":
            return 1 if value else 0
        if self.enum is not None:
            if isinstance(value, str):
                for k, v in self.enum.items():
                    if v == value:
                        return k
                raise ValueError(f"unknown enum label {value!r} for field {self.name!r}")
            return int(value)
        if self.kind == "i":
            return int(value)
        return float(value)


def _reshape(flat: tuple[Any, ...], shape: tuple[int, ...]) -> Any:
    if not shape:
        return flat[0]
    if len(shape) == 1:
        return list(flat)
    head, *rest = shape
    sub_size = 1
    for d in rest:
        sub_size *= d
    return [_reshape(flat[i * sub_size : (i + 1) * sub_size], tuple(rest)) for i in range(head)]


def _flatten(value: Any, shape: tuple[int, ...]) -> list[Any]:
    if not shape:
        return [value]
    if len(shape) == 1:
        values = list(value)
        if len(values) != shape[0]:
            raise ValueError(f"expected {shape[0]} elements, got {len(values)}")
        return values
    out: list[Any] = []
    for sub in value:
        out.extend(_flatten(sub, tuple(shape[1:])))
    return out


class VersionedStructCodec:
    """Decode/encode for one darktable op, keyed by ``modversion``."""

    def __init__(self, op: str, versions: dict[int, list[FieldSpec]]):
        self.op = op
        self._versions = versions
        self._structs = {
            version: struct.Struct("<" + "".join(f.struct_code for f in fields))
            for version, fields in versions.items()
        }

    def supported_versions(self) -> list[int]:
        return sorted(self._versions)

    def decode(self, modversion: int, raw: bytes) -> dict[str, Any] | None:
        fields = self._versions.get(modversion)
        if fields is None:
            return None
        st = self._structs[modversion]
        if len(raw) != st.size:
            # Wrong size for this modversion (corrupt data, or a modversion
            # we think we support but whose layout actually differs) -
            # degrade to "unknown" rather than raising or misdecoding.
            return None
        values = st.unpack(raw)
        out: dict[str, Any] = {}
        idx = 0
        for f in fields:
            chunk = values[idx : idx + f.count]
            idx += f.count
            if f.shape:
                out[f.name] = _reshape(chunk, f.shape)
            else:
                out[f.name] = f.decode_scalar(chunk[0])
        return out

    def encode(self, modversion: int, values: dict[str, Any]) -> bytes:
        fields = self._versions.get(modversion)
        if fields is None:
            raise ValueError(f"{self.op}: unsupported modversion {modversion} for encode")
        st = self._structs[modversion]
        flat: list[Any] = []
        for f in fields:
            if f.name not in values:
                raise ValueError(f"{self.op}: missing field {f.name!r} for encode")
            v = values[f.name]
            if f.shape:
                flat.extend(_flatten(v, f.shape))
            else:
                flat.append(f.encode_scalar(v))
        return st.pack(*flat)
