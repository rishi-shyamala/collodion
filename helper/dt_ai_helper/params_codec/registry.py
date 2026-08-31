"""Op name + modversion -> params codec lookup.

Consumers (xmp.py, dbfallback.py, styles.py) should go through
`decode_params`/`encode_params` rather than importing individual op
modules, so that an unknown op or unsupported modversion is always a quiet
`None` (decode) or a clear `ValueError` (encode) instead of an import
error or a `KeyError` leaking out to a caller that just wants "do we know
this module or not".
"""

from __future__ import annotations

from typing import Any, Protocol

from . import (
    colorbalancergb,
    crop,
    denoiseprofile,
    exposure,
    filmicrgb,
    highlights,
    sharpen,
    sigmoid,
    temperature,
    toneequal,
)


class _Codec(Protocol):
    OP: str
    SUPPORTED_VERSIONS: list[int]

    def decode(self, modversion: int, raw: bytes) -> dict[str, Any] | None: ...
    def encode(self, modversion: int, values: dict[str, Any]) -> bytes: ...


_MODULES: tuple[_Codec, ...] = (
    exposure,
    filmicrgb,
    sigmoid,
    colorbalancergb,
    toneequal,
    highlights,
    temperature,
    sharpen,
    denoiseprofile,
    crop,
)

_REGISTRY: dict[str, _Codec] = {m.OP: m for m in _MODULES}


def known_ops() -> list[str]:
    """Ops with at least one supported modversion codec."""
    return sorted(_REGISTRY)


def get_codec(op: str) -> _Codec | None:
    return _REGISTRY.get(op)


def supported_versions(op: str) -> list[int]:
    codec = _REGISTRY.get(op)
    return list(codec.SUPPORTED_VERSIONS) if codec is not None else []


def decode_params(op: str, modversion: int, raw: bytes) -> dict[str, Any] | None:
    """Decode a params blob for `op`/`modversion`.

    Returns `None` when the op is unknown, the modversion is unsupported,
    the blob's length doesn't match the expected struct size, or any
    unexpected error occurs while unpacking - a missing/failed decode is
    never fatal to the caller.
    """
    codec = _REGISTRY.get(op)
    if codec is None:
        return None
    try:
        return codec.decode(modversion, raw)
    except Exception:
        return None


def encode_params(op: str, modversion: int, values: dict[str, Any]) -> bytes:
    """Encode `values` back into a raw params blob for `op`/`modversion`.

    Raises `ValueError` if the op or modversion has no encoder, or if
    `values` is missing required fields - callers (styles.py) should treat
    that as "this module can't be included in the generated style", not
    crash the whole style-generation request.
    """
    codec = _REGISTRY.get(op)
    if codec is None:
        raise ValueError(f"no codec registered for op {op!r}")
    return codec.encode(modversion, values)
