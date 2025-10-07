# core/generator.py
import pandas as pd
import numpy as np

from .schema import CATEGORY_ORDER
from .rules import (
    three_sigma_levels, classify_three_sigma, governing_cof,
    classify_ccr, pof_band_phrase, inspection_text, describe_inv_faa, opener_sentence
)

def _get_value(row, key):
    val = row.get(key)
    return None if pd.isna(val) else val

def _controlling_corrosion_rate(row):
    # Prefer explicit CCR if provided; otherwise use max(Int, Ext)
    ccr = _get_value(row, "Controlling Corr Rate")
    if ccr is not None:
        return float(ccr)
    int_cr = _get_value(row, "Int Corr Rate")
    ext_cr = _get_value(row, "Ext Corr Rate")
    vals = [v for v in [int_cr, ext_cr] if v is not None]
    if not vals:
        return None
    try:
        return float(max(vals))
    except Exception:
        return None

def build_all_justifications(df: pd.DataFrame):
    # Dataset stats for Inventory and FAA (3σ)
    inv_mean, inv_std, inv_lo, inv_hi = three_sigma_levels(df["Inventory"])
    fa_mean,  fa_std,  fa_lo,  fa_hi  = three_sigma_levels(df["Flammable Affected Area"])

    # Dataset stats for CCR (for conservative spike override)
    # Use computed CCR per row (explicit column or max(int,ext))
    ccr_series = df.apply(lambda r: _controlling_corrosion_rate(r), axis=1)
    try:
        ccr_mean = float(pd.Series(ccr_series).mean())
        ccr_std  = float(pd.Series(ccr_series).std(ddof=0))
    except Exception:
        ccr_mean, ccr_std = None, None

    out = []
    for _, r in df.iterrows():
        risk_cat = str(_get_value(r, "Risk Category") or "").strip() or "N/A"
        pof      = _get_value(r, "Driving PoF")
        pof_int  = int(pof) if (pof is not None and str(pof).strip().isdigit()) else None
        insp     = _get_value(r, "Inspection Priority")

        # Service descriptors
        fluid    = _get_value(r, "Representative Fluid")
        fluid_ty = _get_value(r, "Fluid Type")
        phase    = _get_value(r, "Initial Fluid Phase")
        toxic    = _get_value(r, "Toxic Fluid")

        # Consequence categories
        flam     = _get_value(r, "Flamm Conseq Categ")
        tox_cat  = _get_value(r, "Toxic Conseq Cat")
        prod_cat = _get_value(r, "Lost Production Category")

        # Inventory & FAA levels (3σ, no numbers in prose)
        inv_level = classify_three_sigma(_get_value(r, "Inventory"), inv_lo, inv_hi)
        fa_level  = classify_three_sigma(_get_value(r, "Flammable Affected Area"), fa_lo, fa_hi)

        # Governing CoF
        cof_letter, drivers = governing_cof(flam, tox_cat, prod_cat)

        # CCR classification
        ccr_value = _controlling_corrosion_rate(r)
        ccr_label = classify_ccr(ccr_value, ccr_mean, ccr_std)

        # ------------- Sentence 1: Opener (reason-first) -------------
        opener = opener_sentence(
            pof=pof_int,
            cof_letter=cof_letter,
            drivers=drivers,
            fluid=fluid or fluid_ty,  # prefer representative fluid; fallback to fluid type
            phase=phase,
            toxic=toxic,
            inv_level=inv_level,
            fa_level=fa_level,
            prod_cat=prod_cat,
            ccr_label=ccr_label
        )
        s1 = f"The risk is {risk_cat}, {opener}"

        # ------------- Sentence 2: PoF + CCR + inspection -------------
        pof_phrase = pof_band_phrase(pof_int, ccr_label)
        insp_phrase = inspection_text(risk_cat, insp)
        s2 = f"{pof_phrase} Accordingly, {insp_phrase}"

        # ------------- Sentence 3: CoF details + inv/area closure -------------
        flam_txt = flam if flam is not None else "N/A"
        tox_txt  = tox_cat if tox_cat is not None else "N/A"
        prod_txt = prod_cat if prod_cat is not None else "N/A"

        # CoF governance clause
        if cof_letter is None or not drivers:
            gov_clause = "the governing consequence cannot be determined from the provided categories."
        else:
            if len(drivers) == 1:
                dk = list(drivers.keys())[0]
                if dk == "flammable":
                    gov_clause = f"CoF is dominated by flammable fluid Category {cof_letter}."
                elif dk == "toxic":
                    gov_clause = f"CoF is dominated by toxic exposure Category {cof_letter}."
                elif dk == "production":
                    gov_clause = f"CoF is dominated by lost-production Category {cof_letter}."
                else:
                    gov_clause = f"CoF is governed by Category {cof_letter}."
            elif len(drivers) == 2:
                keys = set(drivers.keys())
                if keys == {"flammable", "toxic"}:
                    gov_clause = f"CoF is jointly governed by flammable and toxic Category {cof_letter}."
                elif keys == {"flammable", "production"}:
                    gov_clause = f"CoF is jointly governed by flammable and production Category {cof_letter}."
                elif keys == {"toxic", "production"}:
                    gov_clause = f"CoF is jointly governed by toxic and production Category {cof_letter}."
                else:
                    gov_clause = f"CoF is jointly governed by Category {cof_letter}."
            else:
                gov_clause = f"CoF is collectively governed by flammable, toxic, and production at Category {cof_letter}."

        inv_faa_phrase = describe_inv_faa(inv_level, fa_level)

        # Service clause (concise; reason already in opener, so keep short here)
        service_bits = []
        if fluid or fluid_ty:
            if fluid and fluid_ty:
                service_bits.append(f"{fluid_ty} {fluid}")
            elif fluid:
                service_bits.append(str(fluid))
            else:
                service_bits.append(str(fluid_ty))
        if phase:
            service_bits.append(f"in {str(phase).lower()} phase")
        if toxic and str(toxic).lower() not in ("nan", "none", "no"):
            service_bits.append(f"with toxic {toxic}")
        service_clause = ""
        if service_bits:
            service_clause = " The component handles " + " ".join(service_bits) + "."

        s3 = (
            f"For the consequence categories, the flammable category is {flam_txt}, the toxic category is {tox_txt}, "
            f"and the production category is {prod_txt}; {gov_clause}{service_clause} "
            f"In addition, {inv_faa_phrase} With PoF = {pof_int if pof_int is not None else 'N/A'} "
            f"and CoF governed by Category {cof_letter if cof_letter else 'N/A'}, the overall classification remains {risk_cat}."
        )

        paragraph = " ".join([s1, s2, s3]).strip()
        out.append(paragraph)

    return out
