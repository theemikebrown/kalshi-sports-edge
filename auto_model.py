"""Exploratory NBA Elo with prequential validation and reliability diagnostics. NOT a trading signal."""
import json, math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ESPN="https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
ALIASES={"GS":"GSW","NY":"NYK","SA":"SAS","NO":"NOP","UTAH":"UTA","WSH":"WAS","PHO":"PHX","BKN":"BKN"}
HOME_ADVANTAGE=65.0
K=20.0
def _norm(v): return ALIASES.get(v,v)
def _get_day(day):
    url=ESPN+"?"+urlencode({"dates":day.strftime("%Y%m%d")})
    with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"}),timeout=12) as r:
        data=json.load(r)
    out=[]
    for e in data.get("events",[]):
        if not e.get("status",{}).get("type",{}).get("completed"): continue
        for comp in e.get("competitions",[]):
            try:
                ts=comp["competitors"]
                h=next(t for t in ts if t["homeAway"]=="home")
                a=next(t for t in ts if t["homeAway"]=="away")
                hs,ass=int(h["score"]),int(a["score"])
                if hs==ass: continue
                out.append((e.get("date",day.isoformat()),_norm(h["team"]["abbreviation"]),_norm(a["team"]["abbreviation"]),hs,ass))
            except (KeyError,StopIteration,ValueError,TypeError): continue
    return out

def recent_results(start,end):
    """Fetch day-by-day; avoid ESPN range HTTP 400. Returns (games,failed_dates)."""
    day=start.date() if isinstance(start,datetime) else start
    last=end.date() if isinstance(end,datetime) else end
    results={}
    failures=[]
    while day<=last:
        try:
            for g in _get_day(day):
                results[(g[0],g[1],g[2])]=g
        except Exception as exc:
            failures.append(f"{day.isoformat()}: {type(exc).__name__}")
        day+=timedelta(days=1)
    return sorted(results.values()),failures

def prob(elo,home,away,venue=True):
    adv=HOME_ADVANTAGE if venue else 0
    return 1/(1+10**((elo[away]-elo[home]-adv)/400))

def fit_and_backtest(games):
    """Chronological one-step-ahead evaluation; no training on future games."""
    elo=defaultdict(lambda:1500.)
    played=defaultdict(int)
    preds=[]
    last_season=None
    for date,home,away,hs,ass in sorted(games):
        season=(int(date[:4])+1) if int(date[5:7])>=7 else int(date[:4])
        if last_season is not None and season!=last_season:
            for team in list(elo): elo[team]=1500+(elo[team]-1500)*0.65
        last_season=season
        p=prob(elo,home,away)
        if played[home]>=5 and played[away]>=5:
            y=1 if hs>ass else 0
            # Apply the SAME fixed shrinkage used for future predictions, using only prior games.
            n=min(played[home],played[away])
            conservative_p=.5+(p-.5)*n/(n+25)
            preds.append((conservative_p,y))
        outcome=1 if hs>ass else 0
        change=K*(outcome-p)
        elo[home]+=change
        elo[away]-=change
        played[home]+=1
        played[away]+=1
    return elo,played,preds

def calibration_bins(preds):
    """Descriptive out-of-sample reliability bins; no fitted calibration on test outcomes."""
    bins=[]
    for lo,hi in ((0,.4),(.4,.5),(.5,.6),(.6,1.000001)):
        subset=[(p,y) for p,y in preds if lo<=p<hi]
        bins.append({"range":f"{lo:.0%}–{min(hi,1):.0%}","count":len(subset),
                     "mean_prediction":round(sum(p for p,_ in subset)/len(subset),3) if subset else None,
                     "observed_rate":round(sum(y for _,y in subset)/len(subset),3) if subset else None})
    return bins

def wilson_interval(wins, n, z=1.96):
    """95% Wilson score interval for observed classification accuracy, not trade win probability."""
    if not n: return None
    phat=wins/n
    denom=1+z*z/n
    center=(phat+z*z/(2*n))/denom
    half=z*math.sqrt((phat*(1-phat)+z*z/(4*n))/n)/denom
    return [round(max(0,center-half),3),round(min(1,center+half),3)]

def validation(preds):
    if not preds: return {"games":0,"brier":None,"accuracy":None,"baseline_brier":None}
    n=len(preds)
    return {"games":n,
            "brier":sum((p-y)**2 for p,y in preds)/n,
            "accuracy":sum((p>=.5)==bool(y) for p,y in preds)/n,
            "baseline_brier":sum((.5-y)**2 for _,y in preds)/n,
            "calibration_bins":calibration_bins(preds),
            "accuracy_95pct_wilson_interval":wilson_interval(sum((p>=.5)==bool(y) for p,y in preds),n),
            "home_team_baseline_accuracy":None,
            "calibration_note":"Out-of-sample descriptive bins; not enough observations for reliable probability calibration."}

def parse_teams(ticker):
    try:
        part=ticker.split("-")[1][7:]
        return (part[:3],part[3:]) if len(part)==6 else None
    except (IndexError,TypeError): return None

def upcoming_context(rows, games):
    """Map ESPN scheduled games to known home/away teams and rest, if verifiable."""
    from research_tracker import game_date_from_ticker
    last={}
    for date,home,away,_,_ in games:
        try: d=datetime.fromisoformat(date.replace('Z','+00:00')).date()
        except ValueError: continue
        for t in (home,away): last[t]=max(d,last.get(t,d))
    dates=set(filter(None,(game_date_from_ticker(r.get('ticker','')) for r in rows)))
    context={}
    for day in sorted(dates):
        try:
            url=ESPN+'?'+urlencode({'dates':day.replace('-','')})
            with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=12) as resp: data=json.load(resp)
            for event in data.get('events',[]):
                for comp in event.get('competitions',[]):
                    teams=comp.get('competitors',[])
                    if len(teams)!=2: continue
                    home=next((x for x in teams if x.get('homeAway')=='home'),None)
                    away=next((x for x in teams if x.get('homeAway')=='away'),None)
                    if not home or not away: continue
                    h=_norm(home.get('team',{}).get('abbreviation',''))
                    a=_norm(away.get('team',{}).get('abbreviation',''))
                    if h and a:
                        d=datetime.fromisoformat(day).date()
                        rest={t:max(0,(d-last[t]).days-1) if t in last else None for t in (h,a)}
                        context[(day,frozenset((h,a)))]=(h,a,rest)
        except Exception: continue
    return context

def confidence(metrics):
    """Gate model outputs by sample size and proper scoring against 50/50 baseline."""
    n=metrics.get('games',0)
    b=metrics.get('brier')
    base=metrics.get('baseline_brier')
    if n<100: return 'INSUFFICIENT VALIDATION (<100 games)'
    if b is None or base is None or b>=base: return 'FAILED 50/50 BASELINE'
    return 'PRELIMINARY ONLY — NO PRICE BACKTEST'

def ranking(rows,fee,minimum_games=5):
    """Returns ranked exploratory candidates, game count, and validation metadata."""
    end=datetime.now(timezone.utc)
    # Longer training window for prior-season strength. Daily API fetches can take time.
    games,failures=recent_results(end-timedelta(days=210),end)
    if len(failures)>20:
        raise RuntimeError(f"Historical data unavailable for {len(failures)} dates; cannot generate trustworthy rankings")
    elo,played,preds=fit_and_backtest(games)
    metrics=validation(preds)
    metrics["failed_dates"]=len(failures)
    metrics["historical_lookback_days"]=210
    metrics["warning"]="No fitted calibration, injuries or lineup adjustments; rest is descriptive. No historical execution-price backtest. A longer lookback does not guarantee better forecasts."
    metrics['model_reliability']=confidence(metrics)
    metrics["model_version"]="0.9"
    metrics["validation_method"]="Chronological one-step-ahead, with fixed conservative shrinkage applied to predictions"
    metrics['validation_note']='A better Brier score is not proof of tradable edge; no historical Kalshi quotes or actual fills were tested.'
    schedule=upcoming_context(rows,games)
    candidates=[]
    for row in rows:
        teams=parse_teams(row.get("ticker",""))
        if not teams: continue
        first,second=teams
        n=min(played[first],played[second])
        if n<minimum_games: continue
        # Kalshi ticker encodes two teams but not home venue. Neutral probability only.
        from research_tracker import game_date_from_ticker
        day=game_date_from_ticker(row.get('ticker',''))
        ctx=schedule.get((day,frozenset((first,second))))
        if ctx:
            home,away,rest=ctx
            p=prob(elo,home,away,venue=True)
            # No invented injury or lineup effects. Rest is descriptive only until validated.
            if first!=home: p=1-p
            venue_label='ESPN-confirmed home court'
            rest_label=f'{first}: {rest.get(first)}; {second}: {rest.get(second)}'
        else:
            p=prob(elo,first,second,venue=False)
            venue_label='Unknown venue — neutral assumption'
            rest_label='Unknown'
        # Conservative shrinkage for limited history; not empirically calibrated.
        p=.5+(p-.5)*n/(n+25)
        selected=row["ticker"].split("-")[-1]
        if selected==second: p=1-p
        elif selected!=first: continue
        ask=row.get("yes_ask")
        if ask is None or not 0<float(ask)<1: continue
        edge=p-float(ask)-fee
        # This is a reliability status, NOT the probability that this specific pick wins.
        if metrics['games']<100 or metrics.get('brier') is None or metrics['brier']>=metrics['baseline_brier']:
            quality='UNVALIDATED'
        elif n<15 or metrics['games']<300:
            quality='LIMITED EVIDENCE'
        else:
            quality='PRELIMINARY — NOT TRADE-VALIDATED'
        candidates.append({"model confidence":quality,"matchup":row.get("event",""),"selection":row.get("title",""),
            "ticker":row["ticker"],"YES ask":round(float(ask),3),
            "heuristic probability":round(p,3),"estimated edge after assumed fee":round(edge,3),
            "games per team (min)":n,"venue evidence":venue_label,"rest days":rest_label,
            "model reliability":metrics['model_reliability'],"signal":"EXPLORATORY — NOT VALIDATED"})
    candidates.sort(key=lambda r:r["estimated edge after assumed fee"],reverse=True)
    return candidates,len(games),metrics
