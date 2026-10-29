"""Descriptive quality gates; no live player data or trading advice."""
from datetime import datetime, timezone

def candidate_quality(candidate, diagnostics):
    """Label evidence, not probability of winning or profitability."""
    n=int(candidate.get('games per team (min)',0) or 0)
    count=int(diagnostics.get('games',0) or 0)
    b=diagnostics.get('brier'); base=diagnostics.get('baseline_brier')
    if count<100 or b is None or base is None: return 'INSUFFICIENT VALIDATION'
    if b>=base: return 'MODEL FAILED BASELINE'
    if n<20 or count<300: return 'LIMITED EVIDENCE'
    return 'PRELIMINARY — NOT TRADE VALIDATED'

def freshness(generated_utc, now=None):
    if not generated_utc: return 'NO SNAPSHOT'
    try:
        t=datetime.fromisoformat(generated_utc.replace('Z','+00:00'))
        if t.tzinfo is None: return 'UNKNOWN TIMESTAMP'
        age=((now or datetime.now(timezone.utc))-t).total_seconds()/3600
        return 'FUTURE TIMESTAMP' if age < -0.1 else ('STALE (>24 HOURS)' if age>24 else 'RECENT SNAPSHOT (<24 HOURS)')
    except (ValueError,TypeError): return 'INVALID TIMESTAMP'

def injury_review(candidates):
    """Availability is NOT fetched. Explicit review state avoids made-up player reports."""
    return [{'ticker':c.get('ticker',''), 'matchup':c.get('matchup',''),
             'status':'NOT VERIFIED', 'source':'No authoritative injury/lineup feed configured',
             'forecast_adjustment':'NONE — injuries not included'} for c in candidates]
