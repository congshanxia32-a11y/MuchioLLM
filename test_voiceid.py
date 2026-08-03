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
    voiceid._embed_cache_key = None
    voiceid._embed_cache_rows = []
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


def test_known_language_match_keeps_legacy_unknown_profile_fallback():
    tempdir = _isolated_voiceid()
    try:
        voiceid.VOICES.write_text(
            json.dumps({
                "legacy": {"name": "Legacy", "vecs": [[1.0, 0.0]]},
                "ja-user": {
                    "name": "Japanese",
                    "samples": [{"lang": "ja", "ts": 1.0, "v": [0.0, 1.0]}],
                },
            }),
            encoding="utf-8",
        )
        hit = voiceid.match([1.0, 0.0], 0.9, lang="ja")
        assert hit is not None
        assert hit[0] == "legacy"
    finally:
        tempdir.cleanup()


def test_language_candidates_include_legacy_unknown_rows_as_fallback():
    tempdir = _isolated_voiceid()
    try:
        voiceid.EMBEDS.write_text(
            '{"ts": 3.0, "v": [1.0, 0.0], "lang": "ja", "lang_conf": 0.9}\n'
            '{"ts": 2.0, "v": [0.99, 0.1]}\n'
            '{"ts": 1.0, "v": [0.0, 1.0], "lang": "en", "lang_conf": 0.9}\n',
            encoding="utf-8",
        )
        result = voiceid.candidates(3.0, threshold=0.8, lang="ja", limit=5)
        assert [(row["ts"], row["lang"]) for row in result] == [(2.0, "unknown")]
    finally:
        tempdir.cleanup()


def test_malformed_embed_rows_are_skipped():
    tempdir = _isolated_voiceid()
    try:
        voiceid.EMBEDS.write_text(
            '{"ts": 4.0, "v": []}\n'
            '{"ts": 3.0, "v": [1.0, "bad"]}\n'
            '{"ts": 2.0, "v": [1.0, 0.0], "lang": "", "lang_conf": 0.9}\n'
            '{"ts": NaN, "v": [1.0, 0.0]}\n',
            encoding="utf-8",
        )
        page = voiceid.pending(limit=10)
        assert [(row["ts"], row["lang"]) for row in page["items"]] == [
            (2.0, "unknown"),
        ]
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


def test_overflow_replaces_most_redundant_existing_sample():
    tempdir = _isolated_voiceid()
    try:
        voiceid.stash(1.0, [1.0, 0.0], "ja", 0.9)
        voiceid.stash(2.0, [0.999, 0.0447], "ja", 0.9)
        voiceid.stash(3.0, [0.0, 1.0], "ja", 0.9)
        for ts in range(100, 161):
            voiceid.stash(float(ts), [0.0, 1.0], "ja", 0.9)
        voiceid.add_samples("u", "A", list(range(1, 4)) + list(range(100, 161)))
        voiceid.stash(200.0, [0.999, 0.0447], "ja", 0.9)
        result = voiceid.add_samples("u", "A", [200.0])
        timestamps = {sample["ts"] for sample in voiceid.load_profiles()["u"]["samples"]}
        assert result == {"added": 1, "missing": 0, "skipped": 0}
        assert len(timestamps) == 64
        assert 2.0 in timestamps
        assert 3.0 not in timestamps
    finally:
        tempdir.cleanup()


def test_candidates_excludes_registered_nearby_timestamp():
    tempdir = _isolated_voiceid()
    try:
        voiceid.stash(1.0, [1.0, 0.0], "ja", 0.9)
        voiceid.add_sample("u", "A", 1.0)
        voiceid.stash(1.005, [1.0, 0.0], "ja", 0.9)
        voiceid.stash(2.0, [0.99, 0.1], "ja", 0.9)
        assert [row["ts"] for row in voiceid.candidates(2.0, 0.5, "ja")] == []
    finally:
        tempdir.cleanup()


if __name__ == "__main__":
    for test in (
        test_stash_keeps_language_and_pages_without_trimming,
        test_old_vecs_are_unknown_and_languages_have_independent_capacity,
        test_match_prefers_same_language_and_candidates_are_manual,
        test_known_language_match_keeps_legacy_unknown_profile_fallback,
        test_language_candidates_include_legacy_unknown_rows_as_fallback,
        test_malformed_embed_rows_are_skipped,
        test_observe_persists_language_before_matching,
        test_overflow_replaces_most_redundant_existing_sample,
        test_candidates_excludes_registered_nearby_timestamp,
    ):
        test()
