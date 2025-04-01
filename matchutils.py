import streamlit as st
import pandas as pd
from match_utils import fuzzy_join
from fpdf import FPDF
import base64
from io import BytesIO

# ---------- SETUP ----------
st.set_page_config(page_title="NYFFC Contractor Lookup Tool", layout="wide")
st.title("🔍 NYFFC Contractor Search Tool")
st.markdown("Search by contractor **name or ZIP code** to view related records across datasets.")

# ---------- LOAD DATA ----------
df_apprentice = pd.read_csv("cleaned_construction_apprentice.csv")
df_wagetheft = pd.read_csv("cleaned_construction_wagetheft.csv")

# ---------- CLEANING / STANDARDIZATION ----------
df_apprentice["signatory_name"] = df_apprentice["signatory_name"].str.lower().str.strip()
df_wagetheft["company_name"] = df_wagetheft["company_name"].str.lower().str.strip()

# ---------- SEARCH INTERFACE ----------
query = st.text_input("🔎 Enter contractor name or ZIP code")

if query:
    query = query.lower().strip()

    # Filter df_apprentice for candidate records
    filtered_apprentice = df_apprentice[
        df_apprentice.apply(lambda row: query in str(row.values).lower(), axis=1)
    ]

    # Run fuzzy join only if candidate records found
    if not filtered_apprentice.empty:
        st.write("🔄 Matching records using fuzzy name/address matching...")
        matched_df = fuzzy_join(filtered_apprentice, df_wagetheft)
    else:
        matched_df = pd.DataFrame()

    # ---------- RESULTS ----------
    if not matched_df.empty:
        st.subheader("🧾 Contractor Match Results")

        for _, row in matched_df.iterrows():
            with st.container():
                st.markdown(f"""
                <div style='border:2px solid #ccc;padding:15px;border-radius:10px;margin-bottom:15px;'>
                    <h4>🏢 <b>{row.get('company_name', 'Unknown').title()}</b></h4>
                    <p><b>Trade:</b> {row.get('trade', 'N/A')}</p>
                    <p><b>Zip Code:</b> {row.get('zip_cd', 'N/A')}</p>
                    <p><b>Wages Stolen:</b> ${row.get('wages_stolen', 0):,.2f}</p>
                    <p><b>Match Confidence:</b> {row.get('avg_score', 0):.2f}%</p>
                </div>
                """, unsafe_allow_html=True)

        st.download_button("📥 Download Matched Results (CSV)",
                           data=matched_df.to_csv(index=False),
                           file_name="nyffc_contractor_matches.csv",
                           mime="text/csv")

        # ---------- MATCH REPORT PDF ----------
        def generate_pdf(df):
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            pdf.set_font("Arial", size=12)

            pdf.cell(200, 10, txt="NYFFC Contractor Match Report", ln=True, align='C')
            pdf.ln(10)

            for _, row in df.iterrows():
                pdf.multi_cell(0, 10, txt=f"""
Contractor: {row.get('company_name', 'N/A').title()}
Trade: {row.get('trade', 'N/A')}
Zip: {row.get('zip_cd', 'N/A')}
Wages Stolen: ${row.get('wages_stolen', 0):,.2f}
Match Confidence: {row.get('avg_score', 0):.2f}%
---
                """)

            return pdf.output(dest='S').encode('latin1')

        pdf_bytes = generate_pdf(matched_df)
        b64 = base64.b64encode(pdf_bytes).decode()
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="nyffc_match_report.pdf">📄 Download Match Report (PDF)</a>'
        st.markdown(href, unsafe_allow_html=True)

    else:
        st.warning("No high-confidence matches found using fuzzy logic.")

st.markdown("---")
st.caption("Built for NYFFC · v1.0")
