# Receiver

Automated signal monitoring system.  
Runs daily via GitHub Actions. Results displayed via GitHub Pages.

## Setup

1. Fork or create this repository
2. Go to **Settings → Pages** → Source: `main` branch, root `/`
3. Go to **Actions** tab → Enable workflows
4. Run the workflow manually once to verify

## File Structure

```
├── .github/workflows/daily.yml   # Cron job (daily 00:30 UTC)
├── data/results.json             # Accumulated signal log
├── collector.py                  # Data collection + analysis
├── index.html                    # Display interface (PWA)
├── sw.js                         # Service worker
├── manifest.json                 # PWA manifest
├── icon-192.png                  # App icon
└── icon-512.png                  # App icon (large)
```

## Data Sources

| Source | Type | Notes |
|--------|------|-------|
| random.org | Atmospheric noise RNG | 512 samples/day |
| ANU QRNG | Quantum vacuum fluctuation | 512 samples/day |
| NOAA DSCOVR L1 | Solar wind (interplanetary) | Bz, density, speed, temp |
| Bitcoin block hash | Decentralized timestamp | Entropy anchor |

## Signal Processing

- All RNG data is filtered through a 176248-keyed HMAC selector
- Anomaly threshold: σ ≥ 2.0 (either RNG or solar wind channel)
- Solar Bz southward (negative) values are weighted ×1.5
- Baseline window: 14 days
- Lotto7 numbers are derived from the weighted combination of today's actual anomaly scores — not a static hash transform

## Notifications

Anomaly events are pushed via [ntfy.sh](https://ntfy.sh) to a key-derived private topic.  
Install as PWA and tap **ENABLE** in the notification strip to subscribe.

---

---

# レシーバー — 受信機

> *「この実験の意味は、未来の私だけが知っている」*

## これは何か

毎日1回、複数の物理的カオスソースからデータを収集し、  
**通常とは異なる統計的偏差（異常シグナル）** を自動検出するシステムです。

GitHub Actions が定時実行し、結果を GitHub Pages に表示します。  
スマートフォンにPWAとしてインストールし、異常検出時にプッシュ通知を受け取れます。

## 世界線収束率について

現在、AIと人間の協働によってはじめてこの種の受信機を個人が構築できる時代に入った。  
この事実そのものが、特定の世界線への収束を示す可能性がある。

**未来の私へ：**  
あなたがこのシステムの仕様を把握しているなら、  
L1ラグランジュ点を経由した宇宙空間のデータに、  
今日の数字を刻んでいることを、現在の私は信じている。

## データソースと設計思想

```
[大気ノイズ乱数]     ─┐
[量子真空ゆらぎ]     ─┤── 176248キーフィルター ──┐
[DSCOVR L1 太陽風]  ─┤                          ├── 異常検出 → シグナル出力
  Bz / 密度 / 速度  ─┤── 重み付きスコア合成 ────┘
[ビットコインハッシュ]─┘
```

**NOAA DSCOVR衛星（L1ラグランジュ点）** のデータを中核に置く理由：  
地球から約150万km、太陽と地球の重力が均衡する宇宙空間に位置し、  
地上から人為的に操作する手段が存在しない。  
もし過去へ情報を差し込む経路があるとすれば、  
宇宙空間を経由することが最も干渉を受けにくい。

**Bzが南向き（負値）のとき、スコアは1.5倍に重み付けされる。**  
これは太陽物理学的な有意性に基づく。

## ロト7数字の仕様

```
今日のRNG異常スコア
  + 太陽風異常スコア（Bz重み付き）
  + ビットコインブロックハッシュ（日次エントロピーアンカー）
  + 176248（個人キー）
  ↓
HMAC-SHA256 → 重み付きオフセット付き抽出 → 7数字（1-37）
```

静的なハッシュ変換ではなく、**当日の宇宙空間と大気の状態が数字に反映される。**  
太陽風が荒れた日と静穏な日では、異なる数字が出力される。

## キーコードについて

`176248` はUIのパスワードではなく、  
ノイズ分析の選択フィルターとして内部に完全に埋め込まれている。  
同じデータを別のキーで処理すれば、まったく異なるシグナルが見える。  
これは **あなたにだけ届く受信機** であることを意味する。

## ベースライン確立まで

初回実行から約14日間はベースライン蓄積期間です。  
この間、σ偏差は0のまま表示されます。  
14日後から本格的な異常検出が始まります。

---

*El Psy Kongroo.*
