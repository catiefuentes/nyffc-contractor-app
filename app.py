import streamlit as st
import pandas as pd
from match_utils import CompanyMap
from fpdf import FPDF
import base64
from io import BytesIO
from tqdm.auto import tqdm
tqdm.pandas()

# ---------- SETUP ----------
st.set_page_config(page_title="NYFFC Contractor Lookup Tool", layout="wide")
st.title("🔍 NYFFC Contractor Search Tool")
st.markdown("Search by contractor **name or ZIP code** to view related records across datasets.")

# ---------- LOAD DATA ----------
@st.cache_data
def load_data():
    df_apprentice = pd.read_csv("cleaned_construction_apprentice.csv")
    df_wagetheft = pd.read_csv("cleaned_construction_wagetheft.csv")
    df_apprentice["signatory_name"] = df_apprentice["signatory_name"].str.lower().str.strip()
    df_wagetheft["company_name"] = df_wagetheft["company_name"].str.lower().str.strip()
    return df_apprentice, df_wagetheft

df_apprentice, df_wagetheft = load_data()

# Build matcher from wage theft dataset
matcher = CompanyMap(df_wagetheft, name_cols=["company_name"], addr_col="zip_cd")

# ---------- SEARCH ----------
query = st.text_input("🔎 Enter contractor name or ZIP code")

if query:
    query = query.lower().strip()

    filtered_apprentice = df_apprentice[
        df_apprentice.apply(lambda row: query in str(row.values).lower(), axis=1)
    ]

    if not filtered_apprentice.empty:
        with st.spinner("🔄 Matching records using fuzzy name/address matching..."):
            matches = filtered_apprentice.progress_apply(
                lambda x: matcher.get_match_idx(
                    x[["signatory_name"]], x["zip_code"], threshold=95, avg_threshold=80
                ), axis=1
            )

            matched_rows = []
            for idx_list in matches:
                if idx_list:
                    for idx in idx_list:
                        apprentice_row = filtered_apprentice.iloc[matches.index[idx]]
                        wage_row = df_wagetheft.iloc[idx]
                        merged = {**apprentice_row.to_dict(), **wage_row.to_dict()}
                        matched_rows.append(merged)

            matched_df = pd.DataFrame(matched_rows)
    else:
        matched_df = pd.DataFrame()

    # ---------- RESULTS ----------
    if not matched_df.empty:
        st.subheader("🧾 Contractor Match Results")

        for _, row in matched_df.iterrows():
            with st.container():
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**🏢 Company:** {row.get('company_name', 'Unknown').title()}")
                    st.markdown(f"**🔧 Trade:** {row.get('trade', 'N/A')}")
                    st.markdown(f"**📍 ZIP Code:** {row.get('zip_cd', 'N/A')}")
                with col2:
                    st.markdown(f"**💰 Wages Stolen:** ${row.get('wages_stolen', 0):,.2f}")
                    confidence = row.get('avg_score', 0)
                    emoji = "✅" if confidence > 90 else ("⚠️" if confidence > 80 else "🆘")
                    st.markdown(f"**📈 Match Confidence:** {emoji} {confidence:.2f}%")
                st.markdown("---")

        st.download_button("📥 Download Matched Results (CSV)",
                           data=matched_df.to_csv(index=False),
                           file_name="nyffc_contractor_matches.csv",
                           mime="text/csv")

        # ---------- PDF REPORT ----------
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
---""")
            return pdf.output(dest='S').encode('latin1')

        pdf_bytes = generate_pdf(matched_df)
        b64 = base64.b64encode(pdf_bytes).decode()
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="nyffc_match_report.pdf">📄 Download Match Report (PDF)</a>'
        st.markdown(href, unsafe_allow_html=True)

    else:
        st.warning("No high-confidence matches found using fuzzy logic.")

st.markdown("---")
st.caption("Built for NYFFC · v1.0")
