"""Tests for helper/dt_ai_helper/styles.py.

Offline, no darktable install required (see agent-insights 007). Covers:
the default blendop params blob's size/shape, the `.dtstyle` XML shape
(`<darktable_style><info><name>/<style><plugin>...`), round-trip
validation of every emitted op via the real xmp.py decode path, the
recommendation -> codec-field translator (including unit parsing and
unrecognized-control/unknown-module reporting), and the `/style` endpoint
through FastAPI's TestClient.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from dt_ai_helper import styles, xmp
from dt_ai_helper.main import create_app
from dt_ai_helper.params_codec import decode_params, supported_versions
from fastapi.testclient import TestClient

TOKEN = "test-token-123"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def assert_close(actual: Any, expected: Any, path: str = "$") -> None:
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


# ---------------------------------------------------------------------------
# blendop defaults
# ---------------------------------------------------------------------------


def test_default_blendop_params_size_matches_struct():
    # dt_develop_blend_params_t @ release-4.6.0 (agent-insights 007).
    assert len(styles.DEFAULT_BLENDOP_PARAMS) == 420


def test_default_blendop_params_disables_blending():
    raw = styles.DEFAULT_BLENDOP_PARAMS
    mask_mode, blend_cst, blend_mode = styles._BLENDOP_STRUCT.unpack(raw)[0:3]
    assert mask_mode == 0  # DEVELOP_MASK_DISABLED
    assert blend_cst == 0  # DEVELOP_BLEND_CS_NONE
    assert blend_mode == 0x18  # DEVELOP_BLEND_NORMAL2
    opacity = styles._BLENDOP_STRUCT.unpack(raw)[4]
    assert opacity == 100.0


def test_default_blendop_params_stable_across_calls():
    assert styles._default_blendop_params_bytes() == styles.DEFAULT_BLENDOP_PARAMS


# ---------------------------------------------------------------------------
# build_style: XML shape + round-trip validation
# ---------------------------------------------------------------------------


def _module(op: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    values = dict(styles.DEFAULT_PARAMS[op])
    values.update(overrides or {})
    return {
        "op": op,
        "modversion": max(supported_versions(op)),
        "values": values,
        "enabled": True,
        "multi_name": "",
        "multi_priority": 0,
    }


def test_build_style_xml_shape_and_roundtrip():
    modules = [
        _module("exposure", {"exposure": 0.65}),
        _module("filmicrgb", {"white_point_source": 4.5}),
    ]
    result = styles.build_style("ai-assistant/test-style", modules)

    assert result["included_ops"] == ["exposure", "filmicrgb"]
    assert result["skipped_ops"] == []

    root = xmp.ET.fromstring(result["xml"])
    assert root.tag == "darktable_style"
    assert root.attrib["version"] == "1.0"

    info = root.find("info")
    assert info is not None
    assert info.find("name").text == "ai-assistant/test-style"

    style_el = root.find("style")
    plugins = style_el.findall("plugin")
    assert len(plugins) == 2

    for plugin, module in zip(plugins, modules, strict=True):
        op = module["op"]
        assert plugin.find("operation").text == op
        assert plugin.find("module").text == str(module["modversion"])
        assert plugin.find("enabled").text == "1"

        # Round-trip through the exact decode path xmp.py uses for real
        # sidecars, to prove the emitted op_params are genuinely
        # consumable, not just internally self-consistent.
        op_params_text = plugin.find("op_params").text
        raw = xmp.decode_params_blob(op_params_text)
        assert raw is not None
        decoded = decode_params(op, module["modversion"], raw)
        assert_close(decoded, module["values"])

        # blendop_params round-trips too and matches the shared default.
        blendop_text = plugin.find("blendop_params").text
        blendop_raw = xmp.decode_params_blob(blendop_text)
        assert blendop_raw == styles.DEFAULT_BLENDOP_PARAMS
        assert plugin.find("blendop_version").text == str(styles.BLENDOP_VERSION)


def test_build_style_skips_op_with_missing_field():
    modules = [
        {
            "op": "exposure",
            "modversion": 6,
            "values": {"mode": "manual", "exposure": 0.5},  # missing required fields
        }
    ]
    result = styles.build_style("broken", modules)
    assert result["included_ops"] == []
    assert len(result["skipped_ops"]) == 1
    assert result["skipped_ops"][0]["op"] == "exposure"


def test_build_style_skips_unknown_op():
    modules = [{"op": "not_a_real_op", "modversion": 1, "values": {}}]
    result = styles.build_style("broken2", modules)
    assert result["included_ops"] == []
    assert "not_a_real_op" in result["skipped_ops"][0]["reason"]


def test_build_style_empty_modules_still_valid_xml():
    result = styles.build_style("empty-style", [])
    root = xmp.ET.fromstring(result["xml"])
    assert root.find("style").findall("plugin") == []
    assert result["included_ops"] == []
    assert result["skipped_ops"] == []


# ---------------------------------------------------------------------------
# translate_recommendation
# ---------------------------------------------------------------------------


def test_translate_recommendation_maps_controls_and_parses_units():
    recommendation = {
        "recommendations": [
            {
                "module": "exposure",
                "settings": [{"control": "Exposure", "value": "+0.65 EV"}],
            },
            {
                "module": "filmicrgb",
                "settings": [
                    {"control": "White relative exposure", "value": "4.5"},
                    {"control": "Latitude", "value": "25%"},
                ],
            },
        ]
    }
    modules, skipped = styles.translate_recommendation(recommendation)
    assert skipped == []
    by_op = {m["op"]: m for m in modules}
    assert by_op["exposure"]["values"]["exposure"] == pytest.approx(0.65)
    assert by_op["filmicrgb"]["values"]["white_point_source"] == pytest.approx(4.5)
    assert by_op["filmicrgb"]["values"]["latitude"] == pytest.approx(25.0)
    # Unset fields fall back to the factory defaults.
    assert by_op["exposure"]["values"]["black"] == 0.0


def test_translate_recommendation_negative_and_plain_values():
    recommendation = {
        "recommendations": [
            {
                "module": "toneequal",
                "settings": [
                    {"control": "shadows", "value": "-1.2 EV"},
                    {"control": "highlights", "value": "0.8"},
                ],
            }
        ]
    }
    modules, skipped = styles.translate_recommendation(recommendation)
    assert skipped == []
    values = modules[0]["values"]
    assert values["shadows"] == pytest.approx(-1.2)
    assert values["highlights"] == pytest.approx(0.8)


def test_translate_recommendation_bool_field():
    recommendation = {
        "recommendations": [
            {
                "module": "filmicrgb",
                "settings": [{"control": "highlight reconstruction", "value": "on"}],
            }
        ]
    }
    modules, skipped = styles.translate_recommendation(recommendation)
    assert skipped == []
    assert modules[0]["values"]["enable_highlight_reconstruction"] is True


def test_translate_recommendation_reports_unrecognized_control():
    recommendation = {
        "recommendations": [
            {
                "module": "exposure",
                "settings": [{"control": "some made up slider", "value": "1"}],
            }
        ]
    }
    modules, skipped = styles.translate_recommendation(recommendation)
    assert len(modules) == 1  # module still included with defaults
    assert len(skipped) == 1
    assert skipped[0]["module"] == "exposure"
    assert skipped[0]["control"] == "some made up slider"
    assert "unrecognized" in skipped[0]["reason"]


def test_translate_recommendation_reports_unparseable_value():
    recommendation = {
        "recommendations": [
            {
                "module": "exposure",
                "settings": [{"control": "exposure", "value": "not a number"}],
            }
        ]
    }
    modules, skipped = styles.translate_recommendation(recommendation)
    assert modules[0]["values"]["exposure"] == 0.0  # default retained
    assert skipped[0]["control"] == "exposure"


def test_translate_recommendation_unknown_module_skipped():
    recommendation = {"recommendations": [{"module": "totally_unknown", "settings": []}]}
    modules, skipped = styles.translate_recommendation(recommendation)
    assert modules == []
    assert skipped[0]["module"] == "totally_unknown"
    assert "no params codec" in skipped[0]["reason"]


def test_translate_recommendation_module_without_defaults_skipped():
    # denoiseprofile has a codec but no static defaults (agent-insights 007).
    recommendation = {
        "recommendations": [
            {"module": "denoiseprofile", "settings": [{"control": "strength", "value": "1.0"}]}
        ]
    }
    modules, skipped = styles.translate_recommendation(recommendation)
    assert modules == []
    assert skipped[0]["module"] == "denoiseprofile"
    assert "no known default parameters" in skipped[0]["reason"]


# ---------------------------------------------------------------------------
# write_style_file
# ---------------------------------------------------------------------------


def test_write_style_file_slugifies_name(tmp_path: Path):
    path = styles.write_style_file("<xml/>", "ai-assistant/my style! v1", tmp_path)
    assert path.parent == tmp_path
    assert path.name == "ai-assistant_my_style_v1.dtstyle"
    assert path.read_text() == "<xml/>"


# ---------------------------------------------------------------------------
# /style endpoint
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(tmp_path: Path):
    app = create_app(TOKEN)
    app.state.style_dir = tmp_path
    with TestClient(app) as c:
        yield c


def test_style_endpoint_full_flow(client: TestClient, tmp_path: Path):
    body = {
        "recommendation": {
            "recommendations": [
                {
                    "module": "exposure",
                    "settings": [{"control": "exposure", "value": "+0.65 EV"}],
                },
                {
                    "module": "denoiseprofile",
                    "settings": [{"control": "strength", "value": "1.5"}],
                },
            ]
        },
        "name": "ai-assistant/optimize-1",
    }
    resp = client.post("/style", json=body, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()

    assert data["included_ops"] == ["exposure"]
    assert any(s["module"] == "denoiseprofile" for s in data["skipped_ops"])
    assert len(data["manual_steps"]) == len(data["skipped_ops"])
    assert any("denoiseprofile" in step for step in data["manual_steps"])

    style_path = Path(data["file"])
    assert style_path.exists()
    assert style_path.parent == tmp_path
    xml_text = style_path.read_text()
    assert "<darktable_style" in xml_text
    assert "<operation>exposure</operation>" in xml_text


def test_style_endpoint_requires_auth(client: TestClient):
    resp = client.post("/style", json={"recommendation": {"recommendations": []}})
    assert resp.status_code == 401


def test_style_endpoint_default_name(client: TestClient):
    body = {"recommendation": {"recommendations": []}}
    resp = client.post("/style", json=body, headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()
    assert data["included_ops"] == []
    assert Path(data["file"]).exists()
