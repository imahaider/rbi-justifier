import os, sys
ROOT = os.path.dirname(os.path.dirname(__file__))  # repo root
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import io
import json
import streamlit as st
import pandas as pd

from core.schema import missing_columns, REQUIRED_COLUMNS
from core.generator import build_all_justifications
from core.rules import three_sigma_levels, classify_three_sigma, governing_cof
from core.validate import safe_keep_or_fallback
from core.llm import polish_with_hf

# --------------------------- Modern Look: page config + CSS ---------------------------
st.set_page_config(page_title="RBI Risk Justification Generator", page_icon="🛠️", layout="wide")

# Global CSS: safe, responsive, no clipping
st.markdown("""
<style>
/* Container sizing for consistent alignment */
.block-container {
  padding-top: 1.0rem !important;    /* slightly tighter */
  padding-bottom: 2rem !important;
  max-width: 1200px;
}

/* Make the default Streamlit H1 look modern without clipping */
h1 {
  font-weight: 800 !important;
  line-height: 1.15 !important;
  letter-spacing: 0.2px;
  margin: 0 0 0.25rem 0 !important;  /* tighter space under title */
  background: linear-gradient(90deg,#0ea5e9,#22c55e,#a855f7);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

/* Gray title note directly under the title */
.title-note {
  color: #6b7280;                    /* gray-500 */
  font-size: 0.92rem;
  margin: 0 0 0.75rem 0;             /* tight under-note spacing */
}

/* Subtitle under the note (if needed later) */
.app-subtitle{
  color: #334155; font-size: 0.98rem; margin: 0 0 1.0rem 0;
}

/* Card styles */
.card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 16px 18px;
  box-shadow: 0 2px 10px rgba(2,6,23,0.06);
  margin-bottom: 14px;
}

/* Mini cards for compact info */
.mini-card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 10px 12px;
  box-shadow: 0 1px 6px rgba(2,6,23,0.05);
  font-size: 0.86rem;
  color: #334155;
}

/* Badges */
.badge {
  display: inline-block; padding: 4px 10px; border-radius: 9999px; font-size: 0.78rem;
  font-weight: 600; border: 1px solid #d1d5db; color: #111827; background: #f9fafb;
}
.badge-green { border-color:#86efac; background:#ecfdf5; color:#065f46; }
.badge-blue  { border-color:#93c5fd; background:#eff6ff; color:#1e3a8a; }
.badge-violet{ border-color:#c4b5fd; background:#f5f3ff; color:#4c1d95; }

/* Buttons */
.stButton>button, .stDownloadButton>button {
  border-radius: 9999px; padding: 0.5rem 1rem; font-weight: 600;
  border: 1px solid #e5e7eb;
}
.stDownloadButton>button {
  background: linear-gradient(90deg,#0ea5e9,#22c55e,#a855f7); color: white; border: none;
}

/* Dataframe frame */
[data-testid="stDataFrame"] div[role="table"] {
  border-radius: 12px; overflow: hidden; border: 1px solid #e5e7eb;
}

/* Sidebar spacing */
section[data-testid="stSidebar"] .block-container {padding: 1rem;}

/* ----- Tighten gap between the badge and file uploader ----- */
.badge-row { margin-bottom: 4px; }  /* small space under the badge */
div[data-testid="stFileUploader"] > div:first-child { margin-top: 0.25rem; }  /* pull uploader closer */
div[data-testid="stFileUploader"] { padding-top: 0rem; }

/* Footer */
.footer {
  margin-top: 1.5rem; 
  color: #6b7280;
  text-align: center;
  font-size: 0.9rem;
  padding-top: 0.5rem;
  border-top: 1px solid #e5e7eb;
}
</style>
""", unsafe_allow_html=True)

# --------------------------- Header ---------------------------
st.title("RBI Risk Justification Generator")
st.markdown('<div class="title-note">Developed by Muhammad Ali Haider</div>', unsafe_allow_html=True)

# --------------------------- Sidebar ---------------------------
with st.sidebar:
   
    # st.header("LLM Polishing")
    # use_llm = st.toggle("Use open-source LLM polishing", value=False)
    # st.caption("Enable to paraphrase grammar and flow without changing facts.")
    # model_id = st.text_input("Hugging Face model id", value="Qwen/Qwen2.5-7B-Instruct")
    # st.caption("You must accept the model license on your HF account.")
    
    st.header("About")
    st.write("Upload your Excel in the standard template. The app will add a **Risk Justification** for each component of RBI Analysis by using the data provided.<br>"
    "Future Update, Optional LLM polishing using AI is planned.",
    unsafe_allow_html=True)
    

    st.markdown("---")
    
    st.header("Jusification Sheet Template")
    try:
        template_path = "template/Justification_Sheet_Example_Template.xlsx"  # repo path
        with open(template_path, "rb") as f:
            st.download_button(
                label="📥 Download Jusification Sheet Template",
                data=f,
                file_name="Justification_Sheet_Example_Template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
    except FileNotFoundError:
        st.warning("Template not found in the repo at: examples/Justification Sheet Example Template.xlsx")
        
    st.markdown("---")
    st.header("Info")
    st.write("Mandatory columns:")
    st.code("\n".join(REQUIRED_COLUMNS), language="text")

#hf_token = st.secrets.get("HF_API_TOKEN", None)

# --------------------------- Main: concise upload row ---------------------------
# Small info row (optional mini cards)
i1, i2 = st.columns([1, 1])
with i1:
    st.markdown('<div class="mini-card"><b>Tips</b><br/>Use exact column names. CoF letters A–E; PoF integers 1–5.</div>', unsafe_allow_html=True)
with i2:
    st.markdown('<div class="mini-card"><b>Output</b><br/>Adds: <code>Risk Justification</code> column for every component.</div>', unsafe_allow_html=True)

# Blue badge and uploader with minimal gap
st.markdown('<div class="badge-row"><span class="badge badge-blue"> Upload Excel (.xlsx) file as per required Template Format</span></div>', unsafe_allow_html=True)
uploaded = st.file_uploader("", type=["xlsx"])

# --------------------------- Core Logic ---------------------------
if uploaded:
    with st.spinner("Reading and validating your Excel..."):
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
    with st.spinner("Generating justifications using rule-based engine..."):
        justs = build_all_justifications(df)
        df["Risk Justification"] = justs

    ### Optional LLM polishing
 
    # if use_llm:
    #     if not hf_token:
    #         st.error("LLM enabled but no HF_API_TOKEN set in Streamlit Secrets.")
    #     else:
    #         st.info("Polishing with open-source LLM...")
    #         # Pre-compute stats for inventory and FAA so payload can include levels if you wish
    #         inv_mean, inv_std, inv_lo, inv_hi = three_sigma_levels(df["Inventory"])
    #         fa_mean, fa_std, fa_lo, fa_hi   = three_sigma_levels(df["Flammable Affected Area"])

    #         polished = []
    #         for i, r in df.iterrows():
    #             # Prepare payload for guardrails
    #             gov_letter, drivers = governing_cof(r["Flamm Conseq Categ"], r["Toxic Conseq Cat"], r["Lost Production Category"])
    #             inv_level = classify_three_sigma(r["Inventory"], inv_lo, inv_hi)
    #             fa_level  = classify_three_sigma(r["Flammable Affected Area"], fa_lo, fa_hi)
    #             payload = {
    #                 "component": r["Component"],
    #                 "risk_category": str(r["Risk Category"]),
    #                 "pof": int(r["Driving PoF"]) if pd.notnull(r["Driving PoF"]) else None,
    #                 "int_corr_rate": float(r["Int Corr Rate"]) if pd.notnull(r["Int Corr Rate"]) else None,
    #                 "ext_corr_rate": float(r["Ext Corr Rate"]) if pd.notnull(r["Ext Corr Rate"]) else None,
    #                 "inspection_priority": int(r["Inspection Priority"]) if pd.notnull(r["Inspection Priority"]) else None,
    #                 "flamm_cat": str(r["Flamm Conseq Categ"]),
    #                 "tox_cat": str(r["Toxic Conseq Cat"]),
    #                 "prod_cat": str(r["Lost Production Category"]),
    #                 "governing_cof": gov_letter,
    #                 "governing_sources": list(drivers.keys()),
    #                 "inventory_level": inv_level,
    #                 "flamm_area_level": fa_level,
    #                 "fluid_type": str(r["Fluid Type"]),
    #                 "fluid": str(r["Representative Fluid"]),
    #                 "phase": str(r["Initial Fluid Phase"]),
    #                 "toxic": str(r["Toxic Fluid"]),
    #             }
    #             draft = df.at[i, "Risk Justification"]
    #             try:
    #                 mt = polish_with_hf(model_id, hf_token, payload, draft)
    #                 safe = safe_keep_or_fallback(mt, payload, draft)
    #                 polished.append(safe)
    #             except Exception:
    #                 polished.append(draft)

    #         df["Risk Justification"] = polished

    st.success("Justifications generated successfully.")

    # Preview
    st.markdown("### Preview")
    st.dataframe(df.head(20), use_container_width=True)

    # Download button
    st.markdown("### Export")
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Table1", index=False)
    st.download_button(
        "Download updated Excel with Justifications",
        data=out.getvalue(),
        file_name="RBI_Justifications.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# --------------------------- Footer ---------------------------
st.markdown('<div class="footer">© 2025 Muhammad Ali Haider. All rights reserved.</div>', unsafe_allow_html=True)
