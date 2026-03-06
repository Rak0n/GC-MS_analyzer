import streamlit as st
import pandas as pd
import io
import re
import time
import pubchempy as pcp

# Gestione robusta dell'import di RDKit
try:
    from rdkit import Chem
    from rdkit.Chem import Draw
    RDKIT_AVAILABLE = True
except ImportError as e:
    RDKIT_AVAILABLE = False
    
import xlsxwriter

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="GC-MS Analyzer Pro", page_icon="🧪", layout="wide")

# --- FUNZIONI DI UTILITA' E CACHING ---
@st.cache_data(show_spinner=False)
def get_pubchem_data(compound_name):
    """
    Interroga PubChem. La cache assicura che lo stesso composto non venga
    MAI cercato due volte (né nella stessa sessione, né in sessioni diverse finché la cache vive).
    """
    try:
        results = pcp.get_compounds(compound_name, 'name')
        if results:
            comp = results[0]
            # Restituiamo formula, peso molecolare e SMILES per RDKit
            return comp.molecular_formula, comp.isomeric_smiles, comp.molecular_weight
        else:
            return "Non Trovato", None, None
    except Exception as e:
        return "Errore API", None, None

def estrai_atomi(formula, elemento):
    """Estrae il numero di atomi dalla formula bruta."""
    if not isinstance(formula, str) or formula in ["Non Trovato", "Errore API", "N/A"]:
        return 0
    match = re.search(elemento + r'(\d*)', formula)
    if match:
        return int(match.group(1)) if match.group(1) else 1
    return 0

def classifica_famiglia(nome, smiles):
    """Logica condizionale semplice per classificare i composti."""
    nome_lower = str(nome).lower()
    if 'phthalate' in nome_lower or 'ftalato' in nome_lower:
        return "Plastica / Contaminante 🔴"
    elif 'acid' in nome_lower or 'acido' in nome_lower:
        return "Acido Organico 🟡"
    elif 'phenol' in nome_lower or 'fenolo' in nome_lower:
        return "Fenolico (Bio-oil) 🟢"
    else:
        return "Altro ⚪"

# --- INIZIALIZZAZIONE SESSION STATE ---
if 'enriched_data' not in st.session_state:
    st.session_state.enriched_data = None

# --- UI: TITOLO E TABS ---
st.title("🧪 GC-MS Data Processing & Cheminformatics Dashboard")
st.markdown("Un'unica piattaforma per pulire, arricchire e visualizzare i tuoi dati GC-MS.")

tab1, tab2, tab3 = st.tabs(["1️⃣ Data Processing (CSV -> Excel)", "2️⃣ Enrichment (PubChem)", "3️⃣ Interactive Dashboard"])

# ==========================================
# TAB 1: DATA PROCESSING
# ==========================================
with tab1:
    st.header("Fase 1: Normalizzazione Dati Grezzi")
    st.info("Carica i file CSV generati dallo strumento GC-MS. Verrà creato un file Excel con formule dinamiche.")
    
    uploaded_csvs = st.file_uploader("Seleziona i file CSV", type="csv", accept_multiple_files=True)
    
    if uploaded_csvs:
        if st.button("Genera Excel Elaborato"):
            # Usiamo un buffer in memoria invece di salvare su disco
            output_buffer = io.BytesIO()
            
            with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
                workbook = writer.book
                
                # Definizione stili (presi dal tuo script)
                input_fmt = workbook.add_format({'bg_color': '#FFF2CC', 'border': 1, 'bold': True, 'align': 'center', 'valign': 'vcenter'})
                header_fmt = workbook.add_format({'bold': True, 'bottom': 2, 'bg_color': '#D9D9D9', 'align': 'center'})
                gray_strikethrough_fmt = workbook.add_format({'bg_color': '#F2F2F2', 'font_color': '#A6A6A6', 'font_strikeout': True})
                num_fmt = workbook.add_format({'num_format': '0.00'})
                sci_fmt = workbook.add_format({'num_format': '0.00E+00'})
                bold_fmt = workbook.add_format({'bold': True})
                
                for uploaded_file in uploaded_csvs:
                    sheet_name = uploaded_file.name.replace('.csv', '')[:31]
                    df = pd.read_csv(uploaded_file)
                    df = df.sort_values(by='Component Area', ascending=False).reset_index(drop=True)
                    
                    start_row, num_rows = 5, len(df)
                    last_row = start_row + num_rows
                    worksheet = workbook.add_worksheet(sheet_name)
                    
                    # Pannello di Controllo
                    worksheet.write('B2', 'Soglia Match Factor:', bold_fmt)
                    worksheet.write('C2', 60, input_fmt)
                    worksheet.write('E2', 'Area Totale Originale:', bold_fmt)
                    worksheet.write_formula('F2', f'=SUM(D6:D{last_row})', sci_fmt) 
                    worksheet.write('E3', 'Nuova Area Totale:', bold_fmt)
                    worksheet.write_formula('F3', f'=SUM(F6:F{last_row})', sci_fmt) 
                    
                    # Intestazioni e Dati
                    headers = list(df.columns) + ['New Component Area', 'New Area %']
                    for col_num, header in enumerate(headers):
                        worksheet.write(4, col_num, header, header_fmt)
                        
                    for row_num in range(num_rows):
                        xl_row = start_row + row_num + 1
                        worksheet.write(start_row + row_num, 0, df.iloc[row_num]['Component RT'], num_fmt)
                        worksheet.write(start_row + row_num, 1, df.iloc[row_num]['Compound Name'])
                        worksheet.write(start_row + row_num, 2, df.iloc[row_num]['Match Factor'], num_fmt)
                        worksheet.write(start_row + row_num, 3, df.iloc[row_num]['Component Area'], sci_fmt)
                        worksheet.write(start_row + row_num, 4, df.iloc[row_num]['Area %'], num_fmt)
                        worksheet.write_formula(start_row + row_num, 5, f'=IF(C{xl_row}<$C$2, 0, D{xl_row})', sci_fmt)
                        worksheet.write_formula(start_row + row_num, 6, f'=IF($F$3>0, (F{xl_row}/$F$3)*100, 0)', num_fmt)
                        
                    # Formattazione
                    worksheet.set_column('A:A', 14); worksheet.set_column('B:B', 38); worksheet.set_column('C:C', 15)
                    worksheet.set_column('D:D', 18); worksheet.set_column('E:E', 10); worksheet.set_column('F:F', 20); worksheet.set_column('G:G', 14)
                    
                    worksheet.conditional_format(f'A6:G{last_row}', {'type': 'formula', 'criteria': '=$C6<$C$2', 'format': gray_strikethrough_fmt})
                    worksheet.freeze_panes(5, 0)
            
            st.success("File Excel generato con successo!")
            st.download_button(
                label="⬇️ Scarica Risultati_GCMS_Elaborati.xlsx",
                data=output_buffer.getvalue(),
                file_name="Risultati_GCMS_Elaborati.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# ==========================================
# TAB 2: ENRICHMENT (PUBCHEM)
# ==========================================
with tab2:
    st.header("Fase 2: Arricchimento tramite PubChem")
    st.info("Carica il file Excel che hai scaricato dalla Fase 1 (e di cui hai validato i nomi).")
    
    uploaded_excel = st.file_uploader("Carica file Excel (.xlsx)", type="xlsx")
    
    if uploaded_excel:
        if st.button("🚀 Avvia Arricchimento PubChem"):
            xls = pd.ExcelFile(uploaded_excel)
            dati_elaborati = {}
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for sheet_idx, sheet_name in enumerate(xls.sheet_names):
                status_text.text(f"Elaborazione foglio: {sheet_name}...")
                
                # Logica per trovare l'header corretto
                df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                header_idx = 0
                for idx, row in df_raw.iterrows():
                    if 'Compound Name' in row.values:
                        header_idx = idx
                        break
                
                df = pd.read_excel(xls, sheet_name=sheet_name, header=header_idx)
                
                if 'Compound Name' not in df.columns:
                    st.warning(f"Nessuna colonna 'Compound Name' in {sheet_name}. Foglio saltato.")
                    continue
                
                # Liste per i nuovi dati
                formule, c_list, o_list, n_list, oc_list = [], [], [], [], []
                smiles_list, pesi_list, famiglie_list = [], [], []
                
                total_rows = len(df)
                for index, row in df.iterrows():
                    nome_composto = str(row['Compound Name']).strip()
                    
                    if pd.isna(nome_composto) or nome_composto.lower() in ['nan', 'none', '']:
                        formula, smiles, peso = "N/A", None, None
                    else:
                        # Chiamata API (caching automatico!)
                        formula, smiles, peso = get_pubchem_data(nome_composto)
                        time.sleep(0.1) # Breve pausa per rispetto delle API, anche se la cache aiuta
                    
                    formule.append(formula)
                    smiles_list.append(smiles)
                    pesi_list.append(peso)
                    famiglie_list.append(classifica_famiglia(nome_composto, smiles))
                    
                    c = estrai_atomi(formula, 'C')
                    o = estrai_atomi(formula, 'O')
                    n = estrai_atomi(formula, 'N')
                    
                    c_list.append(c); o_list.append(o); n_list.append(n)
                    oc_list.append(round(o/c, 3) if c > 0 else None)
                    
                    # Aggiorna progress bar
                    progress_pct = int(((index + 1) / total_rows) * 100)
                    progress_bar.progress(progress_pct)

                df['Formula Bruta'] = formule
                df['SMILES'] = smiles_list
                df['Peso Molecolare'] = pesi_list
                df['Famiglia Assegnata'] = famiglie_list
                df['Atomi_C'] = c_list
                df['Atomi_O'] = o_list
                df['Atomi_N'] = n_list
                df['Rapporto O/C'] = oc_list
                
                dati_elaborati[sheet_name] = df
            
            # Salva i dati in session state per la Tab 3
            st.session_state.enriched_data = dati_elaborati
            status_text.text("Elaborazione completata! Passa alla Tab 3 per la Dashboard.")
            st.success("Dati arricchiti con successo!")

# ==========================================
# TAB 3: INTERACTIVE DASHBOARD
# ==========================================
with tab3:
    st.header("Fase 3: Visualizzazione Interattiva")
    
    if st.session_state.enriched_data is None:
        st.warning("⚠️ Esegui prima l'arricchimento dei dati nella Tab 2 per visualizzare la dashboard.")
    else:
        # Seleziona il foglio da visualizzare
        sheet_selezionato = st.selectbox("Seleziona il Campione (Foglio)", list(st.session_state.enriched_data.keys()))
        df_display = st.session_state.enriched_data[sheet_selezionato]
        
        # Puliamo il DF per la visualizzazione (nascondiamo lo SMILES per ordine)
        cols_to_show = ['Component RT', 'Compound Name', 'Match Factor', 'Component Area', 'Formula Bruta', 'Peso Molecolare', 'Famiglia Assegnata', 'Rapporto O/C']
        df_visual = df_display[[c for c in cols_to_show if c in df_display.columns]]
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Dati del Campione")
            # Usiamo la nuova funzionalità on_select di Streamlit per intercettare il click
            event = st.dataframe(
                df_visual,
                use_container_width=True,
                selection_mode="single-row",
                on_select="rerun"
            )
        
        with col2:
            st.subheader("Dettaglio Molecola")
            # Gestione della selezione riga
            selected_rows = event.selection.rows
            
            if len(selected_rows) > 0:
                row_idx = selected_rows[0]
                dati_riga = df_display.iloc[row_idx]
                
                st.markdown(f"**Composto:** {dati_riga['Compound Name']}")
                st.markdown(f"**Formula:** {dati_riga.get('Formula Bruta', 'N/A')}")
                st.markdown(f"**Famiglia:** {dati_riga.get('Famiglia Assegnata', 'N/A')}")
                
                smiles = dati_riga.get('SMILES', None)
                if smiles and pd.notna(smiles):
                    if RDKIT_AVAILABLE:
                        try:
                            # RDKit per disegnare la molecola
                            mol = Chem.MolFromSmiles(smiles)
                            if mol:
                                img = Draw.MolToImage(mol, size=(300, 300))
                                st.image(img, caption="Struttura 2D")
                            else:
                                st.warning("Impossibile generare l'immagine da questo SMILES.")
                        except:
                            st.error("Errore nella generazione RDKit.")
                    else:
                        st.error("⚠️ **Visualizzazione molecolare disabilitata.**")
                        st.info("Su Streamlit Cloud mancano alcune librerie di sistema necessarie a RDKit.\n\n**Per risolvere il problema:**\n1. Crea un file chiamato `packages.txt` nella tua repository GitHub.\n2. Inserisci al suo interno queste librerie:\n\n`libxrender1`\n`libsm6`\n`libxext6`\n\n3. Riavvia l'app da Streamlit Cloud.")
                else:
                    st.info("Nessuna struttura SMILES disponibile per questo composto.")
            else:
                st.info("👈 Clicca su una riga della tabella per visualizzare la struttura chimica.")
