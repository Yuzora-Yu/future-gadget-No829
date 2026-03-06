#!/usr/bin/env python3
"""
Temporal Signal Receiver - collector.py
Key: 176248
"""

import json
import hashlib
import hmac
import os
import random
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

KEY = "176248"
RESULTS_FILE = Path("data/results.json")
BASELINE_WINDOW = 14  # days for baseline
ANOMALY_THRESHOLD = 2.0  # sigma

# Word pool (seeded by key — only meaningful with correct key)
_seed_val = int(hashlib.sha256(KEY.encode()).hexdigest(), 16) % (2**32)
_rng = random.Random(_seed_val)
_RAW_WORDS = [
    "WAIT","MOVE","NORTH","SOUTH","EAST","WEST","STILL","READY",
    "SOON","DEEP","HIGH","DARK","LIGHT","OPEN","CLOSE","SAFE",
    "ALERT","CALM","HOLD","TURN","RISE","FALL","CARRY","LEAVE",
    "RETURN","WATCH","LISTEN","TRUST","DOUBT","SEEK","FIND","LOSE",
    "BEGIN","END","CYCLE","GATE","BRIDGE","ROOT","WAVE","ECHO"
]
WORD_POOL = _RAW_WORDS[:]
_rng.shuffle(WORD_POOL)


def fetch_random_org(count=512):
    """Fetch true random integers from random.org"""
    url = (
        f"https://www.random.org/integers/"
        f"?num={count}&min=0&max=255&col=1&base=10&format=plain&rnd=new"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return [int(line.strip()) for line in r.read().decode().strip().split("\n") if line.strip()]
    except Exception as e:
        print(f"[WARN] random.org fetch failed: {e}")
        return []


def fetch_bitcoin_hash():
    """Fetch latest Bitcoin block hash from public API"""
    try:
        url = "https://blockchain.info/latestblock"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
            return data.get("hash", "")
    except Exception as e:
        print(f"[WARN] Bitcoin hash fetch failed: {e}")
        return ""


def fetch_anu_qrng(count=512):
    """Fetch quantum random numbers from ANU QRNG"""
    url = f"https://qrng.anu.edu.au/API/jsonI.php?length={count}&type=uint8"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
            if data.get("success"):
                return data["data"]
    except Exception as e:
        print(f"[WARN] ANU QRNG fetch failed: {e}")
    return []


def apply_key_filter(data: list[int], key: str = KEY) -> list[int]:
    """
    Apply 176248 key filter.
    Uses HMAC to derive a selection mask — only indices that pass
    the key-derived test are retained. Without the key, the selection
    looks like noise.
    """
    if not data:
        return []
    key_bytes = key.encode()
    selected = []
    for i, val in enumerate(data):
        probe = f"{i}:{val}".encode()
        h = hmac.new(key_bytes, probe, hashlib.sha256).hexdigest()
        # Keep if first nibble of hash < 8 (50% filter, key-dependent)
        if int(h[0], 16) < 8:
            selected.append(val)
    return selected


def hash_to_lotto(block_hash: str, key: str = KEY) -> list[int]:
    """Derive 7 unique numbers (1-37) from Bitcoin block hash + key"""
    if not block_hash:
        return []
    combined = hmac.new(key.encode(), block_hash.encode(), hashlib.sha256).hexdigest()
    numbers = set()
    cursor = 0
    while len(numbers) < 7 and cursor < len(combined) - 1:
        val = int(combined[cursor:cursor+2], 16) % 37 + 1
        numbers.add(val)
        cursor += 2
    return sorted(list(numbers))


def compute_stats(values: list[float]) -> tuple[float, float]:
    if len(values) < 2:
        return 0.0, 1.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    std = variance ** 0.5
    return mean, max(std, 0.001)


def detect_anomaly(today_score: float, history: list[dict]) -> tuple[float, bool]:
    """Compare today against baseline window. Returns (sigma, is_anomaly)"""
    recent = [d["filtered_mean"] for d in history[-BASELINE_WINDOW:] if "filtered_mean" in d]
    if len(recent) < 3:
        return 0.0, False
    mean, std = compute_stats(recent)
    sigma = abs(today_score - mean) / std
    return round(sigma, 3), sigma >= ANOMALY_THRESHOLD


def score_to_word(sigma: float, date_str: str) -> str:
    """Map anomaly signature to a word from key-seeded pool"""
    combined = f"{date_str}:{sigma:.1f}:{KEY}"
    h = hashlib.sha256(combined.encode()).hexdigest()
    idx = int(h[:8], 16) % len(WORD_POOL)
    return WORD_POOL[idx]


def load_results() -> list[dict]:
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE) as f:
            return json.load(f)
    return []


def save_results(data: list[dict]):
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def run():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"[Receiver] Running for {today}")

    results = load_results()

    # Skip if today already processed
    if any(d["date"] == today for d in results):
        print("[Receiver] Already processed today. Exiting.")
        return

    # --- Fetch data ---
    rand_data = fetch_random_org(512)
    anu_data = fetch_anu_qrng(512)
    btc_hash = fetch_bitcoin_hash()

    # Merge sources
    combined = rand_data + anu_data
    if not combined:
        print("[ERROR] No data received from any source.")
        return

    # --- Apply key filter ---
    filtered = apply_key_filter(combined)
    if not filtered:
        print("[WARN] Filter returned empty set.")
        return

    filtered_mean = round(sum(filtered) / len(filtered), 4)
    source_count = sum([bool(rand_data), bool(anu_data), bool(btc_hash)])

    # --- Anomaly detection ---
    sigma, is_anomaly = detect_anomaly(filtered_mean, results)

    # --- Lotto numbers from Bitcoin hash ---
    lotto = hash_to_lotto(btc_hash) if btc_hash else []

    # --- Word signal (only on anomaly) ---
    word = score_to_word(sigma, today) if is_anomaly else ""

    entry = {
        "date": today,
        "filtered_mean": filtered_mean,
        "sample_size": len(combined),
        "filtered_size": len(filtered),
        "sources": source_count,
        "btc_hash": btc_hash[:16] + "..." if btc_hash else "",
        "sigma": sigma,
        "anomaly": is_anomaly,
        "word": word,
        "lotto": lotto,
    }

    results.append(entry)
    save_results(results)

    print(f"[Result] mean={filtered_mean} sigma={sigma} anomaly={is_anomaly} word='{word}'")
    if lotto:
        print(f"[Lotto]  {lotto}")


if __name__ == "__main__":
    run()
