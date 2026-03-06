#!/usr/bin/env python3
"""
Temporal Signal Receiver - collector.py
Analysis key: 176248 (embedded — do not modify)

Data sources:
  [A] random.org        — atmospheric noise RNG
  [B] ANU QRNG          — quantum vacuum fluctuation RNG
  [C] NOAA DSCOVR L1    — solar wind @ 1.5M km from Earth (interplanetary space)
                          Bz: interplanetary magnetic field south component
                          Proton density / speed / temperature
  [D] Bitcoin block hash — decentralized timestamp anchor

Lotto7 generation:
  Weighted combination of per-source anomaly scores → key-filtered extraction.
  Numbers reflect the actual signal pattern of the day, not a hash transform.
"""

import json
import hashlib
import hmac as hmac_mod
import math
import random
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ── Core constants ───────────────────────────────────────────────────────────
_KEY              = "176248"
_NTFY_TOPIC       = "tsr-3ede456f7bc9b1a5"
RESULTS_FILE      = Path("data/results.json")
BASELINE_WINDOW   = 14
ANOMALY_THRESHOLD = 2.0

# ── Key-seeded word pool ─────────────────────────────────────────────────────
_seed = int(hashlib.sha256(_KEY.encode()).hexdigest(), 16) % (2**32)
_rng  = random.Random(_seed)
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


# ── Data fetchers ────────────────────────────────────────────────────────────
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


def fetch_solar_wind():
    """
    Fetch DSCOVR L1 solar wind data from NOAA SWPC.
    L1 Lagrange point: 1.5M km sunward — fully outside Earth's magnetosphere.
    Returns dict with Bz (nT), proton density (cm⁻³), speed (km/s), temperature (K).
    Data cadence: 1-minute samples. We take the last hour's mean.
    """
    result = {
        "bz": None, "proton_density": None,
        "proton_speed": None, "proton_temp": None,
        "bz_samples": [], "raw_scores": []
    }

    # Magnetic field (Bz component)
    try:
        url = "https://services.swpc.noaa.gov/products/solar-wind/mag-1-hour.json"
        with urllib.request.urlopen(url, timeout=15) as r:
            rows = json.loads(r.read().decode())
            # rows: [time_tag, bx, by, bz, lon, lat, bt]
            bz_vals = []
            for row in rows[1:]:   # skip header
                try:
                    bz_vals.append(float(row[3]))
                except (ValueError, IndexError):
                    pass
            if bz_vals:
                result["bz"] = round(sum(bz_vals) / len(bz_vals), 4)
                result["bz_samples"] = bz_vals[-10:]  # last 10 for variance
                print(f"[Solar] Bz mean={result['bz']:.3f} nT  ({len(bz_vals)} samples)")
    except Exception as e:
        print(f"[WARN] Solar wind mag: {e}")

    # Plasma (density / speed / temperature)
    try:
        url = "https://services.swpc.noaa.gov/products/solar-wind/plasma-1-hour.json"
        with urllib.request.urlopen(url, timeout=15) as r:
            rows = json.loads(r.read().decode())
            # rows: [time_tag, density, speed, temperature]
            densities, speeds, temps = [], [], []
            for row in rows[1:]:
                try:
                    densities.append(float(row[1]))
                    speeds.append(float(row[2]))
                    temps.append(float(row[3]))
                except (ValueError, IndexError):
                    pass
            if densities:
                result["proton_density"] = round(sum(densities) / len(densities), 4)
                result["proton_speed"]   = round(sum(speeds)    / len(speeds),    2)
                result["proton_temp"]    = round(sum(temps)     / len(temps),     1)
                print(f"[Solar] density={result['proton_density']:.3f} cm⁻³  "
                      f"speed={result['proton_speed']:.1f} km/s  "
                      f"temp={result['proton_temp']:.0f} K")
    except Exception as e:
        print(f"[WARN] Solar wind plasma: {e}")

    return result


def fetch_bitcoin_hash():
    try:
        with urllib.request.urlopen("https://blockchain.info/latestblock", timeout=10) as r:
            return json.loads(r.read().decode()).get("hash", "")
    except Exception as e:
        print(f"[WARN] BTC hash: {e}")
        return ""


# ── Signal processing ────────────────────────────────────────────────────────
def apply_key_filter(data: list) -> list:
    """
    176248-keyed HMAC point selector.
    Each (index, value) pair is tested against a key-derived threshold.
    Distribution shift is key-dependent and statistically opaque without the key.
    """
    if not data:
        return []
    kb = _KEY.encode()
    return [v for i, v in enumerate(data)
            if int(hmac_mod.new(kb, f"{i}:{v}".encode(), hashlib.sha256).hexdigest()[0], 16) < 8]


def compute_stats(values):
    if len(values) < 2:
        return 0.0, 1.0
    mean = sum(values) / len(values)
    std  = (sum((x - mean)**2 for x in values) / len(values)) ** 0.5
    return mean, max(std, 0.001)


def detect_anomaly(score, history, field="filtered_mean"):
    recent = [d[field] for d in history[-BASELINE_WINDOW:] if d.get(field) is not None]
    if len(recent) < 3:
        return 0.0, False
    mean, std = compute_stats(recent)
    sigma = abs(score - mean) / std
    return round(sigma, 3), sigma >= ANOMALY_THRESHOLD


def solar_anomaly_score(sw: dict, history: list) -> float:
    """
    Compute composite solar wind anomaly score (0.0 ~ unbounded sigma).
    Uses Bz southward deviation + proton density + speed.

    Bz < 0 (southward) is geomagnetically significant — weight it more.
    """
    scores = []

    if sw["bz"] is not None:
        bz_sigma, _ = detect_anomaly(sw["bz"], history, "solar_bz")
        # Southward Bz (negative) is more "interesting" — amplify
        direction_weight = 1.5 if sw["bz"] < 0 else 1.0
        scores.append(bz_sigma * direction_weight)

    if sw["proton_density"] is not None:
        d_sigma, _ = detect_anomaly(sw["proton_density"], history, "solar_density")
        scores.append(d_sigma)

    if sw["proton_speed"] is not None:
        s_sigma, _ = detect_anomaly(sw["proton_speed"], history, "solar_speed")
        scores.append(s_sigma)

    return round(sum(scores) / len(scores), 4) if scores else 0.0


def weighted_lotto(filtered_mean: float, solar_score: float,
                   btc_hash: str, date_str: str) -> list:
    """
    Generate 7 unique Lotto7 numbers (1-37) from today's actual signal pattern.

    Method:
      1. Combine per-source anomaly scores with weights
      2. Mix with key via HMAC
      3. Extract numbers from the resulting entropy

    Higher anomaly days → different number distributions than quiet days.
    Same date + different key → completely different numbers.
    """
    # Composite entropy string from today's actual measurements
    composite = (
        f"{date_str}:"
        f"{_KEY}:"
        f"fm={filtered_mean:.4f}:"
        f"sw={solar_score:.4f}:"
        f"btc={btc_hash[:32] if btc_hash else 'none'}"
    )
    h = hmac_mod.new(_KEY.encode(), composite.encode(), hashlib.sha256).hexdigest()

    # Weight: solar anomaly tilts the selection window
    weight_offset = int(min(solar_score * 2, 8))  # 0–8 shift based on solar activity

    nums, cursor = set(), weight_offset
    h_extended = h + hashlib.sha256(h.encode()).hexdigest()  # extend if needed
    while len(nums) < 7 and cursor < len(h_extended) - 1:
        raw = int(h_extended[cursor:cursor+2], 16)
        nums.add((raw + weight_offset) % 37 + 1)
        cursor += 2

    return sorted(nums)


def score_to_word(sigma: float, date_str: str) -> str:
    h = hashlib.sha256(f"{date_str}:{sigma:.1f}:{_KEY}".encode()).hexdigest()
    return WORD_POOL[int(h[:8], 16) % len(WORD_POOL)]


# ── Notification ─────────────────────────────────────────────────────────────
def notify_ntfy(date_str, sigma, solar_score, word, lotto):
    nums = " ".join(f"{n:02d}" for n in lotto)
    msg  = (f"[{date_str}]\n"
            f"σ={sigma:.3f}  solar={solar_score:.3f}\n"
            f"WORD={word}\n"
            f"LOTTO: {nums}")
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
            print("[NOTIFY] Sent to ntfy.sh")
    except Exception as e:
        print(f"[WARN] ntfy: {e}")


# ── Persistence ───────────────────────────────────────────────────────────────
def load_results():
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE) as f:
            return json.load(f)
    return []


def save_results(data):
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"[Receiver] {today}")

    results = load_results()
    if any(d["date"] == today for d in results):
        print("[Receiver] Already processed today.")
        return

    # ── Fetch all sources ──
    rand_data = fetch_random_org(512)
    anu_data  = fetch_anu_qrng(512)
    solar     = fetch_solar_wind()
    btc_hash  = fetch_bitcoin_hash()

    combined = rand_data + anu_data
    if not combined:
        print("[ERROR] No RNG data from any source.")
        return

    # ── RNG processing ──
    filtered      = apply_key_filter(combined)
    filtered_mean = round(sum(filtered) / len(filtered), 4) if filtered else 0.0
    sigma_rng, is_anomaly_rng = detect_anomaly(filtered_mean, results)

    # ── Solar wind anomaly ──
    solar_score   = solar_anomaly_score(solar, results)
    _, is_anomaly_solar = (solar_score, solar_score >= ANOMALY_THRESHOLD), (solar_score >= ANOMALY_THRESHOLD,)
    is_anomaly_solar = solar_score >= ANOMALY_THRESHOLD

    # Combined anomaly: either source triggers
    is_anomaly = is_anomaly_rng or is_anomaly_solar
    sigma_combined = round(max(sigma_rng, solar_score), 3)

    # ── Outputs ──
    word  = score_to_word(sigma_combined, today) if is_anomaly else ""
    lotto = weighted_lotto(filtered_mean, solar_score, btc_hash, today)

    source_count = sum([bool(rand_data), bool(anu_data),
                        solar["bz"] is not None, bool(btc_hash)])

    entry = {
        "date":           today,
        # RNG
        "filtered_mean":  filtered_mean,
        "sample_size":    len(combined),
        "filtered_size":  len(filtered),
        "sigma":          sigma_rng,
        # Solar wind (L1 interplanetary)
        "solar_bz":       solar["bz"],
        "solar_density":  solar["proton_density"],
        "solar_speed":    solar["proton_speed"],
        "solar_temp":     solar["proton_temp"],
        "solar_score":    solar_score,
        # Combined
        "sigma_combined": sigma_combined,
        "anomaly":        is_anomaly,
        "sources":        source_count,
        "btc_hash_prefix": btc_hash[:16] + "..." if btc_hash else "",
        # Signal output
        "word":           word,
        "lotto":          lotto,
    }

    results.append(entry)
    save_results(results)

    print(f"[RNG]    mean={filtered_mean}  σ={sigma_rng}  anomaly={is_anomaly_rng}")
    print(f"[Solar]  score={solar_score:.3f}  Bz={solar['bz']}  anomaly={is_anomaly_solar}")
    print(f"[Output] σ_combined={sigma_combined}  anomaly={is_anomaly}  word='{word}'")
    print(f"[Lotto]  {lotto}")

    if is_anomaly:
        notify_ntfy(today, sigma_combined, solar_score, word, lotto)


if __name__ == "__main__":
    run()
