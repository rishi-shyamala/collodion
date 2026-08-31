"""Tests for helper/dt_ai_helper/params_codec/*.

Covers: decode(encode(values)) round-trips for every Tier-1 op/modversion,
byte-exact encode() output for a hand-computed struct, and the "unknown
modversion degrades to None, never raises" contract from the registry.
"""

from __future__ import annotations

import importlib.util
import struct
from pathlib import Path
from typing import Any

import pytest

from dt_ai_helper.params_codec import decode_params, encode_params, get_codec, known_ops

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_make_fixtures():
    spec = importlib.util.spec_from_file_location(
        "make_fixtures", FIXTURES_DIR / "make_fixtures.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


make_fixtures = _load_make_fixtures()


def assert_close(actual: Any, expected: Any, path: str = "$") -> None:
    """Recursively compare decoded values against expected values, treating
    floats with `pytest.approx` (params round-trip through 32-bit floats,
    so e.g. 18.45 decodes back as 18.450000762939453 - exactly right, just
    not bit-identical to the float64 literal)."""
    if isinstance(expected, float):
        assert actual == pytest.approx(expected, rel=1e-5, abs=1e-6), path
    elif isinstance(expected, dict):
        assert isinstance(actual, dict), path
        assert actual.keys() == expected.keys(), path
        for k in expected:
            assert_close(actual[k], expected[k], f"{path}.{k}")
    elif isinstance(expected, list):
        assert isinstance(actual, list), path
        assert len(actual) == len(expected), path
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            assert_close(a, e, f"{path}[{i}]")
    else:
        assert actual == expected, path


_FIXTURE_IDS = [m[0] for m in make_fixtures.FIXTURE_MODULES]


@pytest.mark.parametrize("op,modversion,values", make_fixtures.FIXTURE_MODULES, ids=_FIXTURE_IDS)
def test_decode_encode_round_trip(op: str, modversion: int, values: dict) -> None:
    raw = encode_params(op, modversion, values)
    decoded = decode_params(op, modversion, raw)
    assert decoded is not None
    assert_close(decoded, values)


@pytest.mark.parametrize("op,modversion,values", make_fixtures.FIXTURE_MODULES, ids=_FIXTURE_IDS)
def test_encode_is_deterministic_and_byte_exact(op: str, modversion: int, values: dict) -> None:
    raw1 = encode_params(op, modversion, values)
    raw2 = encode_params(op, modversion, values)
    assert raw1 == raw2
    # re-encoding the decode of an encode must reproduce the same bytes
    # (byte-exact round trip, not just value-exact).
    decoded = decode_params(op, modversion, raw1)
    raw3 = encode_params(op, modversion, decoded)
    assert raw1 == raw3


def test_exposure_known_layout_byte_exact() -> None:
    """Sanity check the exposure codec against a hand-packed struct,
    independent of encode_params - guards against both encode() and
    decode() being wrong in the same way."""
    raw = struct.pack("<iffffi", 0, -0.02, 0.65, 50.0, -4.0, 0)
    decoded = decode_params("exposure", 6, raw)
    assert decoded == {
        "mode": "manual",
        "black": pytest.approx(-0.02, abs=1e-6),
        "exposure": pytest.approx(0.65, abs=1e-6),
        "deflicker_percentile": 50.0,
        "deflicker_target_level": -4.0,
        "compensate_exposure_bias": False,
    }
    assert encode_params("exposure", 6, decoded) == raw


def test_unknown_op_decodes_to_none() -> None:
    assert decode_params("not_a_real_module", 1, b"\x00" * 16) is None


def test_unsupported_modversion_decodes_to_none() -> None:
    assert decode_params("exposure", 999, b"\x00" * 24) is None


def test_wrong_length_blob_decodes_to_none() -> None:
    # exposure v6 expects 24 bytes; feed it garbage-length data.
    assert decode_params("exposure", 6, b"\x00" * 7) is None


def test_unknown_op_encode_raises() -> None:
    with pytest.raises(ValueError):
        encode_params("not_a_real_module", 1, {})


def test_unsupported_modversion_encode_raises() -> None:
    with pytest.raises(ValueError):
        encode_params("exposure", 999, {"mode": "manual"})


def test_registry_known_ops_matches_tier1_list() -> None:
    tier1 = {
        "exposure",
        "filmicrgb",
        "sigmoid",
        "colorbalancergb",
        "toneequal",
        "highlights",
        "temperature",
        "sharpen",
        "denoiseprofile",
        "crop",
    }
    assert set(known_ops()) == tier1


def test_get_codec_returns_none_for_unknown_op() -> None:
    assert get_codec("does_not_exist") is None


def test_every_registered_codec_reachable_via_get_codec() -> None:
    for op in known_ops():
        assert get_codec(op) is not None
