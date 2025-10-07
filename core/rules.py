# core/rules.py
import math
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
DEFAULT_CCR_BANDS = {
    "negligible": 0.05,  # < 0.05
    "low":        0.10,  # 0.05–0.10
    "moderate":   0.20,  # 0.10–0.20
    "high":       0.50,  # 0.20–0.50
    # >0.50 => severe
}

def _label_from_bands(ccr, bands=DEFAULT_CCR_BANDS):
    if ccr is None:
        return "unknown"
    try:
        v = float(ccr)
    except Exception:
        return "unknown"
    if math.isnan(v) or math.isinf(v):
        return "unknown"
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
# Short phrases (for compact sentence 2)
# ------------------------
def pof_band_short(pof):
    p = int(pof) if pof is not None else None
    if p == 1: return "PoF is very high (1)"
    if p == 2: return "PoF is high (2)"
    if p == 3: return "PoF is moderate (3)"
    if p == 4: return "PoF is low (4)"
    if p == 5: return "PoF is very low (5)"
    return "PoF is assessed from available indicators"

def ccr_short(label):
    m = {
        "severe": "CCR is severe",
        "high": "CCR is high",
        "moderate": "CCR is moderate",
        "low": "CCR is low",
        "negligible": "CCR is negligible",
        "unknown": "CCR indicators are noted",
    }
    return m.get(str(label), "CCR indicators are noted")

def inspection_text(risk_cat, priority_value):
    risk = str(risk_cat).strip().upper()
    if risk == "HIGH":
        return "inspection requires reduced intervals"
    if risk == "MEDIUM HIGH":
        return "inspection needs shorter-than-routine intervals"
    if risk == "MEDIUM":
        return "inspection is on routine intervals"
    if risk == "LOW":
        return "inspection can follow extended intervals"
    return "inspection priority is recorded"

# ------------------------
# Opener sentence (always includes fluid + phase when available)
# ------------------------
def opener_sentence(pof, cof_letter, drivers, fluid, phase, toxic, inv_level, fa_level, prod_cat, ccr_label):
    # Normalize service terms
    fluid_txt = (str(fluid).strip() if fluid not in [None, "nan", "NaN"] else "")
    phase_txt = (str(phase).strip().lower() if phase not in [None, "nan", "NaN"] else "")
    toxic_txt = (str(toxic).strip() if toxic not in [None, "nan", "NaN"] else "")

    # Build "fluid + phase" always when present
    service = ""
    if fluid_txt and phase_txt: service = f"{fluid_txt} {phase_txt}"
    elif fluid_txt:             service = fluid_txt
    elif phase_txt:             service = phase_txt  # rare, but acceptable

    # Inventory/area cue (no numbers)
    fa = (fa_level or "").lower()
    fa_phrase = "broad affected area" if fa == "high" else ("limited affected area" if fa == "low" else "moderate affected area")

    # Severity comparison on 1..5 (lower worse)
    pof_sev = int(pof) if pof is not None else 3
    cof_sev = CATEGORY_ORDER.get(str(cof_letter), 3)
    gap = abs(pof_sev - cof_sev)
    both_due_to_ccr = (pof_sev >= 4) and (ccr_label in ["high", "severe"])

    # Compose “reason”
    reason_bits = []
    if service: reason_bits.append(service)
    if toxic_txt and toxic_txt.lower() not in ("nan", "none", "no"):
        reason_bits.append(f"with toxic {toxic_txt}")
    reason = " ".join(reason_bits) if reason_bits else "the handled service"

    # CoF-driven helpers
    def cof_single(driver_key, letter):
        if driver_key == "flammable":
            return f"driven by CoF, dominated by flammable Category {letter}, because {reason} and the {fa_phrase} elevate ignition potential"
        if driver_key == "toxic":
            return f"driven by CoF, dominated by toxic Category {letter}, because {reason} increases exposure potential"
        if driver_key == "production":
            return f"driven by CoF, dominated by lost-production Category {letter}, because outage sensitivity is substantial"
        return f"driven by CoF, governed by Category {letter}"

    def cof_tie(keys, letter):
        s = set(keys)
        if s == {"flammable", "toxic"}:
            return f"consequence-led and jointly governed by flammable and toxic Category {letter}, because {reason} presents ignition and exposure hazards and the {fa_phrase} amplifies reach"
        if s == {"flammable", "production"}:
            return f"consequence-led and jointly governed by flammable and production Category {letter}, since {reason} raises fire potential and the service is throughput-critical"
        if s == {"toxic", "production"}:
            return f"consequence-led and jointly governed by toxic and production Category {letter}, as exposure concerns and outage sensitivity together dominate"
        return f"consequence-led and jointly governed by Category {letter}"

    # Decide opener
    if both_due_to_ccr or gap == 0:
        return f"resulting from both PoF and CoF, because {reason} is material while likelihood remains non-negligible"
    if pof_sev + 1 <= cof_sev:
        # PoF worse → PoF-driven
        if ccr_label in ["high", "severe"]:
            return f"driven mainly by PoF, as elevated likelihood is reinforced by a {ccr_label} CCR in {service or 'service'}"
        return f"driven mainly by PoF, with likelihood outweighing consequence effects"
    # Otherwise CoF-driven
    if not drivers:
        return f"driven by CoF"
    if len(drivers) == 1:
        dk = list(drivers.keys())[0]
        return cof_single(dk, cof_letter)
    if len(drivers) == 2:
        return cof_tie(list(drivers.keys()), cof_letter)
    return f"consequence-led, with flammable, toxic, and production all at Category {cof_letter}, collectively dominating due to {reason} and the {fa_phrase}"
