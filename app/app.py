import io
import json
import streamlit as st
import pandas as pd

from core.schema import missing_columns, REQUIRED_COLUMNS
from core.generator import build_all_justifications
from core.rules import three_sigma_levels, classify_three_sigma, governing_cof
from core.validate import safe_keep_or_fallback
from core.llm import polish_with_hf

st.set_page_config(page_title="RBI Risk Justification Generator", page_icon="🛠️", layout="wide")
st.title("RBI Risk Justification Generator")

st.markdown(
    "Upload an Excel in the agreed format. The app will add a **Risk Justification** column using your rules. "
    "Optionally, it will polish phrasing with an open-source LLM while keeping facts unchanged."
)

with st.sidebar:
    st.header("LLM Polishing")
    use_llm = st.toggle("Use open-source LLM polishing", value=False)
    st.caption("Enable to paraphrase grammar and flow without changing facts.")
    model_id = st.text_input("Hugging Face model id", value="Qwen/Qwen2.5-7B-Instruct")
    st.caption("You must accept the model license on your HF account.")
    st.markdown("---")
    st.header("Info")
    st.write("Required columns:")
    st.code("\n".join(REQUIRED_COLUMNS), language="text")

hf_token = st.secrets.get("HF_API_TOKEN", None)

uploaded = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])
if uploaded:
    try:
        df = pd.read_excel(uploaded, sheet_name=0)
    except Exception as e:
        st.error(f"Failed to read Excel: {e}")
        st.stop()

    miss = missing_columns(df)
    if miss:
        st.error(f"Missing required columns: {miss}")
        st.stop()

    # Build draft justifications
    st.info("Generating draft justifications using rule-based engine...")
    justs = build_all_justifications(df)
    df["Risk Justification"] = justs

    # Optional LLM polishing
    if use_llm:
        if not hf_token:
            st.error("LLM enabled but no HF_API_TOKEN set in Streamlit Secrets.")
        else:
            st.info("Polishing with open-source LLM...")
            # Pre-compute stats for inventory and FAA so payload can include levels if you wish
            inv_mean, inv_std, inv_lo, inv_hi = three_sigma_levels(df["Inventory"])
            fa_mean, fa_std, fa_lo, fa_hi   = three_sigma_levels(df["Flammable Affected Area"])

            polished = []
            for i, r in df.iterrows():
                # Prepare payload for guardrails
                gov_letter, drivers = governing_cof(r["Flamm Conseq Categ"], r["Toxic Conseq Cat"], r["Lost Production Category"])
                inv_level = classify_three_sigma(r["Inventory"], inv_lo, inv_hi)
                fa_level  = classify_three_sigma(r["Flammable Affected Area"], fa_lo, fa_hi)
                payload = {
                    "component": r["Component"],
                    "risk_category": str(r["Risk Category"]),
                    "pof": int(r["Driving PoF"]) if pd.notnull(r["Driving PoF"]) else None,
                    "int_corr_rate": float(r["Int Corr Rate"]) if pd.notnull(r["Int Corr Rate"]) else None,
                    "ext_corr_rate": float(r["Ext Corr Rate"]) if pd.notnull(r["Ext Corr Rate"]) else None,
                    "inspection_priority": int(r["Inspection Priority"]) if pd.notnull(r["Inspection Priority"]) else None,
                    "flamm_cat": str(r["Flamm Conseq Categ"]),
                    "tox_cat": str(r["Toxic Conseq Cat"]),
                    "prod_cat": str(r["Lost Production Category"]),
                    "governing_cof": gov_letter,
                    "governing_sources": list(drivers.keys()),
                    "inventory_level": inv_level,
                    "flamm_area_level": fa_level,
                    "fluid_type": str(r["Fluid Type"]),
                    "fluid": str(r["Representative Fluid"]),
                    "phase": str(r["Initial Fluid Phase"]),
                    "toxic": str(r["Toxic Fluid"]),
                }
                draft = df.at[i, "Risk Justification"]
                try:
                    mt = polish_with_hf(model_id, hf_token, payload, draft)
                    safe = safe_keep_or_fallback(mt, payload, draft)
                    polished.append(safe)
                except Exception:
                    polished.append(draft)

            df["Risk Justification"] = polished

    st.success("Done. Preview below and download Excel.")

    st.dataframe(df.head(20))

    # Download button
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Table1", index=False)
    st.download_button("Download updated Excel", data=out.getvalue(), file_name="RBI_Justifications.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
