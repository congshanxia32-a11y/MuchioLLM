import json
import tempfile
from pathlib import Path

import voiceid


def _isolated_voiceid():
    tempdir = tempfile.TemporaryDirectory()
    root = Path(tempdir.name)
    voiceid.DATA = root
    voiceid.VOICES = root / "voices.json"
    voiceid.EMBEDS = root / "embeds.jsonl"
    voiceid._profiles = {}
    voiceid._mtime = 0.0
    return tempdir


def test_stash_keeps_language_and_pages_without_trimming():
    tempdir = _isolated_voiceid()
    try:
        for i in range(4):
            voiceid.stash(float(i), [1.0, float(i) + 1.0], "ja", 0.9)
        page = voiceid.pending(limit=2)
        assert [row["ts"] for row in page["items"]] == [3.0, 2.0]
        assert page["items"][0]["lang"] == "ja"
        assert page["items"][0]["lang_conf"] == 0.9
        older = voiceid.pending(limit=2, before=page["next_before"])
        assert [row["ts"] for row in older["items"]] == [1.0, 0.0]
    finally:
        tempdir.cleanup()


def test_old_vecs_are_unknown_and_languages_have_independent_capacity():
    tempdir = _isolated_voiceid()
    try:
        voiceid.VOICES.write_text(
            json.dumps({"u": {"name": "A", "vecs": [[1.0, 0.0]]}}),
            encoding="utf-8",
        )
        assert voiceid.summary()[0]["n_by_lang"] == {"unknown": 1}
        for i in range(65):
            voiceid.stash(1000.0 + i, [1.0, 0.01 * i], "ja", 0.9)
            voiceid.add_sample("u", "A", 1000.0 + i)
        for i in range(65):
            voiceid.stash(2000.0 + i, [0.0, 1.0 + 0.01 * i], "en", 0.9)
            voiceid.add_sample("u", "A", 2000.0 + i)
        profile = voiceid.load_profiles()["u"]
        assert sum(s["lang"] == "ja" for s in profile["samples"]) == 64
        assert sum(s["lang"] == "en" for s in profile["samples"]) == 64
        assert any(s["lang"] == "unknown" for s in profile["samples"])
    finally:
        tempdir.cleanup()


def test_match_prefers_same_language_and_candidates_are_manual():
    tempdir = _isolated_voiceid()
    try:
        voiceid.stash(1.0, [1.0, 0.0], "ja", 0.95)
        voiceid.stash(2.0, [0.99, 0.1], "en", 0.95)
        voiceid.add_sample("ja-user", "J", 1.0)
        voiceid.add_sample("en-user", "E", 2.0)
        assert voiceid.match([0.99, 0.1], 0.5, lang="ja")[0] == "ja-user"
        voiceid.stash(3.0, [0.98, 0.2], "ja", 0.95)
        voiceid.stash(4.0, [0.97, 0.2], "ja", 0.95)
        result = voiceid.candidates(4.0, threshold=0.6, lang="ja", limit=5)
        assert [row["ts"] for row in result] == [3.0]
        assert voiceid.summary()[0]["n"] == 1
    finally:
        tempdir.cleanup()


def test_observe_persists_language_before_matching():
    tempdir = _isolated_voiceid()
    try:
        hit = voiceid.observe(10.0, [1.0, 0.0], "en", 0.82, 0.5)
        assert hit is None
        row = voiceid.pending(limit=1)["items"][0]
        assert row["lang"] == "en"
        assert row["lang_conf"] == 0.82
    finally:
        tempdir.cleanup()


if __name__ == "__main__":
    for test in (
        test_stash_keeps_language_and_pages_without_trimming,
        test_old_vecs_are_unknown_and_languages_have_independent_capacity,
        test_match_prefers_same_language_and_candidates_are_manual,
        test_observe_persists_language_before_matching,
    ):
        test()
