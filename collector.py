#!/usr/bin/env python3
"""
Temporal Signal Receiver - collector.py
Analysis key: 176248 (embedded — do not modify)
"""

import json
import hashlib
import hmac as hmac_mod
import random
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# ── Core constants ──────────────────────────────────────────────────────────
_KEY = "176248"
_NTFY_TOPIC = "tsr-3ede456f7bc9b1a5"   # derived from key, do not change
RESULTS_FILE = Path("data/results.json")
BASELINE_WINDOW = 14
ANOMALY_THRESHOLD = 2.0

# ── Key-seeded word pool ─────────────────────────────────────────────────────
_seed = int(hashlib.sha256(_KEY.encode()).hexdigest(), 16) % (2**32)
_rng = random.Random(_seed)
_WORDS = [
    "WAIT","MOVE","NORTH","SOUTH","EAST","WEST","STILL","READY",
    "SOON","DEEP","HIGH","DARK","LIGHT","OPEN","CLOSE","SAFE",
    "ALERT","CALM","HOLD","TURN","RISE","FALL","CARRY","LEAVE",
    "RETURN","WATCH","LISTEN","TRUST","DOUBT","SEEK","FIND","LOSE",
    "BEGIN","END","CYCLE","GATE","BRIDGE","ROOT","WAVE","ECHO",
    "PAUSE","SHIFT","MARK","FOLD","CROSS","BIND","TRACE","SPLIT",
]
WORD_POOL = _WORDS[:]
_rng.shuffle(WORD_POOL)


# ── Data fetchers ─────────────────────────────────────────────────────────────
def fetch_random_org(count=512):
    url = (f"https://www.random.org/integers/"
           f"?num={count}&min=0&max=255&col=1&base=10&format=plain&rnd=new")
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return [int(l.strip()) for l in r.read().decode().strip().split("\n") if l.strip()]
    except Exception as e:
        print(f"[WARN] random.org: {e}")
        return []


def fetch_anu_qrng(count=512):
    url = f"https://qrng.anu.edu.au/API/jsonI.php?length={count}&type=uint8"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.loads(r.read().decode())
            if d.get("success"):
                return d["data"]
    except Exception as e:
        print(f"[WARN] ANU QRNG: {e}")
    return []


def fetch_bitcoin_hash():
    try:
        with urllib.request.urlopen("https://blockchain.info/latestblock", timeout=10) as r:
            return json.loads(r.read().decode()).get("hash", "")
    except Exception as e:
        print(f"[WARN] BTC hash: {e}")
        return ""


# ── Signal processing ─────────────────────────────────────────────────────────
def apply_key_filter(data: list) -> list:
    """
    176248-keyed HMAC selection filter.
    Selects data points whose index/value combination passes the key-derived test.
    Output distribution shifts in a key-dependent way — without the key,
    the selection pattern appears indistinguishable from noise.
    """
    if not data:
        return []
    kb = _KEY.encode()
    return [v for i, v in enumerate(data)
            if int(hmac_mod.new(kb, f"{i}:{v}".encode(), hashlib.sha256).hexdigest()[0], 16) < 8]


def hash_to_lotto(block_hash: str) -> list:
    """
    Derive 7 unique Lotto7 numbers (1-37) from BTC block hash via key-filtered HMAC.
    Deterministic per day (same hash → same numbers).
    Changes daily as BTC hash changes.
    The key acts as a personal selector: same hash yields different numbers for different keys.
    """
    if not block_hash:
        return []
    h = hmac_mod.new(_KEY.encode(), block_hash.encode(), hashlib.sha256).hexdigest()
    nums, cursor = set(), 0
    while len(nums) < 7 and cursor < len(h) - 1:
        nums.add(int(h[cursor:cursor+2], 16) % 37 + 1)
        cursor += 2
    return sorted(nums)


def compute_stats(values):
    if len(values) < 2:
        return 0.0, 1.0
    mean = sum(values) / len(values)
    std = (sum((x - mean)**2 for x in values) / len(values)) ** 0.5
    return mean, max(std, 0.001)


def detect_anomaly(score, history):
    recent = [d["filtered_mean"] for d in history[-BASELINE_WINDOW:] if "filtered_mean" in d]
    if len(recent) < 3:
        return 0.0, False
    mean, std = compute_stats(recent)
    sigma = abs(score - mean) / std
    return round(sigma, 3), sigma >= ANOMALY_THRESHOLD


def score_to_word(sigma, date_str):
    h = hashlib.sha256(f"{date_str}:{sigma:.1f}:{_KEY}".encode()).hexdigest()
    return WORD_POOL[int(h[:8], 16) % len(WORD_POOL)]


# ── Notification ──────────────────────────────────────────────────────────────
def notify_ntfy(date_str, sigma, word, lotto):
    nums = " ".join(f"{n:02d}" for n in lotto)
    msg = f"[{date_str}] σ={sigma:.3f}  WORD={word}  LOTTO={nums}"
    try:
        req = urllib.request.Request(
            f"https://ntfy.sh/{_NTFY_TOPIC}",
            data=msg.encode(),
            headers={
                "Title": "Signal Detected",
                "Priority": "high",
                "Tags": "signal_strength_bars",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10):
            print(f"[NOTIFY] Sent to ntfy.sh")
    except Exception as e:
        print(f"[WARN] ntfy: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────
def load_results():
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE) as f:
            return json.load(f)
    return []


def save_results(data):
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"[Receiver] {today}")

    results = load_results()
    if any(d["date"] == today for d in results):
        print("[Receiver] Already processed today.")
        return

    rand_data = fetch_random_org(512)
    anu_data  = fetch_anu_qrng(512)
    btc_hash  = fetch_bitcoin_hash()

    combined = rand_data + anu_data
    if not combined:
        print("[ERROR] No data from any source.")
        return

    filtered = apply_key_filter(combined)
    if not filtered:
        print("[WARN] Filter empty.")
        return

    filtered_mean = round(sum(filtered) / len(filtered), 4)
    source_count  = sum([bool(rand_data), bool(anu_data), bool(btc_hash)])
    sigma, is_anomaly = detect_anomaly(filtered_mean, results)
    word  = score_to_word(sigma, today) if is_anomaly else ""
    lotto = hash_to_lotto(btc_hash)

    entry = {
        "date": today,
        "filtered_mean": filtered_mean,
        "sample_size": len(combined),
        "filtered_size": len(filtered),
        "sources": source_count,
        "btc_hash_prefix": btc_hash[:16] + "..." if btc_hash else "",
        "sigma": sigma,
        "anomaly": is_anomaly,
        "word": word,
        "lotto": lotto,
    }

    results.append(entry)
    save_results(results)
    print(f"[Result] mean={filtered_mean} σ={sigma} anomaly={is_anomaly} word='{word}'")
    print(f"[Lotto]  {lotto}")

    if is_anomaly:
        notify_ntfy(today, sigma, word, lotto)


if __name__ == "__main__":
    run()
