# Voice-memory whole-branch review fix round 1 report

## Scope

Worked only in:

`W:\UnityProjects\Sanatia\MuchioLLM_dist\MuchioLLM\.worktrees\voice-memory`

Feature range under review: `160264b..8ee7151`.

## Regression tests added first

Added regressions for the review brief:

- `test_known_language_match_keeps_legacy_unknown_profile_fallback`
  - Break caught: known-language matching must not globally drop legacy `{name, vecs}` unknown-only profiles when another profile has a same-language sample.
- `test_language_candidates_include_legacy_unknown_rows_as_fallback`
  - Break caught: `voiceid.candidates(..., lang="ja")` must include old pending rows whose language defaults to `unknown` when they clear the stricter fallback threshold.
- `test_malformed_embed_rows_are_skipped`
  - Break caught: malformed embedding rows with empty vectors, non-numeric vector entries, or non-finite timestamps must be skipped at load time.
- `_voice_page()` bounded scan assertion in `test_muchio.py`
  - Break caught: page building must stop after collecting `limit + 1` valid transcript-backed rows, not keep walking older pending history.
- `/voices?limit=1` HTTP assertion in `test_muchio.py`
  - Break caught: `/voices` must clamp to a positive `1..100` range, not force a minimum of 20.

Also reset `voiceid._embed_cache_key` and `voiceid._embed_cache_rows` in `test_voiceid.py`'s isolated helper as required.

## RED evidence

Commands run before production fixes:

```text
python test_voiceid.py
```

Result: exit 1 at the new legacy fallback regression:

```text
AssertionError at test_known_language_match_keeps_legacy_unknown_profile_fallback: assert hit is not None
```

```text
python -c "import test_voiceid; test_voiceid.test_language_candidates_include_legacy_unknown_rows_as_fallback()"
```

Result: exit 1:

```text
AssertionError
```

```text
python -c "import test_voiceid; test_voiceid.test_malformed_embed_rows_are_skipped()"
```

Result: exit 1:

```text
AssertionError
```

```text
python test_muchio.py
```

Result: exit 1 at the new bounded-scan regression:

```text
AssertionError: [(2, None), (2, 9.0), (2, 7.0)]
```

## Fixes implemented

- `voiceid.match`
  - Normalizes requested/sample language values.
  - For known input languages, scores same-language samples first.
  - Allows legacy `unknown` samples only as fallback, with `threshold + 0.05`.
  - Preserves `unknown` input behavior by keeping its stricter threshold.
- `voiceid.candidates`
  - Normalizes requested/row languages.
  - Allows `unknown` rows for `ja`/`en` candidate requests only as stricter fallback.
  - Keeps non-matching known-language rows excluded.
- `voiceid._embed_rows`
  - Converts `ts` to finite float.
  - Requires a non-empty finite numeric vector.
  - Normalizes/defaults language.
  - Defaults malformed/non-finite `lang_conf` to `0.0`.
  - Continues skipping malformed JSON/row content without aborting the load.
- `muchio_llm._voice_page`
  - Continues past embedding rows with no transcript metadata.
  - Stops once it has `limit + 1` valid transcript-backed rows or pending history is exhausted.
  - Returns `recent[:limit]` and sets `next_before` only when the extra valid row exists.
- `/voices` HTTP handler
  - Clamps `limit` to `1..100`.

## GREEN / full verification evidence

Required verification commands from the brief:

```text
python test_voiceid.py
python test_muchio.py
python test_muchio_relay.py
python test_peer_idle.py
python test_social_context.py
python test_ui_config.py
python -m py_compile voiceid.py vrc_listener.py muchio_llm.py test_voiceid.py
node --check ui/app.js
git diff --check
```

Observed results:

- `python test_voiceid.py`: exit 0
- `python test_muchio.py`: exit 0, printed usual model-substitution logs and `ok`
- `python test_muchio_relay.py`: exit 0, printed `ok`
- `python test_peer_idle.py`: exit 0, printed `ok`
- `python test_social_context.py`: exit 0, printed `ok`
- `python test_ui_config.py`: exit 0, printed `ok`
- `python -m py_compile voiceid.py vrc_listener.py muchio_llm.py test_voiceid.py`: exit 0
- `node --check ui/app.js`: exit 0
- `git diff --check`: exit 0; emitted only Git line-ending warnings for the modified files.

## Self-review

- Diff is limited to `voiceid.py`, `muchio_llm.py`, `test_voiceid.py`, and `test_muchio.py`.
- No audio storage was added.
- Existing compatibility API shapes are preserved.
- Unknown-language fallbacks are stricter than same-language matches.
- The `/voice_candidates` limit clamp was already `1..100`; only `/voices` needed adjustment.
- Concern: `git diff --check` reports CRLF-normalization warnings for modified files, but exits 0 and reports no whitespace errors.
