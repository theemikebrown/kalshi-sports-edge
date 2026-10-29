# Kalshi Sports Edge 2.0 — research infrastructure update

This update preserves the existing Elo prediction method and saved research data. It does **not** claim to improve forecast accuracy or include injury-adjusted probabilities. It adds transparent quality/freshness gates, explicit player-availability verification status, richer price-comparison metrics, and deterministic offline tests.

## Why no live injury adjustment?
An authoritative, legally usable, timestamped player-availability feed has not been configured or validated. Inventing injury adjustments would be misleading. A future release can integrate such a source and compare its predictions out of sample against the original Elo baseline before using it for ranking.

## Installation
Upload the changed `cloud_job.py`, `market_audit.py`, `.github/workflows/daily-research.yml` and new `research_quality.py`, `tests/test_quality.py`, `UPGRADE_NOTES.md` to the repository, preserving paths. **Do not overwrite `data/` or `docs/` from the ZIP**; GitHub Actions regenerates docs and data. Then run the Daily NBA research workflow manually and refresh GitHub Pages. If the workflow has no qualifying games, it can succeed without creating new snapshots.

No real-money orders, live trader-copying, validated profitable edge, or confirmed injury feed is included.
