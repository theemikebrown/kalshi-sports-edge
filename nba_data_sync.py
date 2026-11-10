"""Incremental ESPN NBA final-game box-score collector; no authentication or trades."""
import argparse
import csv
import json
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

FIELDS=['game_id','player_id','player','game_date','team','pts','reb','ast','fg3m']
BASE='https://site.api.espn.com/apis/site/v2/sports/basketball/nba'

def get_json(url):
    req=Request(url,headers={'User-Agent':'KalshiSportsEdgeResearch/1.0 (public NBA box score research)'})
    with urlopen(req,timeout=20) as response:return json.load(response)

def final_game_ids(scoreboard):
    ids=[]
    for event in scoreboard.get('events',[]):
        comps=event.get('competitions') or []
        if comps and comps[0].get('status',{}).get('type',{}).get('completed') is True:
            ids.append(str(event['id']))
    return ids

def parse_summary(summary,game_id,day):
    rows=[]
    for team in summary.get('boxscore',{}).get('players',[]):
        team_name=team.get('team',{}).get('abbreviation','')
        for group in team.get('statistics',[]):
            labels=[str(s).upper() for s in group.get('labels',[])]
            if not all(k in labels for k in ('PTS','REB','AST','3PT')):continue
            ix={k:labels.index(k) for k in ('PTS','REB','AST','3PT')}
            for entry in group.get('athletes',[]):
                if entry.get('didNotPlay') or entry.get('inactive'):continue
                stats=entry.get('stats') or []
                try:
                    pts=int(stats[ix['PTS']]);reb=int(stats[ix['REB']]);ast=int(stats[ix['AST']]);fg3m=int(str(stats[ix['3PT']]).split('-')[0])
                    if min(pts,reb,ast,fg3m)<0:continue
                    athlete=entry.get('athlete',{})
                    player=athlete.get('displayName','').strip()
                    if not player:continue
                    rows.append(dict(game_id=game_id,player_id=str(athlete.get('id','')),player=player,game_date=day.isoformat(),team=team_name,pts=pts,reb=reb,ast=ast,fg3m=fg3m))
                except (ValueError,TypeError,IndexError):continue
    return rows

def load_existing(path):
    if not path.exists():return {}
    with path.open(newline='',encoding='utf-8') as f:
        reader=csv.DictReader(f)
        if not set(FIELDS).issubset(reader.fieldnames or []):raise ValueError('Existing game log has incompatible columns')
        return {(r['game_id'],r['player_id']):r for r in reader}

def sync(path,days=35,as_of=None,delay=0.1):
    today=as_of or date.today()
    existing=load_existing(path)
    known_games={r['game_id'] for r in existing.values()}
    failed=[];new_games=0;new_rows=0
    for offset in range(days,0,-1):
        day=today-timedelta(days=offset)
        try:
            board=get_json(BASE+'/scoreboard?'+urlencode({'dates':day.strftime('%Y%m%d'),'limit':100}))
            for game_id in final_game_ids(board):
                if game_id in known_games:continue
                try:
                    summary=get_json(BASE+'/summary?'+urlencode({'event':game_id}))
                    rows=parse_summary(summary,game_id,day)
                    if not rows:raise ValueError('No supported player box score rows')
                    for r in rows:
                        key=(r['game_id'],r['player_id'])
                        if key not in existing:new_rows+=1
                        existing[key]=r
                    known_games.add(game_id);new_games+=1
                except Exception as exc:failed.append(f'{day} game {game_id}: {exc}')
                time.sleep(delay)
        except Exception as exc:failed.append(f'{day} scoreboard: {exc}')
        time.sleep(delay)
    if not existing:
        raise RuntimeError('No valid NBA player data collected; refusing to replace data with an empty file. '+('; '.join(failed[:3])))
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    with temp.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader()
        writer.writerows(sorted(existing.values(),key=lambda r:(r['game_date'],r['game_id'],r['player_id'])))
    temp.replace(path)
    return {'new_games':new_games,'new_player_rows':new_rows,'total_player_rows':len(existing),'failures':failed}

def main():
    p=argparse.ArgumentParser();p.add_argument('--days',type=int,default=35);p.add_argument('--as-of');p.add_argument('--output',default='data/nba_player_game_logs.csv');args=p.parse_args()
    if not 1<=args.days<=120:raise ValueError('days must be 1–120')
    result=sync(Path(args.output),args.days,date.fromisoformat(args.as_of) if args.as_of else None)
    print(json.dumps(result,indent=2))
    if result['failures']:print('Warning: incomplete ESPN coverage; inspect failed dates before using estimates.')

if __name__=='__main__':main()
