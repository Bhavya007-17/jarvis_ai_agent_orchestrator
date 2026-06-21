import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import gen_personas as gp  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SHIPPED_8 = {"architect", "skeptic", "pragmatist", "coder",
             "researcher", "creative", "fact-checker", "planner"}
# Representative ECC ids that must appear (from FEATURES.md persona table).
ECC_SAMPLE = {"code-reviewer", "security-reviewer", "performance-optimizer",
              "code-architect", "tdd-guide", "explorer"}


def test_baked_catalog_covers_shipped_and_ecc():
    ids = {p["id"] for p in gp.PERSONA_SOURCES}
    assert SHIPPED_8 <= ids
    assert ECC_SAMPLE <= ids


def test_every_persona_has_required_fields():
    for p in gp.PERSONA_SOURCES:
        for field in ("id", "persona", "category", "defaultModelKey", "lens", "blurb"):
            assert p.get(field), f"{p.get('id')} missing {field}"
        assert p["defaultModelKey"] in {"reasoning", "code", "general"}


def test_build_catalog_assigns_accents():
    for p in gp.build_catalog():
        assert p["accent"].startswith("#")


def test_render_personas_json_is_the_id_set():
    catalog = gp.build_catalog()
    ids = set(json.loads(gp.render_personas_json(catalog)))
    assert SHIPPED_8 <= ids


def test_render_agents_js_has_exports():
    js = gp.render_agents_js(gp.build_catalog())
    assert "export const AGENT_CATALOG" in js
    assert "export function agentById" in js
    assert "export function resolveModel" in js
    assert "export const CATEGORIES" in js


def test_generator_is_idempotent():
    a = gp.render_agents_js(gp.build_catalog())
    b = gp.render_agents_js(gp.build_catalog())
    assert a == b


def test_committed_artifacts_match_generator():
    """The committed files must equal a fresh render (re-run the generator if this fails)."""
    catalog = gp.build_catalog()
    assert (ROOT / "web/src/lib/agents.js").read_text(encoding="utf-8") == gp.render_agents_js(catalog)
    assert json.loads((ROOT / "scripts/personas.json").read_text(encoding="utf-8")) == json.loads(gp.render_personas_json(catalog))
