from pathlib import Path


HTML = Path(__file__).parent / "ui" / "index.html"
README = Path(__file__).parent / "README.md"


def test_peer_settings_are_submitted_with_main_config_form():
    text = HTML.read_text(encoding="utf-8")
    start = text.index('<form id="cfg"')
    end = text.index("</form>", start)
    for field in ("peer_enabled", "peer_supabase_url", "peer_supabase_key", "peer_room", "peer_max_turns",
                  "peer_idle_enabled", "peer_idle_after_minutes",
                  "peer_idle_interval_minutes", "peer_idle_daily_limit"):
        pos = text.index(f'name="{field}"')
        control_start = text.rfind("<input", 0, pos)
        control_end = text.index(">", pos)
        inside_form = start < pos < end
        associated_with_form = 'form="cfg"' in text[control_start:control_end]
        assert inside_form or associated_with_form, field


def test_peer_key_has_visibility_and_copy_controls():
    text = HTML.read_text(encoding="utf-8")
    assert 'id="peer-supabase-key"' in text
    assert 'onclick="togglePeerKey()"' in text
    assert 'onclick="copyPeerKey()"' in text
    assert '&#x1F441;' in text
    assert '&#x1F4CB;' in text
    assert "async function copyPeerKey" in (Path(__file__).parent / "ui" / "app.js").read_text(encoding="utf-8")


def test_peer_status_explains_automatic_idle_role():
    text = HTML.read_text(encoding="utf-8")
    assert 'id="peer-idle-status"' in text
    app = (Path(__file__).parent / "ui" / "app.js").read_text(encoding="utf-8")
    assert "idle_next_seconds" in app


def test_dynamic_range_controls_exist_for_traits_and_llm_sampling():
    app = (Path(__file__).parent / "ui" / "app.js").read_text(encoding="utf-8")
    assert "dynamic_enabled" in app
    assert "_min" in app and "_max" in app
    assert "llm_temperature" in app
    assert "llm_top_p" in app


def test_dynamic_settings_are_exposed_in_bootstrap_defaults():
    import muchio_llm as m
    cfg = m._bootstrap_data()["cfg"]
    assert "dynamic_enabled" in cfg
    assert "dynamic_period_minutes" in cfg
    for key, *_ in m.TRAITS:
        assert f"{key}_min" in cfg
        assert f"{key}_max" in cfg
    assert "llm_temperature_min" in cfg
    assert "llm_temperature_max" in cfg
    assert "llm_top_p_min" in cfg
    assert "llm_top_p_max" in cfg


def test_monologue_controls_are_submitted_with_main_config_form():
    text = HTML.read_text(encoding="utf-8")
    start = text.index('<form id="cfg"')
    end = text.index("</form>", start)
    for field in ("monologue_max_continuations", "monologue_topic_cooldown",
                  "monologue_connector_mode", "monologue_connectors",
                  "monologue_avoid_words"):
        pos = text.index(f'name="{field}"')
        control_start = text.rfind("<", start, pos)
        control_end = text.index(">", pos)
        inside_form = start < pos < end
        associated_with_form = 'form="cfg"' in text[control_start:control_end]
        assert inside_form or associated_with_form, field


def test_monologue_controls_are_bound_to_bootstrap_and_save_ui():
    app = (Path(__file__).parent / "ui" / "app.js").read_text(encoding="utf-8")
    for field in ("monologue_max_continuations", "monologue_topic_cooldown",
                  "monologue_connector_mode", "monologue_connectors",
                  "monologue_avoid_words"):
        assert field in app, field


def test_unitypackage_descriptions_cover_both_packages_and_repair_mapping():
    html = HTML.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")
    for text in (html, readme):
        assert "MuchioKanjiMod.unitypackage" in text
        assert "MaterialCurveBindingRepairer-20260804.unitypackage" in text
        assert "material._Char035" in text
        assert "material._Char35" in text
    assert "VRCFury" in html
    assert "Muchio/KATアセットに依存しません" in html


if __name__ == "__main__":
    test_peer_settings_are_submitted_with_main_config_form()
    test_peer_key_has_visibility_and_copy_controls()
    test_dynamic_range_controls_exist_for_traits_and_llm_sampling()
    test_dynamic_settings_are_exposed_in_bootstrap_defaults()
    test_monologue_controls_are_submitted_with_main_config_form()
    test_monologue_controls_are_bound_to_bootstrap_and_save_ui()
    test_unitypackage_descriptions_cover_both_packages_and_repair_mapping()
    print("ok")
