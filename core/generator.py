import pandas as pd
from .rules import three_sigma_levels, classify_three_sigma, governing_cof, inspection_text
from .schema import CATEGORY_ORDER

def build_all_justifications(df: pd.DataFrame):
    inv_mean, inv_std, inv_lo, inv_hi = three_sigma_levels(df["Inventory"])
    fa_mean, fa_std, fa_lo, fa_hi = three_sigma_levels(df["Flammable Affected Area"])

    out = []
    for _, r in df.iterrows():
        risk_cat = str(r.get("Risk Category", "")).strip()
        pof = r.get("Driving PoF")
        try:
            pof_int = int(pof)
        except Exception:
            pof_int = None

        int_cr = r.get("Int Corr Rate")
        ext_cr = r.get("Ext Corr Rate")
        insp = r.get("Inspection Priority")

        flam = r.get("Flamm Conseq Categ")
        tox = r.get("Toxic Conseq Cat")
        prod = r.get("Lost Production Category")

        gov_letter, gov_drivers = governing_cof(flam, tox, prod)

        inv_level = classify_three_sigma(r.get("Inventory"), inv_lo, inv_hi)
        fa_level  = classify_three_sigma(r.get("Flammable Affected Area"), fa_lo, fa_hi)

        # Decide what drives the risk for opening sentence
        # Map letters to 1..5, lower number is worse
        def val_or_default(letter, default=3):
            return CATEGORY_ORDER.get(str(letter), default)

        cof_strength = val_or_default(gov_letter, 3)
        pof_strength = 3 if pof_int is None else (6 - pof_int)  # PoF 5 => strongest -> map to 1..5 like CoF
        # Opening driver
        if pof_int is not None:
            if pof_strength < cof_strength - 1:
                opener = "driven mainly by probability of failure"
            elif cof_strength < pof_strength - 1:
                opener = "driven primarily by consequence of failure"
            else:
                opener = "resulting from both the probability and consequence of failure"
        else:
            opener = "resulting from both the probability and consequence of failure"

        # PoF clause
        if pof_int is None:
            pof_clause = "the probability of failure is assessed from available data and corrosion rates are stated below"
        elif pof_int >= 4:
            pof_clause = f"the probability of failure is elevated with PoF = {pof_int}, supported by noticeable corrosion activity (internal ≈ {float(int_cr):.2f} mm/y, external ≈ {float(ext_cr):.2f} mm/y)"
        else:
            pof_clause = f"the probability of failure is relatively low with PoF = {pof_int} and corrosion rates are minimal (internal ≈ {float(int_cr):.2f} mm/y, external ≈ {float(ext_cr):.2f} mm/y)"

        insp_clause = inspection_text(risk_cat, insp)

        flam_txt = f"{flam}" if pd.notnull(flam) else "N/A"
        tox_txt  = f"{tox}" if pd.notnull(tox) else "N/A"
        prod_txt = f"{prod}" if pd.notnull(prod) else "N/A"

        if gov_letter is None:
            gov_clause = "The governing consequence cannot be determined from the provided categories."
        else:
            if len(gov_drivers) == 1:
                dk = list(gov_drivers.keys())[0]
                gov_clause = f"The governing consequence is Category {gov_letter}, driven by the {dk} category {gov_letter}."
            else:
                keys = " and ".join(sorted(gov_drivers.keys()))
                gov_clause = f"The governing consequence is Category {gov_letter}, jointly influenced by the {keys} categories {gov_letter}."

        # Service description
        pieces = []
        if pd.notnull(r.get("Fluid Type")) and pd.notnull(r.get("Representative Fluid")):
            pieces.append(f"{str(r.get('Fluid Type')).strip()} {str(r.get('Representative Fluid')).strip()}")
        elif pd.notnull(r.get("Fluid Type")):
            pieces.append(str(r.get("Fluid Type")).strip())
        elif pd.notnull(r.get("Representative Fluid")):
            pieces.append(str(r.get("Representative Fluid")).strip())
        if pd.notnull(r.get("Initial Fluid Phase")):
            pieces.append(f"in {str(r.get('Initial Fluid Phase')).strip()} phase")
        if pd.notnull(r.get("Toxic Fluid")):
            pieces.append(f"with toxic {str(r.get('Toxic Fluid')).strip()}")
        service_clause = f" The component handles {' '.join(pieces)}." if pieces else ""

        inv_area_clause = f"The inventory is {inv_level} and the flammable affected area is {fa_level}, shaping the severity of potential release outcomes."

        paragraph = (
            f"The risk is {risk_cat} {opener} because {pof_clause}, and {insp_clause} "
            f"For the consequence categories, the flammable category is {flam_txt}, the toxic category is {tox_txt}, and the production category is {prod_txt}. "
            f"{gov_clause}{service_clause} {inv_area_clause} "
            f"With PoF at level {pof_int if pof_int is not None else 'N/A'} and CoF governed by Category {gov_letter if gov_letter else 'N/A'}, the combined effect results in an overall {risk_cat} risk classification."
        )

        out.append(paragraph)
    return out
