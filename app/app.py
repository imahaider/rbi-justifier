import os
import sys
import io
import streamlit as st
import pandas as pd

# Ensure repo root on path (works on Streamlit Cloud too)
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Core imports (fail fast with a clear message)
try:
    from core.schema import missing_columns, REQUIRED_COLUMNS
    from core.generator import build_all_justifications
    from core.rules import three_sigma_levels, classify_three_sigma, governing_cof
    from core.validate import safe_keep_or_fallback
    from core.llm import polish_with_hf
except Exception as e:
    st.stop()  # Stop rendering further
    raise

st.set_page_config(page_title="RBI Risk Justification Generator", page_icon="🛠️", layout="wide")
st.title("RBI Risk Justification Generator")

st.markdown(
    "Upload an Excel in the agreed format. The app will add a **Risk Justification** column using your rules. "
    "Optionally, it will polish phrasing with an open-source LLM while keeping facts unchanged."
)

# ---------------- Sidebar controls (LLM and Info) ----------------
with st.sidebar:
    st.header("LLM Polishing")
    use_llm = st.toggle("Use open-source LLM polishing", value=False)
    st.caption("Enable to paraphrase grammar and flow without changing facts.")
    model_id = st.text_input("Hugging Face model id", value="Qwen/Qwen2.5-7B-Instruct")

    # Health check lives in the same block so variable scope is safe
with st.sidebar:
    st.header("LLM Polishing")
    use_llm = st.toggle("Use open-source LLM polishing", value=False)
    model_id = st.text_input("Hugging Face model id", value="Qwen/Qwen2.5-7B-Instruct")
    st.caption("Enable to paraphrase grammar and flow without changing facts.")

    # 🔽 Add this block here
    test_llm = st.button("Test LLM health")
    if 'test_result' not in st.session_state:
        st.session_state.test_result = ""

    if test_llm:
        try:
            from core.llm import polish_with_hf
            demo_payload = {
                "component":"TEST","risk_category":"MEDIUM","pof":4,
                "int_corr_rate":0.10,"ext_corr_rate":0.03,"inspection_priority":15,
                "flamm_cat":"B","tox_cat":"B","prod_cat":"E","governing_cof":"B",
                "governing_sources":["flammable","toxic"],
                "inventory_level":"medium","flamm_area_level":"medium",
                "fluid_type":"Flammable","fluid":"C4","phase":"Gas","toxic":"H2S"
            }
            demo_draft = "The risk is MEDIUM because PoF = 4 with minimal corrosion; governing CoF is Category B."
            text = polish_with_hf(model_id, st.secrets.get("HF_API_TOKEN"), demo_payload, demo_draft)
            st.session_state.test_result = f"OK: {text[:200]}"
        except Exception as e:
            import traceback
            st.session_state.test_result = f"ERROR: {type(e).__name__}: {str(e)}\n\n{traceback.format_exc(limit=1)}"

    if st.session_state.test_result:
        st.info(st.session_state.test_result)


    st.markdown("---")
    st.header("Info")
    st.write("Required columns:")
    st.code("\n".join(REQUIRED_COLUMNS), language="text")

# Token for polishing (read once)
HF_TOKEN = st.secrets.get("HF_API_TOKEN", None)

# ---------------- File upload ----------------
uploaded = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])

if uploaded:
    # Read file
    try:
        df = pd.read_excel(uploaded, sheet_name=0)
    except Exception as e:
        st.error(f"Failed to read Excel: {e}")
        st.stop()

    # Schema check
    miss = missing_columns(df)
    if miss:
        st.error(f"Missing required columns: {miss}")
        st.stop()

    # Build draft justifications (rule-based)
    st.info("Generating draft justifications using rule-based engine...")
    justs = build_all_justifications(df)
    df["Risk Justification"] = justs

    # Optional LLM polishing
    if use_llm:
        if not HF_TOKEN:
            st.error("LLM enabled but no HF_API_TOKEN set in Streamlit Secrets. Disable LLM or add the token.")
        else:
            st.info("Polishing with open-source LLM...")
            # Precompute 3σ thresholds once (in case you later show stats or payload needs them)
            inv_mean, inv_std, inv_lo, inv_hi = three_sigma_levels(df["Inventory"])
            fa_mean, fa_std, fa_lo, fa_hi   = three_sigma_levels(df["Flammable Affected Area"])

            polished = []
            for i, r in df.iterrows():
                # Prepare payload for guardrails (facts handed to model)
                try:
                    gov_letter, drivers = governing_cof(
                        r["Flamm Conseq Categ"],
                        r["Toxic Conseq Cat"],
                        r["Lost Production Category"]
                    )
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
                except Exception:
                    payload = {}

                draft = df.at[i, "Risk Justification"]
                try:
                    mt = polish_with_hf(model_id, HF_TOKEN, payload, draft)
                    final = safe_keep_or_fallback(mt, payload, draft)  # falls back if facts missing
                    polished.append(final)
                except Exception as e:
                    # Keep draft if LLM fails for the row
                    polished.append(draft)

            df["Risk Justification"] = polished

    st.success("Done. Preview below and download Excel.")
    st.dataframe(df.head(20), use_container_width=True)

    # Download button
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Table1", index=False)
    st.download_button(
        "Download updated Excel",
        data=out.getvalue(),
        file_name="RBI_Justifications.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
