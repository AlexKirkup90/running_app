from core.services.session_compiler import compile_session_for_athlete
from core.services.session_library import default_structure


def _main_set_target(compiled: dict):
    for block in compiled.get("blocks", []):
        if isinstance(block, dict) and str(block.get("phase", "")).lower() == "main_set":
            target = block.get("target") or {}
            if isinstance(target, dict):
                return target
    return {}


def test_compile_session_prefers_easy_intent_over_generic_z3_main_set():
    compiled = compile_session_for_athlete(
        structure_json=default_structure(45),
        athlete_id=1,
        session_name="Easy Run",
        template_name="Easy Run 45min",
        template_intent="easy_aerobic",
        vdot=45.0,
    )
    target = _main_set_target(compiled)
    assert target.get("intensity_code") == "E"


def test_compile_session_prefers_strides_name_over_generic_z3_main_set():
    compiled = compile_session_for_athlete(
        structure_json=default_structure(35),
        athlete_id=1,
        session_name="Strides / Neuromuscular",
        template_name="Strides / Neuromuscular",
        template_intent="strides",
        vdot=45.0,
    )
    target = _main_set_target(compiled)
    assert target.get("intensity_code") == "R"
