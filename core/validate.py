import re

def safe_keep_or_fallback(model_text: str, payload: dict, draft_text: str) -> str:
    # Require PoF pattern
    pof = payload.get("pof")
    if pof is not None and f"PoF = {pof}" not in model_text:
        return draft_text

    # Require governing_cof letter
    g = payload.get("governing_cof")
    if g and f"Category {g}" not in model_text:
        return draft_text

    # Require final risk category mention
    rc = payload.get("risk_category")
    if rc and rc not in model_text:
        return draft_text

    # Basic letter presence
    for k in ["flamm_cat", "tox_cat", "prod_cat"]:
        v = payload.get(k)
        if v and v not in model_text:
            return draft_text

    # Do not allow different numbers for corrosion rates if provided
    for key in ["int_corr_rate", "ext_corr_rate"]:
        if key in payload and payload[key] is not None:
            num = f"{payload[key]:.2f}"
            if num not in model_text:
                return draft_text

    return model_text
