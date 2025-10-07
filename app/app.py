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

# --------------------------- Modern Look: page config + CSS ---------------------------
st.set_page_config(page_title="RBI Risk Justification Generator", page_icon="🛠️", layout="wide")

# Global CSS: safe, responsive, no clipping
st.markdown("""
<style>
/* Container sizing for consistent alignment */
.block-container {
  padding-top: 1.0rem !important;
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
.badge-blue  { border-color:#93c5fd; background:#eff6ff; color:#1e3a8a; }

/* Tighten gap between the badge and uploader */
.badge-row { margin-bottom: 2px; }
div[data-testid="stFileUploader"] { margin-top: -6px; }

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
    st.header("About")
    st.write(
        "Upload your Excel in the standard template. The app will add a **Risk Justification** "
        "for each component of RBI Analysis using your rule set. Optional LLM polishing is planned.",
        unsafe_allow_html=True
    )

    st.markdown("---")

    st.header("Justification Sheet Template")
    try:
        template_path = "template/Justification_Sheet_Example_Template.xlsx"  # repo path
        with open(template_path, "rb") as f:
            st.download_button(
                label="📥 Download Justification Sheet Template",
                data=f,
                file_name="Justification_Sheet_Example_Template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
    except FileNotFoundError:
        st.warning("Template not found in the repo at: template/Justification_Sheet_Example_Template.xlsx")
        
    st.markdown("---")
    st.header("Info")
    st.write("Mandatory columns:")
    from core.schema import REQUIRED_COLUMNS  # re-import safe here
    st.code("\n".join(REQUIRED_COLUMNS), language="text")

# --------------------------- Main: concise upload row ---------------------------
# Small info row (optional mini cards)
i1, i2 = st.columns([1, 1])
with i1:
    st.markdown('<div class="mini-card"><b>Tips</b><br/>Use exact column names. CoF letters A–E; PoF integers 1–5 (1 = highest likelihood).</div>', unsafe_allow_html=True)
with i2:
    st.markdown('<div class="mini-card"><b>Output</b><br/>Adds: <code>Risk Justification</code> for every component—reason-first, CCR-aware, non-generic.</div>', unsafe_allow_html=True)

# Blue badge and uploader with minimal gap
st.markdown('<div class="badge-row"><span class="badge badge-blue"> Upload Excel (.xlsx) file as per required Template Format</span></div>', unsafe_allow_html=True)
uploaded = st.file_uploader(
    "Upload Excel (.xlsx) file as per required Template Format",  # <- non-empty label to satisfy Streamlit
    type=["xlsx"],
    label_visibility="collapsed"  # keeps UI clean but avoids the warning
)

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

    with st.spinner("Generating justifications using the rules engine..."):
        justs = build_all_justifications(df)
        df["Risk Justification"] = justs

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
