"""Scheduled, read-only NBA research capture and static dashboard publication."""
import argparse
import csv
import html
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

from auto_model import ranking, parse_teams, _get_day
from research_tracker import record, resolve, load, summary
from ranking_views import split_rankings

BASE='https://external-api.kalshi.com/trade-api/v2'
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'/'nba_research_snapshots.csv'
DOCS=ROOT/'docs'/'index.html'
RANKINGS=ROOT/'data'/'nba_latest_rankings.json'

def get_json(url):
    req=Request(url,headers={'User-Agent':'KalshiSportsEdgeResearch/0.6','Accept':'application/json'})
    with urlopen(req,timeout=25) as response:
        return json.load(response)

def price(m):
    value=m.get('yes_ask_dollars')
    if value not in (None,''):
        return float(value)
    value=m.get('yes_ask')
    return float(value)/100 if value is not None else None

def markets(limit=80):
    rows=[]
    cursor=None
    for _ in range(5):
        params={'series_ticker':'KXNBAGAME','status':'open','limit':100}
        if cursor: params['cursor']=cursor
        response=get_json(BASE+'/events?'+urlencode(params))
        for e in response.get('events',[]):
            ticker=e.get('event_ticker','')
            if not ticker: continue
            try:
                detail=get_json(BASE+'/events/'+quote(ticker,safe='')+'?with_nested_markets=true')
                ms=detail.get('markets') or detail.get('event',{}).get('markets',[])
                for m in ms:
                    if m.get('status') not in ('active','open',None): continue
                    ask=price(m)
                    if ask is None: continue
                    rows.append({'ticker':m.get('ticker',''),'event':e.get('title',''),
                                 'title':m.get('title',''),'yes_ask':ask})
            except Exception as exc:
                print('Skipped event',ticker,type(exc).__name__)
            if len(rows)>=limit: return rows
        cursor=response.get('cursor')
        if not cursor: break
    return rows

def safe_pregame(rows,now):
    """Only select games with an ESPN scheduled start >60 min ahead.
    If ESPN schedule cannot be confirmed, skip rather than capture in-play prices.
    """
    days=set()
    from research_tracker import game_date_from_ticker
    for r in rows:
        d=game_date_from_ticker(r.get('ticker',''))
        if d: days.add(d)
    starts={}
    for d in sorted(days):
        try:
            from datetime import date
            day=date.fromisoformat(d)
            # ESPN scoreboard returns future events with start time.
            url='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?'+urlencode({'dates':day.strftime('%Y%m%d')})
            data=get_json(url)
            for e in data.get('events',[]):
                for comp in e.get('competitions',[]):
                    ts=comp.get('competitors',[])
                    if len(ts)!=2: continue
                    teams=frozenset(t.get('team',{}).get('abbreviation','') for t in ts)
                    from auto_model import ALIASES
                    teams=frozenset(ALIASES.get(t,t) for t in teams)
                    try: start=datetime.fromisoformat(e['date'].replace('Z','+00:00'))
                    except (KeyError,ValueError): continue
                    if not e.get('status',{}).get('type',{}).get('completed',False):
                        starts[(d,teams)]=start
        except Exception as exc:
            print('Schedule unavailable for',d,type(exc).__name__)
    valid=[]
    for r in rows:
        teams=parse_teams(r.get('ticker',''))
        day=game_date_from_ticker(r.get('ticker',''))
        start=starts.get((day,frozenset(teams))) if teams else None
        if start and start>now+timedelta(minutes=60): valid.append(r)
    return valid

def save_rankings(candidates, now, diagnostics=None):
    high, value=split_rankings(candidates,minimum_probability=.75,limit=10)
    payload={'generated_utc':now.isoformat(),'minimum_probability':.75,
             'highest_win_probability':high,'best_estimated_value':value,
             'diagnostics':diagnostics or {}}
    RANKINGS.parent.mkdir(parents=True,exist_ok=True)
    RANKINGS.write_text(json.dumps(payload,indent=2),encoding='utf-8')

def render(status=''):
    records=load(DATA)
    try: rankings=json.loads(RANKINGS.read_text(encoding='utf-8'))
    except (FileNotFoundError,ValueError): rankings={}
    def rankings_table(rows):
        if not rows: return '<p class="muted">No eligible candidates in this ranking.</p>'
        fields=[('matchup','Matchup'),('selection','Selection'),('heuristic probability','Model estimate'),
                ('YES ask','YES ask'),('estimated edge after assumed fee','Model-estimated edge')]
        headers=''.join('<th>'+html.escape(label)+'</th>' for _,label in fields)
        cells=''.join('<tr>'+''.join('<td>'+html.escape(str(row.get(k,'')))+'</td>' for k,_ in fields)+'</tr>' for row in rows)
        return '<div class="scroll"><table><thead><tr>'+headers+'</tr></thead><tbody>'+cells+'</tbody></table></div>'
    rank_date=html.escape(str(rankings.get('generated_utc','No ranking snapshot yet')))
    high_table=rankings_table(rankings.get('highest_win_probability',[]))
    value_table=rankings_table(rankings.get('best_estimated_value',[]))
    stats=summary(records)
    def fmt(x): return html.escape(str(x if x is not None else ''))
    cols=['snapshot_utc','matchup','selection','yes_ask','model_probability','estimated_edge','game_date','status','winning_team','hypothetical_pnl_per_contract']
    table=''.join('<tr>'+''.join('<td>'+fmt(r.get(c,''))+'</td>' for c in cols)+'</tr>' for r in reversed(records[-200:]))
    winrate=f"{stats['win_rate']:.1%}" if stats['win_rate'] is not None else '—'
    roi=f"{stats['hypothetical_roi']:+.1%}" if stats['hypothetical_roi'] is not None else '—'
    latest=fmt(records[-1]['snapshot_utc']) if records else 'No snapshots yet'
    page=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Kalshi Sports Edge — Research Tracker</title><style>
body{{font-family:system-ui,-apple-system,sans-serif;background:#101218;color:#f2f3f6;margin:0;padding:32px;line-height:1.5}}main{{max-width:1400px;margin:auto}}h1{{font-size:2rem}}.muted{{color:#a8b0bd}}.warning{{background:#36331d;padding:16px;border-radius:10px}}.stats{{display:flex;gap:16px;flex-wrap:wrap;margin:25px 0}}.stat{{background:#20242e;padding:16px 25px;border-radius:10px;min-width:155px}}.num{{font-size:1.7rem;font-weight:700}}.scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:.9rem}}td,th{{border-bottom:1px solid #333a46;padding:10px;text-align:left;white-space:nowrap}}th{{background:#262b36}}a{{color:#8cc9ff}}
</style></head><body><main><h1>🏀 Kalshi Sports Edge — Cloud Research Tracker</h1><p class="muted">Daily research snapshots and ESPN outcome checks. Last saved snapshot: {latest}</p><p class="warning">Research only. The NBA Elo model has not demonstrated predictive or trading profitability. Hypothetical P/L assumes one YES contract at the observed ask plus a flat assumed fee; it is NOT verified fill, settlement, or realized profit. Public GitHub repositories expose this data.</p><h2>🎯 Highest estimated win probability (75% minimum)</h2><p class="muted">Experimental probabilities, not verified win rates. No qualifying selections is a valid outcome.</p>{high_table}<h2>💰 Best model-estimated value after assumed fees</h2><p class="muted">These differences are not verified profitable edges. Prices can change. Last ranking snapshot: {rank_date}.</p>{value_table}<h2>Research snapshot performance</h2><section class="stats"><div class="stat">Snapshots<div class="num">{stats['snapshots']}</div></div><div class="stat">Resolved<div class="num">{stats['resolved']}</div></div><div class="stat">Win rate<div class="num">{winrate}</div></div><div class="stat">Hypothetical P/L<div class="num">${stats['hypothetical_pnl']:+.2f}</div></div><div class="stat">Hypothetical ROI<div class="num">{roi}</div></div></section><p class="muted">{fmt(status)}</p><div class="scroll"><table><thead><tr>{''.join('<th>'+fmt(c.replace('_',' ').title())+'</th>' for c in cols)}</tr></thead><tbody>{table}</tbody></table></div><p class="muted">Snapshot timestamps are UTC. Outcomes are ESPN final scores, not Kalshi settlements. Prices are observed quotes, not guaranteed executions. Data is only updated when the scheduled workflow runs.</p></main></body></html>'''
    DOCS.parent.mkdir(parents=True,exist_ok=True)
    DOCS.write_text(page,encoding='utf-8')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--render-only',action='store_true')
    args=parser.parse_args()
    if args.render_only:
        render('Static preview; no network requests were made')
        return
    now=datetime.now(timezone.utc)
    updated,errors=resolve(DATA,utc_now=now)
    print('Resolved:',updated,'Errors:',errors)
    # Never fabricate a snapshot when API or schedule verification fails.
    all_rows=markets()
    candidates=safe_pregame(all_rows,now)
    print('Market rows:',len(all_rows),'Verified pregame rows:',len(candidates))
    saved=0
    if not candidates:
        save_rankings([],now)
    if candidates:
        ranked,games,diagnostics=ranking(candidates,fee=.02)
        print('History:',games,'Diagnostics:',diagnostics)
        if diagnostics['games']>=20:
            save_rankings(ranked,now,diagnostics)
            for r in ranked: r['assumed_fee']=.02
            saved=record(DATA,ranked,limit=10,utc_now=now)
        else:
            save_rankings([],now,diagnostics)
            print('Skipping snapshots: insufficient walk-forward validation data')
    print('Saved:',saved)
    render(f'Latest job: {now:%Y-%m-%d %H:%M UTC} · New snapshots: {saved} · Outcomes updated: {updated} · Score request errors: {len(errors)}')

if __name__=='__main__': main()
