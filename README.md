# Receiver

Automated signal monitoring system.  
Runs daily via GitHub Actions. Results displayed via GitHub Pages.

## Setup

1. Fork or create this repository
2. Go to **Settings → Pages** → Source: `main` branch, root `/`
3. Go to **Actions** tab → Enable workflows
4. Run the workflow manually once to verify

## Structure

```
├── .github/workflows/daily.yml   # Cron job (daily 00:30 UTC)
├── data/results.json             # Accumulated signal log
├── collector.py                  # Data collection + analysis
└── index.html                    # Display interface
```

## Notes

- Baseline requires ~14 days to stabilize
- Anomaly threshold: 2σ deviation across key-filtered data
- Sources: random.org, ANU QRNG, Bitcoin block hash
