"""Local, read-only research snapshot and NBA game outcome tracker.

Tracks YES buys at the observed ask. No actual fills or trades are assumed.
Game winners are sourced from ESPN, NOT Kalshi market settlement.
"""
import csv
from datetime import datetime, timezone
from pathlib import Path
from auto_model import _get_day, parse_teams

FIELDS=['snapshot_utc','ticker','matchup','selection','yes_ask','model_probability',
        'assumed_fee','estimated_edge','game_date','status','winning_team',
        'hypothetical_pnl_per_contract','resolution_note']
def game_date_from_ticker(ticker):
    try:
        # KXNBAGAME-26OCT28SASUTA-UTA
        stamp=ticker.split('-')[1][:7]
        return datetime.strptime(stamp,'%y%b%d').date().isoformat()
    except (ValueError,IndexError,AttributeError):
        return ''

def load(path):
    if not Path(path).exists(): return []
    with open(path,newline='',encoding='utf-8') as f:
        return list(csv.DictReader(f))

def save(path, rows):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    with tmp.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS,extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)

def record(path, candidates, limit=10, utc_now=None):
    """One snapshot per UTC day per ticker. Never overwrite original observed prices."""
    existing=load(path)
    moment=utc_now or datetime.now(timezone.utc)
    stamp=moment.strftime('%Y-%m-%d %H:%M:%S UTC')
    day=moment.date().isoformat()
    keys={(r['snapshot_utc'][:10],r['ticker']) for r in existing}
    added=0
    for r in candidates[:limit]:
        ticker=r.get('ticker','')
        ask=r.get('YES ask')
        p=r.get('heuristic probability')
        if not ticker or ask is None or p is None or (day,ticker) in keys: continue
        existing.append({'snapshot_utc':stamp,'ticker':ticker,'matchup':r.get('matchup',''),
            'selection':r.get('selection',''),'yes_ask':ask,
            'model_probability':p,'assumed_fee':r.get('assumed_fee',.02),
            'estimated_edge':r.get('estimated edge after assumed fee',''),
            'game_date':game_date_from_ticker(ticker),'status':'PENDING',
            'winning_team':'','hypothetical_pnl_per_contract':'',
            'resolution_note':'Game outcome pending; Kalshi settlement not checked'})
        keys.add((day,ticker))
        added+=1
    if added: save(path,existing)
    return added

def resolve(path, utc_now=None, day_fetcher=None):
    """Mark game outcome using ESPN scores, only for dates before current UTC date.
    No assumption that ESPN game outcome equals Kalshi market settlement.
    """
    today=(utc_now or datetime.now(timezone.utc)).date()
    rows=load(path)
    fetcher=day_fetcher or _get_day
    dates=set()
    from datetime import date
    for r in rows:
        if r['status']!='PENDING' or not r['game_date']: continue
        try:
            d=date.fromisoformat(r['game_date'])
            if d<today: dates.add(d)
        except ValueError: continue
    results={}
    errors=[]
    for d in sorted(dates):
        try:
            results[d]=fetcher(d)
        except Exception as exc:
            errors.append(f'{d.isoformat()}: {type(exc).__name__}')
    updated=0
    for r in rows:
        if r['status']!='PENDING' or not r['game_date']: continue
        try: d=date.fromisoformat(r['game_date'])
        except ValueError: continue
        if d not in results: continue
        teams=parse_teams(r['ticker'])
        if not teams: continue
        for _,home,away,hs,ass in results[d]:
            if set(teams)!={home,away}: continue
            winner=home if hs>ass else away
            selection=r['ticker'].split('-')[-1]
            if selection not in teams: break
            win=selection==winner
            ask=float(r['yes_ask'])
            fee=float(r['assumed_fee'])
            # Hypothetical gross payout $1 on a winning YES, $0 otherwise.
            pnl=(1.0 if win else 0.0)-ask-fee
            r['status']='WIN' if win else 'LOSS'
            r['winning_team']=winner
            r['hypothetical_pnl_per_contract']=f'{pnl:.4f}'
            r['resolution_note']='ESPN final score only; NOT verified Kalshi settlement or executable fill'
            updated+=1
            break
    if updated: save(path,rows)
    return updated,errors

def summary(rows):
    resolved=[r for r in rows if r.get('status') in ('WIN','LOSS')]
    n=len(resolved)
    total=sum(float(r['hypothetical_pnl_per_contract']) for r in resolved)
    cost=sum(float(r['yes_ask'])+float(r['assumed_fee']) for r in resolved)
    return {'snapshots':len(rows),'resolved':n,'wins':sum(r['status']=='WIN' for r in resolved),
        'win_rate':(sum(r['status']=='WIN' for r in resolved)/n) if n else None,
        'hypothetical_pnl':total,'hypothetical_roi':total/cost if cost else None}
