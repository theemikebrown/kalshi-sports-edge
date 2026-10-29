"""Conservative audit of timestamped research snapshots, NOT a fill/settlement backtest."""
from datetime import datetime, timezone

def audit(rows):
    # Count at most one observation per contract to avoid multiple-day double counting.
    first={}
    for r in sorted(rows,key=lambda x:x.get('snapshot_utc','')):
        ticker=r.get('ticker','')
        if ticker and ticker not in first: first[ticker]=r
    resolved=[]; rejected=0
    for r in first.values():
        if r.get('status') not in ('WIN','LOSS'): continue
        try:
            p=float(r['model_probability']); ask=float(r['yes_ask']); fee=float(r['assumed_fee'])
            observed=datetime.strptime(r['snapshot_utc'],'%Y-%m-%d %H:%M:%S UTC').replace(tzinfo=timezone.utc)
            game=datetime.strptime(r['game_date'],'%Y-%m-%d').replace(tzinfo=timezone.utc)
            if not (0<=p<=1 and 0<ask<1 and fee>=0 and observed<game.replace(hour=23,minute=59)):
                rejected+=1; continue
            y=int(r['status']=='WIN')
            resolved.append((p,ask,fee,y))
        except (ValueError,KeyError,TypeError): rejected+=1
    n=len(resolved)
    if not n:
        return {'contracts':0,'status':'NO RESOLVED CONTRACTS','rejected':rejected,'model_brier':None,'market_brier':None,'hypothetical_roi':None,'hypothetical_pnl':None,'model_brier_advantage':None,'model_wins_brier':None}
    cost=sum(a+f for _,a,f,_ in resolved)
    return {'contracts':n,'status':'PRELIMINARY — OBSERVED ASK ONLY' if n>=100 else 'INSUFFICIENT PRICE HISTORY (<100 CONTRACTS)',
        'rejected':rejected,'model_brier':sum((p-y)**2 for p,_,_,y in resolved)/n,
        'market_brier':sum((a-y)**2 for _,a,_,y in resolved)/n,
        'hypothetical_pnl':sum(y-a-f for _,a,f,y in resolved),
        'hypothetical_roi':sum(y-a-f for _,a,f,y in resolved)/cost if cost else None,
        'model_brier_advantage':sum((a-y)**2-(p-y)**2 for p,a,_,y in resolved)/n,
        'model_wins_brier':sum((p-y)**2 for p,_,_,y in resolved)<sum((a-y)**2 for _,a,_,y in resolved)}
