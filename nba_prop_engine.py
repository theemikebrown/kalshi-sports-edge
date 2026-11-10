"""Offline, transparent NBA player-prop research estimates.

Input CSV columns: player,game_date,pts,reb,ast,fg3m (case-insensitive).
This is NOT a calibrated forecast, live feed, or executable Kalshi quote.
"""
import argparse
import csv
import json
import math
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

STAT_COLS = {'points':'pts','rebounds':'reb','assists':'ast','threes':'fg3m'}

def wilson_interval(successes, n, z=1.96):
    if n == 0: return (None, None)
    p = successes/n
    center = (p+z*z/(2*n))/(1+z*z/n)
    spread = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/(1+z*z/n)
    return (max(0,center-spread), min(1,center+spread))

def load_games(path, as_of):
    grouped=defaultdict(list)
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames: raise ValueError('CSV is empty')
        columns={c.strip().lower():c for c in reader.fieldnames}
        required={'player','game_date','pts','reb','ast','fg3m'}
        missing=required-set(columns)
        if missing: raise ValueError('Missing CSV columns: '+', '.join(sorted(missing)))
        for row in reader:
            try:
                day=date.fromisoformat(row[columns['game_date']].strip()[:10])
                if day>=as_of: continue # strict pregame data cutoff
                name=row[columns['player']].strip()
                if not name: continue
                stats={k:float(row[columns[k]]) for k in ('pts','reb','ast','fg3m')}
                if any(not math.isfinite(v) or v<0 for v in stats.values()):continue
                grouped[name].append((day,stats))
            except (ValueError,TypeError,KeyError):continue
    for name in grouped:grouped[name].sort(key=lambda x:x[0],reverse=True)
    return grouped

def estimate(games, player, stat, threshold, window=20):
    if stat not in STAT_COLS:raise ValueError('Unknown stat')
    if window<1:raise ValueError('Window must be positive')
    values=[g[1][STAT_COLS[stat]] for g in games.get(player,[])[:window]]
    n=len(values)
    if n<10:return {'player':player,'stat':stat,'threshold':threshold,'games':n,'status':'INSUFFICIENT_DATA','probability':None}
    hits=sum(v>=threshold for v in values)
    low,high=wilson_interval(hits,n)
    return {'player':player,'stat':stat,'threshold':threshold,'games':n,'hits':hits,'mean':round(sum(values)/n,2),'probability':round(hits/n,4),'ci95':[round(low,4),round(high,4)],'status':'UNVALIDATED_EMPIRICAL','note':'Historical hit rate only; not a calibrated forecast; excludes injury, opponent, minutes and correlation adjustments.'}

def main():
    parser=argparse.ArgumentParser(description='Build preliminary NBA prop hit-rate research from historical game logs')
    parser.add_argument('--games',required=True,help='CSV containing historical NBA player game logs')
    parser.add_argument('--requests',required=True,help='JSON list of {player,stat,threshold} requests')
    parser.add_argument('--as-of',default=date.today().isoformat(),help='YYYY-MM-DD, only earlier games used')
    parser.add_argument('--output',default='data/nba_prop_research.json')
    args=parser.parse_args()
    cutoff=date.fromisoformat(args.as_of)
    games=load_games(args.games,cutoff)
    requests=json.loads(Path(args.requests).read_text(encoding='utf-8'))
    if not isinstance(requests,list):raise ValueError('Requests must be a JSON list')
    results=[estimate(games,str(r['player']),str(r['stat']).lower(),float(r['threshold'])) for r in requests]
    payload={'as_of':cutoff.isoformat(),'model':'unvalidated empirical hit-rate v1','source':'user-supplied historical CSV','results':results,'live_market_prices':False,'validated_forecasts':False}
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print('Wrote',out,'with',len(results),'estimates')

if __name__=='__main__':main()
