from ranking_views import split_rankings
"""Kalshi Sports Edge — read-only Streamlit research dashboard."""
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen
import streamlit as st
import pandas as pd
from auto_model import ranking
from research_tracker import record, resolve, load as load_snapshots, summary as snapshot_summary

BASE = 'https://external-api.kalshi.com/trade-api/v2'
DATA = Path(__file__).parent / 'data'
DATA.mkdir(exist_ok=True)
WATCH = DATA / 'watchlist.csv'
PAPER = DATA / 'paper_trades.csv'
SNAPSHOTS = DATA / 'nba_research_snapshots.csv'
WATCH_FIELDS = ['trader','public_profile_url','sport','notes','last_checked_utc']
PAPER_FIELDS = ['created_utc','ticker','market','side','entry_price','contracts','model_probability','assumed_fee_per_contract','status','settlement','notes']

def read_rows(path, fields):
    if not path.exists(): return []
    with path.open(newline='',encoding='utf-8') as f: return list(csv.DictReader(f))

def add_row(path, fields, row):
    with path.open('a',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields)
        if f.tell()==0: w.writeheader()
        w.writerow({k:row.get(k,'') for k in fields})

def now(): return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

@st.cache_data(ttl=45,show_spinner=False)
def api(path, params=None):
    url=BASE+path+('?' + urlencode(params) if params else '')
    req=Request(url,headers={'User-Agent':'KalshiSportsEdgeDashboard/0.3','Accept':'application/json'})
    with urlopen(req,timeout=18) as resp: return json.load(resp)

def price(m, side):
    key=side.lower()+'_ask_dollars'
    val=m.get(key)
    if val not in (None,''):
        try: return float(val)
        except (TypeError,ValueError): pass
    # Older API integer cents fields, if present.
    val=m.get(side.lower()+'_ask')
    try: return float(val)/100 if val is not None else None
    except (TypeError,ValueError): return None

def market_rows(series, limit):
    # Event endpoint limits to one sports series; avoids searching arbitrary markets.
    results=[]
    cursor=None
    for _ in range(4):
        params={'series_ticker':series,'status':'open','limit':min(limit,200)}
        if cursor: params['cursor']=cursor
        data=api('/events',params)
        events=data.get('events',[])
        for event in events:
            event_ticker=event.get('event_ticker','')
            try:
                detail=api('/events/'+quote(event_ticker,safe=''),{'with_nested_markets':'true'})
                markets=detail.get('markets') or detail.get('event',{}).get('markets',[])
                for m in markets:
                    results.append({'ticker':m.get('ticker',''),'title':m.get('title') or event.get('title',''),
                        'event':event.get('title',''), 'status':m.get('status',''),
                        'yes_ask':price(m,'YES'),'no_ask':price(m,'NO'),
                        'volume':m.get('volume',None)})
            except Exception: continue
            if len(results)>=limit: return results
        cursor=data.get('cursor')
        if not cursor or not events: break
    return results

st.set_page_config(page_title='Kalshi Sports Edge',page_icon='🏀',layout='wide')
st.title('🏀 Kalshi Sports Edge')
st.caption('Read-only NBA market research · Snapshot tracking · Public-trader watchlist · Paper trading · No automatic orders')
st.warning('Research tool only. An experimental NBA Elo model is included, but it is NOT calibrated or verified profitable; no real-time trader-copy feed. Market quotes can change; model probabilities must be independently justified. No profit is guaranteed.',icon='⚠️')
scanner, tracker_tab, traders, paper, about=st.tabs(['🏀 NBA markets','📊 Model tracker','👥 Trader watchlist','🧪 Paper trades','ℹ️ Setup & limitations'])

with scanner:
    left,right=st.columns([1,2])
    with left:
        series=st.text_input('Kalshi sports series ticker',value='KXNBAGAME',help='Kalshi series tickers may change. Find one in the Kalshi market URL or API.')
        max_markets=st.slider('Maximum markets',10,120,40,10)
        fee=st.number_input('Estimated fees per contract ($)',0.0,0.25,0.02,0.005,help='Illustrative placeholder; check actual Kalshi fees.')
        min_edge=st.slider('Minimum net edge to flag (percentage points)',0,30,5)
        refresh=st.button('Refresh live market quotes',type='primary')
        if refresh: api.clear()
    with right:
        st.info('The scanner retrieves public quotes. The automatic ranking below uses a prior-results Elo model with walk-forward diagnostics, **not** a validated trading model. You can still enter your own independent probabilities for paper trades.')
    try:
        with st.spinner('Loading public Kalshi markets…'):
            rows=market_rows(series.strip().upper(),max_markets)
        if not rows:
            st.warning('No markets returned. Confirm that the series ticker exists and currently has open events.')
        else:
            df=pd.DataFrame(rows)
            st.subheader('🏆 Automatic NBA candidate ranking')
            st.caption('Experimental only: up to 120 days of completed ESPN NBA games, season-transition regression, conservative shrinkage, and walk-forward validation. Home court uses confirmed venue; rest is descriptive, not an adjustment. **Do not treat rankings as profitable trade signals.**')
            try:
                with st.spinner('Estimating recent-form probabilities from completed games…'):
                    ranked, games_used, diagnostics = ranking(rows,fee)
                st.caption(f'Historical games loaded: {games_used} · Minimum 5 games per team · Failed date requests: {diagnostics["failed_dates"]}')
                if diagnostics["games"]:
                    st.write(f'**Walk-forward game predictions:** {diagnostics["games"]} · **Brier score:** {diagnostics["brier"]:.3f} (lower is better) · **Winner accuracy:** {diagnostics["accuracy"]:.1%} · **50/50 baseline Brier:** {diagnostics["baseline_brier"]:.3f}')
                else:
                    st.info('Insufficient games for a meaningful walk-forward validation sample.')
                st.caption('These metrics measure game predictions only, not returns from Kalshi trades. No historical execution-price or fee backtest is included.')
                if diagnostics.get('calibration_bins'):
                    st.caption('Descriptive out-of-sample probability bins (small samples; not fitted calibration):')
                    st.dataframe(pd.DataFrame(diagnostics['calibration_bins']),hide_index=True,width='stretch')
                if ranked:
                    top=pd.DataFrame(ranked[:10])
                    st.dataframe(top,hide_index=True,use_container_width=True)
                    st.warning('Model reliability: '+str(diagnostics.get('model_reliability','UNVERIFIED'))+'. Venue evidence is shown where available; rest days are descriptive, not validated predictive adjustments. No historical Kalshi price backtest.')
                    threshold=st.select_slider('Minimum estimated win probability',options=[.60,.65,.70,.75],value=.75,format_func=lambda x:f'{x:.0%}')
                    high_probability, best_value = split_rankings(ranked,minimum_probability=threshold,limit=10)
                    st.subheader(f'🎯 Highest estimated win probability ({threshold:.0%} minimum)')
                    st.caption('Experimental Elo probabilities, not reliable win rates. High probability does not imply positive expected value.')
                    if high_probability:
                        st.dataframe(pd.DataFrame(high_probability),hide_index=True,use_container_width=True)
                    else:
                        st.info(f'No candidates meet the {threshold:.0%} model-estimated probability threshold. The model is not validated.')
                    st.subheader('💰 Best estimated value after assumed fees')
                    st.caption('Ranked by experimental probability minus observed YES ask and assumed fee. These are NOT validated profitable opportunities.')
                    if best_value:
                        st.dataframe(pd.DataFrame(best_value),hide_index=True,use_container_width=True)
                    else:
                        st.info('No eligible candidates.')
                    st.download_button('Export exploratory top 10',top.to_csv(index=False),'nba_exploratory_rankings.csv','text/csv')
                    st.caption('Daily research snapshots are saved locally only when you press the button below; there is no unattended scheduler.')
                    if st.button('Save today’s Top 10 research snapshot'):
                        enriched=[dict(r,assumed_fee=fee) for r in ranked]
                        added=record(SNAPSHOTS,enriched,limit=10)
                        st.success(f'Saved {added} new market snapshots. Same-day duplicate tickers are skipped. No trades placed.')
                    st.warning('Do not treat positive heuristic edge as evidence of real positive expected value. This model has not been backtested or calibrated. Prices can change and fees vary.')
                else:
                    st.info('Not enough completed recent games or matching market quotes to produce credible automatic rankings yet. No picks are fabricated.')
            except Exception as model_exc:
                st.warning(f'Automatic ranking temporarily unavailable: {model_exc}. Live Kalshi quotes remain accessible below.')
            st.subheader('Live Kalshi market quotes')
            st.metric('Markets found',len(df))
            st.dataframe(df,hide_index=True,use_container_width=True)
            st.download_button('Download current quotes CSV',df.to_csv(index=False),'nba_market_quotes.csv','text/csv')
            choices={f"{r['ticker']} — {r['title'][:85]}":r for r in rows if r['ticker']}
            selected=st.selectbox('Analyze one market',list(choices))
            if selected:
                m=choices[selected]
                a,b,c=st.columns(3)
                with a: side=st.selectbox('Side',['YES','NO'])
                with b: p=st.number_input('Your independent probability (%)',min_value=1.0,max_value=99.0,value=50.0,step=1.0)
                with c: qty=st.number_input('Paper contracts',min_value=1,max_value=100000,value=3,step=1)
                ask=m['yes_ask'] if side=='YES' else m['no_ask']
                if ask is None or not 0<ask<1:
                    st.error('No valid executable ask quote for this side. Cannot calculate edge.')
                else:
                    net=(p/100)-ask-fee
                    roi=net/(ask+fee)
                    st.write(f'**Ask:** ${ask:.3f} · **Estimated net edge:** {net:+.3f} per contract · **Estimated ROI:** {roi:+.1%} · **Paper cost incl. assumed fees:** ${(ask+fee)*qty:.2f}')
                    if net >= min_edge/100: st.success('Research flag: estimated edge meets your threshold. Not a trade recommendation.')
                    else: st.info('Estimated edge below your threshold.')
                    if st.button('Add to paper-trade log'):
                        add_row(PAPER,PAPER_FIELDS,{'created_utc':now(),'ticker':m['ticker'],'market':m['title'],'side':side,
                            'entry_price':ask,'contracts':qty,'model_probability':p/100,
                            'assumed_fee_per_contract':fee,'status':'OPEN','settlement':'','notes':'Manual independent estimate'})
                        st.success('Saved to local paper-trade log. No real order submitted.')
    except Exception as exc:
        st.error(f'Could not retrieve Kalshi markets: {exc}')
        st.caption('Check your internet connection, API availability, or the sports series ticker.')


with tracker_tab:
    st.subheader('📊 NBA research snapshot tracker')
    st.write('Record the observed YES ask and model probability at a point in time. After games finish, compare outcomes with hypothetical one-contract YES purchases. **This is not a backtest of actual fills or Kalshi settlement.**')
    if st.button('Check completed NBA game outcomes'):
        with st.spinner('Checking ESPN final scores for pending past games…'):
            changed, errors=resolve(SNAPSHOTS)
        st.success(f'Updated {changed} snapshots from ESPN final scores.')
        if errors: st.warning(f'{len(errors)} game-date requests failed; those snapshots remain pending.')
    snapshots=load_snapshots(SNAPSHOTS)
    if snapshots:
        stats=snapshot_summary(snapshots)
        a,b,c,d=st.columns(4)
        a.metric('Saved snapshots',stats['snapshots'])
        b.metric('Resolved outcomes',stats['resolved'])
        c.metric('Observed win rate',f"{stats['win_rate']:.1%}" if stats['win_rate'] is not None else '—')
        d.metric('Hypothetical total P/L',f"${stats['hypothetical_pnl']:+.2f}")
        if stats['resolved']:
            st.write(f"**Hypothetical ROI (one YES contract per resolved snapshot, assumed fees):** {stats['hypothetical_roi']:+.1%}")
            st.caption('Selection bias: these are the model’s top-ranked candidates, not random or independent bets. One market may appear on multiple dates. Small samples, missing slippage and liquidity, and unverified settlement make ROI unreliable.')
        st.dataframe(pd.DataFrame(snapshots),hide_index=True,use_container_width=True)
        st.download_button('Export saved research snapshots',pd.DataFrame(snapshots).to_csv(index=False),'nba_research_snapshots.csv','text/csv')
    else:
        st.info('No snapshots yet. Open NBA markets, refresh, and click “Save today’s Top 10 research snapshot”. Then return here to review results.')

with traders:
    st.subheader('Public sports-trader watchlist')
    st.write('Track trader profiles you have verified are public. **This version does not automatically scrape accounts, rank real traders, or detect their trades in real time.** Kalshi public market trades do not generally identify the trader.')
    st.markdown('[Kalshi social](https://kalshi.com/social) · [KalshiScan](https://kalshiscan.com)')
    with st.form('watch_form',clear_on_submit=True):
        name=st.text_input('Trader display name')
        url=st.text_input('Public profile URL')
        sport=st.selectbox('Specialty',['NBA','NFL','MLB','NHL','Other sports'])
        notes=st.text_area('Why follow this trader? Evidence of performance, dates, public disclosures')
        if st.form_submit_button('Add public trader'):
            if not name.strip() or not url.startswith(('https://','http://')): st.error('Enter a name and valid public URL.')
            else:
                add_row(WATCH,WATCH_FIELDS,{'trader':name.strip(),'public_profile_url':url.strip(),'sport':sport,'notes':notes,'last_checked_utc':now()})
                st.success('Trader added to your local watchlist.')
    watch=read_rows(WATCH,WATCH_FIELDS)
    if watch:
        st.dataframe(pd.DataFrame(watch),hide_index=True,use_container_width=True)
        st.download_button('Export trader watchlist',pd.DataFrame(watch).to_csv(index=False),'trader_watchlist.csv','text/csv')
    else: st.caption('No traders added yet.')

with paper:
    st.subheader('Paper-trade journal')
    trades=read_rows(PAPER,PAPER_FIELDS)
    if trades:
        df=pd.DataFrame(trades)
        st.dataframe(df,hide_index=True,use_container_width=True)
        st.download_button('Export paper trades',df.to_csv(index=False),'paper_trades.csv','text/csv')
        st.caption('Positions are recorded locally and do not auto-settle. Use the exported CSV to annotate actual settlement outcomes. The displayed hypothetical ROI excludes slippage and uses estimated fees.')
    else: st.info('Your journal is empty. Add a simulated trade from the NBA markets tab.')

with about:
    st.markdown('''### Run locally
1. Install Python 3.10 or newer.
2. Open a terminal in this folder and run `pip install -r requirements.txt`.
3. Run `streamlit run app.py`.
4. Your browser opens the dashboard. Data is saved to the local `data/` folder.

### Important limitations
- **No automatic trading:** this app never authenticates or sends orders to Kalshi.
- **No real-time copy-trading:** the public market tape is not a verified account-level feed. Trader entries are manual public-profile bookmarks.
- **Experimental automatic ranking:** a unvalidated multi-month Elo model with limited walk-forward game-result diagnostics may rank up to ten candidates. It is NOT a calibrated or independently validated probability model; do not assume flagged trades are profitable. Manual probability input remains available.
- **No guarantees:** account for spreads, actual fee schedules, market depth, latency, changing rosters, and settlement rules.
- **Research tracker:** saves snapshots only when you press the button. ESPN final-score matching is not official Kalshi settlement. ROI is hypothetical, with no verified fills.
- **Refresh:** the scanner uses public API calls cached briefly; no persistent background process or notifications.
- **Deployment:** this is a local Streamlit app. To access it from multiple devices, deploy to a secure host and add authentication before storing any sensitive data.

Public API reference: https://docs.kalshi.com/
''')
