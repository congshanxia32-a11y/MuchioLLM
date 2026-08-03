from pathlib import Path


HTML = Path(__file__).parent / "ui" / "index.html"
README = Path(__file__).parent / "README.md"


def test_peer_settings_are_submitted_with_main_config_form():
    text = HTML.read_text(encoding="utf-8")
    start = text.index('<form id="cfg"')
    end = text.index("</form>", start)
    for field in ("peer_enabled", "peer_supabase_url", "peer_supabase_key", "peer_room", "peer_max_turns",
                  "peer_idle_enabled", "peer_idle_initiator", "peer_idle_after_minutes",
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
    test_unitypackage_descriptions_cover_both_packages_and_repair_mapping()
    print("ok")
