# NBA probability engine — first working research module

This is a **historical player-prop hit-rate calculator**, not a validated predictive model. It does **not** pull today's schedule, injury reports, live Kalshi prices, or player game logs automatically. It does not produce trade recommendations.

## Inputs

1. A legitimate, licensed or otherwise permitted historical player-game CSV with the columns `player,game_date,pts,reb,ast,fg3m`. Dates use `YYYY-MM-DD`; each row is one completed game.
2. A JSON file of requested thresholds, for example:

```json
[{"player":"Example Player","stat":"points","threshold":25},{"player":"Example Player","stat":"assists","threshold":5}]
```

## Run

```bash
python nba_prop_engine.py --games path/to/player_games.csv --requests path/to/requests.json --as-of 2026-11-09 --output data/nba_prop_research.json
python -m unittest discover -s tests -p 'test_*.py' -v
```

The engine strictly excludes games on or after the `--as-of` date to avoid look-ahead bias. It calculates the last 20 eligible game hit rate, a 95% Wilson uncertainty interval, and sample size. Under 10 games yields `INSUFFICIENT_DATA`. No data is invented. It does not automatically alter `docs/combo-lab.html`, `docs/index.html`, or the existing daily research workflow.

## Next required integration

- Obtain permitted historical game logs and verified current player/game availability.
- Join today's NBA matchups to players and current Kalshi market tickers, including accurate market rules and real-time prices.
- Calibrate probability estimates on held-out games, account for injury, minutes, opponent and dependence among legs; evaluate calibration and performance.
- Compare *verified executable combo quotes* against calibrated joint probabilities. Without those, a claim of profitable combos is unsupported.

This staged release is safe to install without affecting the running dashboard.
