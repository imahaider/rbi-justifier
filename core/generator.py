# core/generator.py
import pandas as pd
from .rules import (
    three_sigma_levels, classify_three_sigma, governing_cof,
    classify_ccr, opener_sentence, pof_band_short, ccr_short, inspection_text
)

def _get(row, key):
    val = row.get(key)
    return None if pd.isna(val) else val

def _ccr(row):
    """
    CCR precedence:
    1) Int Controlling Corrosion Rate  (authoritative)
    2) Controlling Corr Rate           (legacy alias)
    3) max(Int Corr Rate, Ext Corr Rate)
    """
    ccr = row.get("Int Controlling Corrosion Rate")
    if pd.notna(ccr):
        try: return float(ccr)
        except Exception: pass

    ccr_legacy = row.get("Controlling Corr Rate")
    if pd.notna(ccr_legacy):
        try: return float(ccr_legacy)
        except Exception: pass

    int_cr = row.get("Int Corr Rate")
    ext_cr = row.get("Ext Corr Rate")
    vals = []
    if pd.notna(int_cr):
        try: vals.append(float(int_cr))
        except Exception: pass
    if pd.notna(ext_cr):
        try: vals.append(float(ext_cr))
        except Exception: pass
    return max(vals) if vals else None

def build_all_justifications(df: pd.DataFrame):
    # 3σ levels for Inventory & FAA (qualitative only)
    _, _, inv_lo, inv_hi = three_sigma_levels(df["Inventory"])
    _, _, fa_lo,  fa_hi  = three_sigma_levels(df["Flammable Affected Area"])

    # Dataset CCR stats (for conservative spike override)
    ccr_series = df.apply(lambda r: _ccr(r), axis=1)
    try:
        ccr_mean = float(pd.Series(ccr_series).mean())
        ccr_std  = float(pd.Series(ccr_series).std(ddof=0))
    except Exception:
        ccr_mean, ccr_std = None, None

    out = []
    for _, r in df.iterrows():
        risk_cat = str(_get(r, "Risk Category") or "").strip() or "N/A"
        pof      = _get(r, "Driving PoF")
        pof_int  = int(pof) if (pof is not None and str(pof).strip().isdigit()) else None

        # Service descriptors (always try Representative Fluid first; fallback to Fluid Type)
        fluid    = _get(r, "Representative Fluid") or _get(r, "Fluid Type")
        phase    = _get(r, "Initial Fluid Phase")
        toxic    = _get(r, "Toxic Fluid")

        # CoF categories
        flam     = _get(r, "Flamm Conseq Categ")
        tox_cat  = _get(r, "Toxic Conseq Cat")
        prod_cat = _get(r, "Lost Production Category")

        # Qualitative levels (no numbers in text)
        inv_level = classify_three_sigma(_get(r, "Inventory"), inv_lo, inv_hi)
        fa_level  = classify_three_sigma(_get(r, "Flammable Affected Area"), fa_lo, fa_hi)

        # Governing CoF
        cof_letter, drivers = governing_cof(flam, tox_cat, prod_cat)

        # CCR classification
        ccr_val   = _ccr(r)
        ccr_label = classify_ccr(ccr_val, ccr_mean, ccr_std)

        # -------- Sentence 1: Opener (reason-first, includes fluid + phase if available)
        opener = opener_sentence(
            pof=pof_int,
            cof_letter=cof_letter,
            drivers=drivers,
            fluid=fluid,
            phase=phase,
            toxic=toxic,
            inv_level=inv_level,
            fa_level=fa_level,
            prod_cat=prod_cat,
            ccr_label=ccr_label
        )
        s1 = f"The risk is {risk_cat}, {opener}."

        # -------- Sentence 2: Compact PoF + CCR + inspection + CoF summary (no repeated reasons)
        pof_txt  = pof_band_short(pof_int)
        ccr_txt  = ccr_short(ccr_label)
        insp_txt = inspection_text(risk_cat, _get(r, "Inspection Priority"))

        flam_txt = flam if flam is not None else "N/A"
        tox_txt  = tox_cat if tox_cat is not None else "N/A"
        prod_txt = prod_cat if prod_cat is not None else "N/A"
        cof_txt  = cof_letter if cof_letter else "N/A"

        s2 = (
            f"{pof_txt}; {ccr_txt}; {insp_txt}. "
            f"Flam/Tox/Prod = {flam_txt}/{tox_txt}/{prod_txt}; "
            f"with CoF governed by Category {cof_txt}, the profile remains {risk_cat}."
        )

        out.append(f"{s1} {s2}".strip())

    return out
