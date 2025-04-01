import streamlit as st
import pandas as pd
from rapidfuzz import process, fuzz

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

# ---------- FUZZY MATCHING ----------
def fuzzy_match(name, choices, threshold=85):
    match = process.extractOne(name, choices, scorer=fuzz.partial_ratio, score_cutoff=threshold)
    return match[0] if match else None

df_apprentice["matched_wagetheft_name"] = df_apprentice["signatory_name"].apply(
    lambda x: fuzzy_match(x, df_wagetheft["company_name"].dropna().unique())
)

# ---------- SEARCH INTERFACE ----------
query = st.text_input("🔎 Enter contractor name or ZIP code")

if query:
    query = query.lower().strip()

    # Define columns to search
    apprentice_cols = ["signatory_name", "signatory_address", "zip_code"]
    wagetheft_cols = ["company_name", "zip_code"]

    apprentice_matches = df_apprentice[
        df_apprentice[apprentice_cols].apply(
            lambda row: row.astype(str).str.contains(query, case=False, na=False).any(), axis=1)
    ]

    wagetheft_matches = df_wagetheft[
        df_wagetheft[wagetheft_cols].apply(
            lambda row: row.astype(str).str.contains(query, case=False, na=False).any(), axis=1)
    ]

    # ---------- RESULTS ----------
    st.subheader("🧾 Contractor ID Card")

    if not apprentice_matches.empty or not wagetheft_matches.empty:
        with st.container():
            if not apprentice_matches.empty:
                st.markdown("### 📘 Apprenticeship Info")
                st.dataframe(apprentice_matches)

            if not wagetheft_matches.empty:
                st.markdown("### ⚖️ Wage Theft Info")
                st.dataframe(wagetheft_matches)
    else:
        st.warning("No results found for that contractor name or ZIP code.")

st.markdown("---")
st.caption("Built for NYFFC · v1.0")
