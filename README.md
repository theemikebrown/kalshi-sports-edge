# Kalshi Sports Edge v0.6 — cloud daily research

This project runs on **GitHub Actions** every day at **15:15 UTC** (8:15 AM California during daylight saving time, 7:15 AM in standard time). It does **not** need your Mac on. GitHub schedules are best-effort and can be delayed or disabled for inactive repositories. It also supports manual runs.

It collects public NBA YES ask quotes, confirms games have **not started** using ESPN scheduled start times (more than one hour in the future), generates unvalidated Elo probabilities, and saves up to 10 research snapshots per day. It checks completed prior-day games against ESPN scores and updates hypothetical P/L. The job commits its CSV data and `docs/index.html` into your GitHub repository. GitHub Pages can host that static results page.

## Setup (no terminal required)

1. Create a **new GitHub repository** at https://github.com/new. For the simplest setup, choose **Public**. **Public means all your saved research data is visible to anyone.** Never upload your `.venv`, personal watchlist, or private paper-trade files. A private repo can run Actions but Pages availability/settings depend on your GitHub plan.
2. Unzip this package and upload **all files and folders inside `kalshi_sports_dashboard`** to the repository root, including the hidden `.github/workflows/daily-research.yml` file. On macOS Finder, press **Command+Shift+.** to show hidden folders. The `.github` folder must exist in the repository for scheduling to work.
3. On GitHub, open **Settings → Actions → General → Workflow permissions**. Select **Read and write permissions** if your repository allows it, then save. The job needs this to commit daily CSV and HTML updates. If an organization disallows this, a maintainer must change the policy.
4. Open the **Actions** tab, select **Daily NBA research**, and choose **Run workflow** to test. Open the run and confirm a green checkmark. First run may take several minutes.
5. To publish the browser dashboard, open **Settings → Pages → Build and deployment**, choose **Deploy from a branch**, branch **main**, folder **/docs**, then save. GitHub will show your exact website URL once deployment succeeds (usually `https://YOUR-USERNAME.github.io/YOUR-REPO/`).
6. Bookmark the Pages URL on your Mac or phone. It is a **read-only results dashboard**, not the interactive Streamlit app. For interactive manual scanning and trader watchlists, continue using Streamlit locally.

### What to expect

- New research snapshots are **only saved when ESPN confirms a future start time**. If no suitable games are found, the job may succeed with zero new snapshots. It never deliberately records in-play markets.
- The first scheduled run may have no prior results to resolve. Outcomes are checked on later daily runs.
- The model's first 38 walk-forward game predictions had 50% winner accuracy and a worse Brier score than 50/50. It is not validated. The reported estimated edge and hypothetical ROI should **not** guide real-money trades.
- The ESPN API is unofficial; GitHub scheduled runs are not guaranteed to occur at the exact minute. If a run fails, inspect the Actions logs. A failed network request should not create fabricated data.
- GitHub Pages will display up to the most recent 200 snapshots. The CSV retains all snapshots.
- The assumed fee is a flat $0.02 per contract, not an exact Kalshi fee calculation. Market settlement is **not verified** against Kalshi. The outcome is based on ESPN final scores.
- No actual orders, account access, automatic copy trading, or private credentials.

### Local use

The existing Streamlit dashboard is still available:

```
cd ~/Downloads/kalshi_sports_dashboard
source .venv/bin/activate
python -m streamlit run app.py
```

Cloud CSV updates do **not** automatically sync into your local Streamlit `data/` folder. To review the cloud history, use the GitHub Pages site, or download the repository CSV.

### Quick verification

Run `python cloud_job.py --render-only` to generate a local static preview without network access. For a live cloud test, use the GitHub Actions **Run workflow** button.

## Highest Win Probability and Best Value (v0.6 ranking update)
- The local Streamlit NBA markets tab now displays two additional tables.
- **Highest estimated win probability** filters model probabilities to >=75%, then sorts descending. It may legitimately be empty.
- **Best estimated value** ranks by experimental probability minus observed YES ask minus assumed fee, without the 75% filter. These are not verified positive-EV trades.
- The scheduled cloud job saves `data/nba_latest_rankings.json` and publishes both tables to the static GitHub Pages dashboard.
- The model's historical validation was worse than a 50/50 baseline in the user's initial run. Do not interpret estimates as reliable or place trades based solely on these rankings.
- GitHub Pages may publish after the scheduled workflow updates the docs folder. No automatic real-money trading.
- Upload all project files including `ranking_views.py` and `.github/workflows/daily-research.yml` directly to the root of your repository. Do not upload `.venv` or `__pycache__`.
