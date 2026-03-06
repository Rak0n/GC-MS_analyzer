# GC-MS_analyzer
🧪 GC-MS Data Insights: From Raw CSV to Molecular Intelligence An interactive Streamlit web-app to automate GC-MS data processing, chemical enrichment via PubChem, and 2D molecular visualization. Designed for chemists who need fast, validated, and insightful reports.
# ⚗️ GC-MS Analyzer

Automate your chemical analysis workflow. This app transforms raw GC-MS outputs into structured, enriched Excel reports with molecular insights.

### 🚀 Features
* **Smart Cleaning:** Filter by Match Factor and recalculate Area % instantly.
* **Human-in-the-loop:** Export to Excel, refine names, and re-import.
* **Chemical Intelligence:** Automatic fetching of Molecular Formulas and Atom Counts via PubChem API.
* **Visual Dashboard:** 2D structure rendering for identified compounds using RDKit.

### 🛠️ Tech Stack
* **Frontend:** [Streamlit](https://streamlit.io/)
* **Chemistry:** [RDKit](https://www.rdkit.org/), [PubChemPy](https://github.com/mcs07/PubChemPy)
* **Data:** [Pandas](https://pandas.pydata.org/), [XlsxWriter](https://xlsxwriter.readthedocs.io/)

### 📖 How to use
1. Upload your raw CSV files.
2. Download the formatted Excel and validate compound names.
3. Re-upload the validated Excel for full molecular enrichment.
