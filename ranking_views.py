"""Presentation-only rankings. These probabilities are unvalidated heuristics."""
def split_rankings(candidates, minimum_probability=.75, limit=10):
    valid=[]
    for row in candidates:
        try:
            p=float(row['heuristic probability'])
            ask=float(row['YES ask'])
            edge=float(row['estimated edge after assumed fee'])
            if not (0<=p<=1 and 0<ask<1): continue
            valid.append(row)
        except (ValueError,TypeError,KeyError): continue
    # High probability list applies user-selected 75% cutoff.
    high=sorted((r for r in valid if float(r['heuristic probability'])>=minimum_probability),
                key=lambda r:(-float(r['heuristic probability']),-float(r['estimated edge after assumed fee'])))[:limit]
    # Best value ranks by model-vs-ask difference, with no 75% restriction.
    value=sorted(valid,key=lambda r:float(r['estimated edge after assumed fee']),reverse=True)[:limit]
    return high,value
