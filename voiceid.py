#!/usr/bin/env python3
import json
import math
import os
import time
from pathlib import Path

DATA = Path(__file__).parent / "data"
VOICES = DATA / "voices.json"
EMBEDS = DATA / "embeds.jsonl"
MAX_SAMPLES_PER_LANG = 64

_profiles = {}
_mtime = 0.0
_embed_cache_key = None
_embed_cache_rows = []


def _norm(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def load_profiles():
    global _profiles, _mtime
    try:
        mtime = VOICES.stat().st_mtime
    except FileNotFoundError:
        _profiles, _mtime = {}, 0.0
        return _profiles
    if mtime != _mtime:
        try:
            raw = json.loads(VOICES.read_text(encoding="utf-8"))
            _profiles = {}
            for uid, profile in raw.items():
                samples = profile.get("samples")
                if not samples:
                    samples = [{"lang": "unknown", "ts": 0.0, "v": _norm(v)}
                               for v in profile.get("vecs", [])]
                _profiles[uid] = {
                    "name": profile.get("name", ""),
                    "samples": samples,
                    "vecs": [sample["v"] for sample in samples],
                }
            _mtime = mtime
        except (json.JSONDecodeError, OSError):
            pass
    return _profiles


def _save_profiles():
    global _mtime
    DATA.mkdir(exist_ok=True)
    tmp = VOICES.with_suffix(".tmp")
    tmp.write_text(json.dumps(_profiles, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, VOICES)
    _mtime = VOICES.stat().st_mtime


def match(vec, threshold, lang=None):
    vec = _norm(vec)
    profiles = load_profiles()
    has_same_language = (
        lang is not None and lang != "unknown" and any(
            any(sample.get("lang", "unknown") == lang
                for sample in profile.get("samples", []))
            for profile in profiles.values()
        )
    )
    scored = []
    for uid, profile in profiles.items():
        samples = profile.get("samples", [])
        same_language = [
            sample for sample in samples
            if lang is not None and sample.get("lang", "unknown") == lang
        ]
        if has_same_language and not same_language:
            continue
        selected = same_language or samples
        scores = sorted(
            (sum(a * b for a, b in zip(vec, _norm(sample["v"])))
             for sample in selected),
            reverse=True,
        )
        if scores:
            score = (sum(scores[:3]) / min(3, len(scores))
                     if len(scores) >= 3 else scores[0])
            scored.append((score, uid))
    if not scored:
        return None
    score, uid = max(scored)
    required = threshold + 0.05 if lang == "unknown" else threshold
    if score < required:
        return None
    return uid, profiles[uid]["name"], score


def stash(ts, vec, lang="unknown", lang_conf=0.0):
    global _embed_cache_key
    DATA.mkdir(exist_ok=True)
    with EMBEDS.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({
            "ts": ts,
            "v": [round(x, 4) for x in _norm(vec)],
            "lang": lang,
            "lang_conf": lang_conf,
        }) + "\n")
    _embed_cache_key = None


def _embed_rows():
    global _embed_cache_key, _embed_cache_rows
    if not EMBEDS.exists():
        return []
    stat = EMBEDS.stat()
    cache_key = (stat.st_mtime_ns, stat.st_size)
    if cache_key == _embed_cache_key:
        return _embed_cache_rows
    rows = []
    for line in EMBEDS.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if "ts" in row and "v" in row:
                row.setdefault("lang", "unknown")
                row.setdefault("lang_conf", 0.0)
                rows.append(row)
        except (json.JSONDecodeError, TypeError):
            continue
    _embed_cache_key = cache_key
    _embed_cache_rows = rows
    return rows


def _find_embed(ts):
    for row in _embed_rows():
        if abs(row["ts"] - ts) < 0.01:
            return row
    return None


def pending(limit=50, before=None):
    rows = sorted(_embed_rows(), key=lambda row: row["ts"], reverse=True)
    if before is not None:
        rows = [row for row in rows if row["ts"] < before]
    items = rows[:limit]
    return {
        "items": items,
        "next_before": items[-1]["ts"] if len(rows) > limit else None,
    }


def add_samples(uid, name, timestamps):
    load_profiles()
    profile = _profiles.setdefault(uid, {"name": name, "samples": [], "vecs": []})
    profile["name"] = name
    added = missing = skipped = 0
    for ts in timestamps:
        row = _find_embed(ts)
        if row is None:
            missing += 1
            continue
        if any(abs(sample.get("ts", 0.0) - ts) < 0.01
               for sample in profile["samples"]):
            skipped += 1
            continue
        sample = {"lang": row["lang"], "ts": ts, "v": row["v"]}
        same_language = [
            existing for existing in profile["samples"]
            if existing.get("lang", "unknown") == sample["lang"]
        ]
        if len(same_language) >= MAX_SAMPLES_PER_LANG:
            def average_similarity(existing):
                others = [other for other in same_language if other is not existing]
                return sum(
                    sum(a * b for a, b in zip(_norm(existing["v"]), _norm(other["v"])))
                    for other in others
                ) / len(others)

            replacement = max(
                same_language,
                key=average_similarity,
            )
            profile["samples"].remove(replacement)
        profile["samples"].append(sample)
        added += 1
    profile["vecs"] = [sample["v"] for sample in profile["samples"]]
    if added:
        _save_profiles()
    return {"added": added, "missing": missing, "skipped": skipped}


def add_sample(uid, name, ts):
    return add_samples(uid, name, [ts])["added"] == 1


def candidates(ts, threshold, lang=None, limit=20):
    target = _find_embed(ts)
    if target is None:
        return []
    registered = {
        sample.get("ts")
        for profile in load_profiles().values()
        for sample in profile.get("samples", [])
    }
    target_vec = _norm(target["v"])
    result = []
    for row in _embed_rows():
        if (abs(row["ts"] - ts) < 0.01 or
                any(abs(row["ts"] - timestamp) < 0.01
                    for timestamp in registered)):
            continue
        if lang is not None and row["lang"] != lang:
            continue
        score = sum(a * b for a, b in zip(target_vec, _norm(row["v"])))
        if score >= threshold:
            result.append({**row, "score": score})
    return sorted(result, key=lambda row: row["score"], reverse=True)[:limit]


def observe(ts, vec, lang, lang_conf, threshold):
    stash(ts, vec, lang, lang_conf)
    return match(vec, threshold, lang=lang)


def reset(uid):
    load_profiles()
    if _profiles.pop(uid, None) is None:
        return False
    _save_profiles()
    return True


def summary():
    result = []
    for uid, profile in load_profiles().items():
        by_language = {}
        for sample in profile.get("samples", []):
            lang = sample.get("lang", "unknown")
            by_language[lang] = by_language.get(lang, 0) + 1
        result.append({
            "uid": uid,
            "name": profile["name"],
            "n": len(profile.get("samples", [])),
            "n_by_lang": by_language,
        })
    return result


_encoder = None
_dead = False


def embed(audio_f32_16k):
    """16kHz mono float32 → 192次元声紋。speechbrain未導入/失敗はNone(以後休止)"""
    global _encoder, _dead
    if _dead:
        return None
    if _encoder is None:
        try:
            import torch
            from speechbrain.inference.speaker import EncoderClassifier
            dev = "cuda" if torch.cuda.is_available() else "cpu"
            _encoder = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=str(DATA / "ecapa"), run_opts={"device": dev})
            print(time.strftime("%H:%M:%S ") + f"こえ分類 準備完了 (ecapa/{dev})", flush=True)
        except Exception as e:
            _dead = True
            print(time.strftime("%H:%M:%S ") +
                  f"こえ分類は休止({e.__class__.__name__}: {str(e)[:80]})。"
                  "pip install speechbrain で有効になります", flush=True)
            return None
    try:
        import torch
        with torch.no_grad():
            t = torch.from_numpy(audio_f32_16k).unsqueeze(0)
            v = _encoder.encode_batch(t).squeeze()
        return [float(x) for x in v]
    except Exception:
        return None
