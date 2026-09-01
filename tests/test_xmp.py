"""Tests for helper/dt_ai_helper/xmp.py.

Covers: the two fixtures in tests/fixtures/ - a hand-written XMP exercising
multi-instance collapse, history_end truncation, and plain-hex params, and
a codec-generated XMP covering every Tier-1 module (mixing plain-hex and
gz-compressed params depending on struct size, exactly as darktable's
default "only large entries" compress_xmp_tags preference would) - plus
unit tests for the gz/hex decoding helper and the unknown-decoder
degrade-to-null contract.
"""

from __future__ import annotations

import base64
import zlib
from pathlib import Path
from typing import Any

import pytest
import yaml

from dt_ai_helper import xmp

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def assert_close(actual: Any, expected: Any, path: str = "$") -> None:
    if isinstance(expected, float):
        assert actual == pytest.approx(expected, rel=1e-5, abs=1e-6), path
    elif isinstance(expected, dict):
        assert isinstance(actual, dict), path
        for k in expected:
            assert k in actual, f"{path}.{k} missing"
            assert_close(actual[k], expected[k], f"{path}.{k}")
    elif isinstance(expected, list):
        assert isinstance(actual, list), path
        assert len(actual) == len(expected), path
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            assert_close(a, e, f"{path}[{i}]")
    else:
        assert actual == expected, path


def _load_expected(name: str) -> dict:
    with (FIXTURES_DIR / name).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _assert_matches_expected(result: dict, expected: dict) -> None:
    assert result["history_source"] == expected["history_source"]
    assert result["iop_order"] == expected["iop_order"]
    assert len(result["enabled_modules"]) == len(expected["enabled_modules"])
    for actual_mod, expected_mod in zip(
        result["enabled_modules"], expected["enabled_modules"], strict=True
    ):
        assert_close(actual_mod, expected_mod)


def test_handwritten_multi_instance_fixture() -> None:
    result = xmp.read_edit_state(FIXTURES_DIR / "handwritten_multi_instance.xmp")
    expected = _load_expected("handwritten_multi_instance.yaml")
    _assert_matches_expected(result, expected)

    # explicitly re-assert the properties the fixture exists to exercise
    ops_seen = [(m["op"], m["multi_priority"]) for m in result["enabled_modules"]]
    assert ops_seen == [("exposure", 0), ("exposure", 1)]
    assert result["enabled_modules"][0]["params_decoded"]["exposure"] == pytest.approx(1.25)
    assert result["enabled_modules"][1]["multi_name"] == "vignette control"
    # crop (num=3) is beyond history_end=3 and must not appear anywhere
    assert all(m["op"] != "crop" for m in result["enabled_modules"])


def test_generated_tier1_fixture() -> None:
    result = xmp.read_edit_state(FIXTURES_DIR / "generated_tier1.xmp")
    expected = _load_expected("generated_tier1.yaml")
    _assert_matches_expected(result, expected)
    # every Tier-1 op should have decoded (none of them should degrade to null)
    for mod in result["enabled_modules"]:
        assert mod["params_decoded"] is not None, mod["op"]


def test_generated_fixture_mixes_gz_and_hex_encoding() -> None:
    """Sanity-check that the generator actually produced both encodings
    (struct size > 100 bytes -> gz, else plain hex), so this fixture is
    exercising both code paths in decode_params_blob."""
    raw_xml = (FIXTURES_DIR / "generated_tier1.xmp").read_text(encoding="utf-8")
    assert 'darktable:params="gz' in raw_xml
    # exposure (24 bytes) must be small enough to stay plain hex
    assert 'darktable:operation="exposure"' in raw_xml


def test_decode_params_blob_gz_round_trip() -> None:
    raw = b"\x01\x02\x03\x04" * 40  # 160 bytes, well above the 100-byte threshold
    compressed = zlib.compress(raw)
    factor = min(len(raw) // len(compressed) + 1, 99)
    text = f"gz{factor:02d}" + base64.b64encode(compressed).decode("ascii")
    assert xmp.decode_params_blob(text) == raw


def test_decode_params_blob_plain_hex() -> None:
    raw = bytes(range(16))
    assert xmp.decode_params_blob(raw.hex()) == raw


def test_decode_params_blob_none_and_malformed() -> None:
    assert xmp.decode_params_blob(None) is None
    assert xmp.decode_params_blob("") is None
    assert xmp.decode_params_blob("not hex and not gz!!") is None
    assert xmp.decode_params_blob("gz01not-valid-base64!!!") is None


def test_unknown_module_degrades_to_null_without_raising() -> None:
    xml_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:darktable="http://darktable.sf.net/"
    darktable:history_end="1">
   <darktable:history>
    <rdf:Seq>
     <rdf:li
      darktable:num="0"
      darktable:operation="some_future_module"
      darktable:enabled="1"
      darktable:modversion="1"
      darktable:params="deadbeef"
      darktable:multi_name=""
      darktable:multi_priority="0"/>
    </rdf:Seq>
   </darktable:history>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
"""
    result = xmp.parse_xmp_bytes(xml_bytes)
    assert len(result["enabled_modules"]) == 1
    mod = result["enabled_modules"][0]
    assert mod["op"] == "some_future_module"
    assert mod["params_decoded"] is None
    assert "note" in mod


def test_unsupported_modversion_of_known_module_degrades_to_null() -> None:
    xml_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:darktable="http://darktable.sf.net/"
    darktable:history_end="1">
   <darktable:history>
    <rdf:Seq>
     <rdf:li
      darktable:num="0"
      darktable:operation="exposure"
      darktable:enabled="1"
      darktable:modversion="2"
      darktable:params="deadbeefcafef00d"
      darktable:multi_name=""
      darktable:multi_priority="0"/>
    </rdf:Seq>
   </darktable:history>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
"""
    result = xmp.parse_xmp_bytes(xml_bytes)
    mod = result["enabled_modules"][0]
    assert mod["op"] == "exposure"
    assert mod["modversion"] == 2
    assert mod["params_decoded"] is None


def test_disabled_module_excluded() -> None:
    xml_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:darktable="http://darktable.sf.net/"
    darktable:history_end="1">
   <darktable:history>
    <rdf:Seq>
     <rdf:li
      darktable:num="0"
      darktable:operation="sharpen"
      darktable:enabled="0"
      darktable:modversion="1"
      darktable:params="000000400000003f0000003f"
      darktable:multi_name=""
      darktable:multi_priority="0"/>
    </rdf:Seq>
   </darktable:history>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
"""
    result = xmp.parse_xmp_bytes(xml_bytes)
    assert result["enabled_modules"] == []


def test_child_element_form_is_also_accepted() -> None:
    """Defensive parsing: some XMP writers/serializers render struct
    properties as child elements rather than attributes on <rdf:li>. We
    have not validated which form real darktable output uses in this
    environment (no darktable install available) - see agent-insights
    005 - so both are supported."""
    xml_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
   xmlns:darktable="http://darktable.sf.net/">
  <rdf:Description rdf:about="">
   <darktable:history_end>1</darktable:history_end>
   <darktable:history>
    <rdf:Seq>
     <rdf:li rdf:parseType="Resource">
      <darktable:num>0</darktable:num>
      <darktable:operation>sharpen</darktable:operation>
      <darktable:enabled>1</darktable:enabled>
      <darktable:modversion>1</darktable:modversion>
      <darktable:params>000000400000003f0000003f</darktable:params>
      <darktable:multi_name></darktable:multi_name>
      <darktable:multi_priority>0</darktable:multi_priority>
     </rdf:li>
    </rdf:Seq>
   </darktable:history>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
"""
    result = xmp.parse_xmp_bytes(xml_bytes)
    assert len(result["enabled_modules"]) == 1
    assert result["enabled_modules"][0]["op"] == "sharpen"
    assert result["enabled_modules"][0]["params_decoded"] is not None


def test_no_history_yields_empty_but_valid_result() -> None:
    xml_bytes = b"""<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" xmlns:darktable="http://darktable.sf.net/"/>
 </rdf:RDF>
</x:xmpmeta>
"""
    result = xmp.parse_xmp_bytes(xml_bytes)
    assert result == {"history_source": "xmp", "enabled_modules": [], "iop_order": []}


def test_invalid_xml_raises_xmp_parse_error() -> None:
    with pytest.raises(xmp.XmpParseError):
        xmp.parse_xmp_bytes(b"<not valid xml")
