import numpy as np
from .schema import CATEGORY_ORDER

def three_sigma_levels(series):
    mean = float(series.mean())
    std = float(series.std(ddof=0))
    return mean, std, mean - 3*std, mean + 3*std

def classify_three_sigma(value, low_thr, high_thr):
    try:
        v = float(value)
    except Exception:
        return "medium"
    if v < low_thr:
        return "low"
    if v > high_thr:
        return "high"
    return "medium"

def governing_cof(flam, tox, prod):
    vals = {}
    if str(flam) in CATEGORY_ORDER: vals["flammable"] = str(flam)
    if str(tox) in CATEGORY_ORDER:  vals["toxic"] = str(tox)
    if str(prod) in CATEGORY_ORDER: vals["production"] = str(prod)
    if not vals:
        return None, {}
    worst = min(vals.values(), key=lambda x: CATEGORY_ORDER[x])
    drivers = {k: v for k, v in vals.items() if v == worst}
    return worst, drivers

def inspection_text(risk_cat, priority_value):
    risk = str(risk_cat).strip().upper()
    p = priority_value
    if risk == "HIGH":
        return f"inspection priority of {p} reflects the need for very close attention with reduced inspection intervals."
    if risk == "MEDIUM HIGH":
        return f"inspection priority of {p} indicates heightened monitoring with shorter-than-routine inspection intervals."
    if risk == "MEDIUM":
        return f"inspection priority of {p} reflects balanced monitoring with routine inspection intervals."
    if risk == "LOW":
        return f"inspection priority of {p} supports extended inspection intervals and lower monitoring intensity."
    return f"inspection priority of {p} is recorded for this component."
