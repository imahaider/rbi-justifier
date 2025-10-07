# core/rules.py
import math
import numpy as np
from .schema import CATEGORY_ORDER

# ------------------------
# Dataset-level statistics
# ------------------------
def three_sigma_levels(series):
    mean = float(series.mean())
    std = float(series.std(ddof=0))
    return mean, std, mean - 3 * std, mean + 3 * std

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

# ------------------------
# CoF governance
# ------------------------
def governing_cof(flam, tox, prod):
    vals = {}
    if str(flam) in CATEGORY_ORDER: vals["flammable"] = str(flam)
    if str(tox)  in CATEGORY_ORDER: vals["toxic"]     = str(tox)
    if str(prod) in CATEGORY_ORDER: vals["production"]= str(prod)
    if not vals:
        return None, {}

    worst_letter = min(vals.values(), key=lambda x: CATEGORY_ORDER[x])  # A worst
    drivers = {k: v for k, v in vals.items() if v == worst_letter}
    return worst_letter, drivers

# ------------------------
# CCR classification
# ------------------------
# Default absolute bands (mm/y). Tune per material if needed.
DEFAULT_CCR_BANDS = {
    "negligible": 0.05,  # < 0.05
    "low":        0.10,  # 0.05–0.10
    "moderate":   0.20,  # 0.10–0.20
    "high":       0.50,  # 0.20–0.50
    # >0.50 => severe
}

def _label_from_bands(ccr, bands=DEFAULT_CCR_BANDS):
    if ccr is None or (isinstance(ccr, float) and (math.isnan(ccr) or math.isinf(ccr))):
        return "unknown"
    v = float(ccr)
    if v < bands["negligible"]:
        return "negligible"
    if v < bands["low"]:
        return "low"
    if v < bands["moderate"]:
        return "moderate"
    if v < bands["high"]:
        return "high"
    return "severe"

def classify_ccr(ccr_value, dataset_mean=None, dataset_std=None, bands=DEFAULT_CCR_BANDS):
    """
    Classify CCR by absolute bands; if CCR > mean + 2σ, bump up one level (conservative override).
    We never downgrade based on dataset stats.
    """
    base = _label_from_bands(ccr_value, bands)
    if dataset_mean is None or dataset_std is None or base in ("unknown", "severe"):
        return base

    try:
        v = float(ccr_value)
    except Exception:
        return base

    if v > (float(dataset_mean) + 2 * float(dataset_std)):
        order = ["negligible", "low", "moderate", "high", "severe"]
        idx = order.index(base) if base in order else 2
        return order[min(idx + 1, len(order) - 1)]
    return base

# ------------------------
# Inspection text
# ------------------------
def inspection_text(risk_cat, priority_value):
    risk = str(risk_cat).strip().upper()
    if risk == "HIGH":
        return "inspection requires very close attention with reduced intervals."
    if risk == "MEDIUM HIGH":
        return "inspection needs heightened monitoring with shorter-than-routine intervals."
    if risk == "MEDIUM":
        return "inspection follows balanced monitoring on routine intervals."
    if risk == "LOW":
        return "inspection can follow extended intervals with lower intensity."
    return "inspection priority is recorded for this component."

# ------------------------
# Helper: asymmetry wording for Inventory / FAA
# ------------------------
def describe_inv_faa(inv_level, fa_level):
    inv = str(inv_level).lower() if inv_level else "medium"
    fa  = str(fa_level).lower()  if fa_level  else "medium"

    if inv == "high" and fa == "low":
        return "a large inventory outweighs a limited affected area, keeping consequence pronounced."
    if inv == "low" and fa == "high":
        return "a small inventory tempers release magnitude, but a wide affected area amplifies exposure."
    if inv == "high" and fa == "medium":
        return "a large inventory reinforces consequence despite a moderate affected area."
    if inv == "medium" and fa == "high":
        return "a moderate inventory with a broad affected area elevates dispersion and ignition opportunities."
    if inv == "low" and fa == "medium":
        return "a small inventory moderates magnitude while a moderate area keeps exposure meaningful."
    if inv == "medium" and fa == "low":
        return "a moderate inventory is tempered by a limited affected area."
    if inv == "high" and fa == "high":
        return "a large inventory and a broad affected area together intensify potential impact."
    if inv == "low" and fa == "low":
        return "a small inventory and limited affected area jointly mitigate consequence."
    return "the inventory and affected area shape the potential release outcomes."

# ------------------------
# PoF band wording (PoF 1 worst … 5 best)
# ------------------------
def pof_band_phrase(pof, ccr_label):
    p = int(pof) if pof is not None else None
    ccr = str(ccr_label)

    if p == 1:
        base = "PoF is very high (1) with severe likelihood"
    elif p == 2:
        base = "PoF is high (2) with notable likelihood"
    elif p == 3:
        base = "PoF is moderate (3) with controlled likelihood"
    elif p == 4:
        base = "PoF is low (4) with minimal likelihood"
    elif p == 5:
        base = "PoF is very low (5) with negligible likelihood"
    else:
        base = "PoF is assessed from the available indicators"

    ccr_map = {
        "severe":    "the controlling corrosion rate is severe",
        "high":      "the controlling corrosion rate is high",
        "moderate":  "the controlling corrosion rate is moderate",
        "low":       "the controlling corrosion rate is low",
        "negligible":"the controlling corrosion rate is negligible",
        "unknown":   "corrosion indicators are noted",
    }
    return f"{base}; {ccr_map.get(ccr, 'corrosion indicators are noted')}."

# ------------------------
# Opener sentence selector (reason-first)
# ------------------------
def opener_sentence(pof, cof_letter, drivers, fluid, phase, toxic, inv_level, fa_level, prod_cat, ccr_label):
    fluid_txt = str(fluid).strip() if fluid not in [None, "nan", "NaN"] else ""
    phase_txt = str(phase).strip().lower() if phase not in [None, "nan", "NaN"] else ""
    toxic_txt = str(toxic).strip() if toxic not in [None, "nan", "NaN"] else ""
    prod_txt  = str(prod_cat).strip() if prod_cat else ""

    pof_sev = int(pof) if pof is not None else 3          # 1 worst … 5 best
    cof_sev = CATEGORY_ORDER.get(str(cof_letter), 3)       # A=1 … E=5

    gap = abs(pof_sev - cof_sev)
    both_due_to_ccr = (pof_sev >= 4) and (ccr_label in ["high", "severe"])

    service_bits = []
    if fluid_txt and phase_txt: service_bits.append(f"{fluid_txt} in {phase_txt} phase")
    elif fluid_txt: service_bits.append(fluid_txt)
    if toxic_txt and toxic_txt.lower() not in ("nan", "none", "no"):
        service_bits.append(f"with toxic {toxic_txt}")
    service_reason = ", ".join(service_bits) if service_bits else "the handled service"

    inv = (inv_level or "").lower()
    fa  = (fa_level  or "").lower()
    fa_phrase = "broad affected area" if fa == "high" else ("limited affected area" if fa == "low" else "moderate affected area")

    def cof_single(driver_key, letter):
        if driver_key == "flammable":
            return f"driven primarily by CoF, dominated by flammable fluid Category {letter}, because {service_reason} and the {fa_phrase} elevate ignition potential."
        if driver_key == "toxic":
            return f"driven primarily by CoF, dominated by toxic exposure Category {letter}, because {service_reason} increases exposure potential."
        if driver_key == "production":
            return f"driven primarily by CoF, dominated by lost-production Category {letter}, because the service is outage-sensitive and downtime impact is substantial."
        return f"driven primarily by CoF, governed by Category {letter}."

    def cof_tie(keys, letter):
        s = set(keys)
        if s == {"flammable", "toxic"}:
            return f"consequence-led, jointly governed by flammable and toxic Category {letter}, because {service_reason} presents ignition and exposure hazards, amplified by the {fa_phrase}."
        if s == {"flammable", "production"}:
            return f"consequence-led, jointly governed by flammable and production Category {letter}, since {service_reason} raises fire potential and the service is throughput-critical."
        if s == {"toxic", "production"}:
            return f"consequence-led, jointly governed by toxic and production Category {letter}, as exposure concerns and outage sensitivity together dominate."
        return f"consequence-led, jointly governed by {' and '.join(keys)} Category {letter}."

    if both_due_to_ccr or gap == 0:
        return f"the risk results from both PoF and CoF, because {service_reason} is material while likelihood remains non-negligible."
    if pof_sev + 1 <= cof_sev:
        if ccr_label in ["high", "severe"]:
            return f"driven mainly by PoF, with elevated likelihood reinforced by a {ccr_label} controlling corrosion rate."
        return f"driven mainly by PoF, as the likelihood outweighs consequence effects."
    else:
        if not drivers:
            return f"driven primarily by CoF."
        if len(drivers) == 1:
            dk = list(drivers.keys())[0]
            return cof_single(dk, cof_letter)
        if len(drivers) == 2:
            return cof_tie(list(drivers.keys()), cof_letter)
        return f"consequence-led, with flammable, toxic, and production all at Category {cof_letter}, collectively dominating given {service_reason} and the {fa_phrase}."
