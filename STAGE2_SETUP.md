# Stage 2 — NBA player game-log collection

This upgrade adds `nba_data_sync.py`, the Stage 1 `nba_prop_engine.py`, tests, and a new step to the existing daily GitHub Actions workflow. The existing Combo Lab and dashboard HTML files are unchanged.

## How it works

The daily workflow requests ESPN NBA scoreboard results for the previous 35 **completed** calendar days, fetches box scores for newly discovered completed games, and writes `data/nba_player_game_logs.csv` with player name, ESPN ID, team, game date, points, rebounds, assists, and made threes. Existing game records are retained and duplicates are skipped. A failed fetch is logged, not fabricated. The default lookback is **not** a full season and does not guarantee enough games per player for an estimate. The public ESPN endpoint is unofficial and may change or rate-limit requests.

## Run manually

From the repository root, run `python nba_data_sync.py --days 35`, then `python -m unittest discover -s tests -p 'test_*.py' -v`. To compute research estimates, create a JSON list like `[{"player":"Example Player","stat":"points","threshold":20}]` and run `python nba_prop_engine.py --games data/nba_player_game_logs.csv --requests requests.json --as-of 2026-11-09 --output data/nba_prop_research.json`. Only game logs strictly **before** the as-of date count.

## GitHub setup

Upload the changed repository files to the same paths in your repo, preserving `.github/workflows/daily-research.yml`. Open Actions > Daily NBA research > Run workflow. Once it finishes, check `data/nba_player_game_logs.csv` for populated player records. The existing game-winner research step remains separate.

## Limits

This is **historical data collection only**. The CSV is public in your GitHub repo. No player-prop projections, injury checks, live market prices, calibrated probabilities, correlation estimates, or profitable combo recommendations are implemented. The Combo Lab still does not auto-populate prop probabilities. No trades are placed.
