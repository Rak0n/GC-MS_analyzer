import streamlit as st
import pandas as pd
import io
import re
import time
import os
import pubchempy as pcp
import plotly.express as px

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
    """Interroga PubChem con sistema di caching."""
    try:
        results = pcp.get_compounds(compound_name, 'name')
        if results:
            comp = results[0]
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

@st.cache_data
def load_rules(uploaded_file=None):
    """Carica il file csv delle regole di classificazione."""
    try:
        if uploaded_file is not None:
            return pd.read_csv(uploaded_file)
        elif os.path.exists("gcms_classification_rules.csv"):
            return pd.read_csv("gcms_classification_rules.csv")
        return None
    except Exception as e:
        st.error(f"Errore nel caricamento delle regole: {e}")
        return None

def classifica_famiglia(nome, rules_df):
    """Classifica il composto basandosi sul file CSV fornito."""
    nome_lower = str(nome).lower()
    
    if rules_df is not None and not rules_df.empty:
        for index, row in rules_df.iterrows():
            keyword = str(row['Keyword']).lower()
            if keyword in nome_lower:
                fam = str(row.get('Family', 'Sconosciuta'))
                sub = str(row.get('SubFamily', ''))
                # Se c'è una sottofamiglia valida, formattiamo "Famiglia - Sottofamiglia"
                if sub and sub.lower() != 'nan':
                    return f"{fam} - {sub}"
                return fam
        return "Altro / Non Classificato"
        
    # Fallback se non ci sono regole caricate
    if 'phthalate' in nome_lower or 'ftalato' in nome_lower:
        return "Plastica / Contaminante 🔴"
    elif 'acid' in nome_lower or 'acido' in nome_lower:
        return "Acido Organico 🟡"
    elif 'phenol' in nome_lower or 'fenolo' in nome_lower:
        return "Fenolico (Bio-oil) 🟢"
    else:
        return "Altro ⚪"

def esegui_arricchimento(dict_dfs, rules_df):
    """Esegue l'arricchimento PubChem su un dizionario di DataFrame."""
    dati_elaborati = {}
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Calcola il totale delle righe per la progress bar
    totale_righe_complessivo = sum(len(df) for df in dict_dfs.values())
    righe_processate = 0

    for sheet_name, original_df in dict_dfs.items():
        # FIX 1: Copia profonda per evitare conflitti di memoria in Streamlit durante il bypass
        df = original_df.copy()
        
        status_text.text(f"Elaborazione foglio: {sheet_name}...")
        
        if 'Compound Name' not in df.columns:
            st.warning(f"Nessuna colonna 'Compound Name' in {sheet_name}. Foglio saltato.")
            continue
        
        # FIX 2: Gestione intelligente delle formule Excel non calcolate
        if 'New Area %' in df.columns:
            df['New Area %'] = pd.to_numeric(df['New Area %'], errors='coerce')
            
            # Se troviamo NaN o zero totale (perché l'utente ha caricato l'Excel senza aprirlo/salvarlo)
            if df['New Area %'].isna().all() or df['New Area %'].sum() == 0:
                if 'Component Area' in df.columns and 'Match Factor' in df.columns:
                    st.info(f"💡 Ricalcolo automatico aree per '{sheet_name}' (le formule Excel non erano pre-calcolate).")
                    soglia = st.session_state.get('last_soglia', 60)
                    df['Match Factor'] = pd.to_numeric(df['Match Factor'], errors='coerce').fillna(0)
                    df['Component Area'] = pd.to_numeric(df['Component Area'], errors='coerce').fillna(0)
                    new_area = df.apply(lambda x: x['Component Area'] if x['Match Factor'] >= soglia else 0, axis=1)
                    tot = new_area.sum()
                    df['New Area %'] = new_area.apply(lambda x: (x/tot*100) if tot > 0 else 0)

            # Ora siamo sicuri che i numeri ci siano, applichiamo il filtro
            df = df[df['New Area %'] > 0].reset_index(drop=True)
        
        formule, c_list, o_list, n_list, oc_list = [], [], [], [], []
        smiles_list, pesi_list, famiglie_list = [], [], []
        
        for index, row in df.iterrows():
            nome_composto = str(row['Compound Name']).strip()
            
            if pd.isna(nome_composto) or nome_composto.lower() in ['nan', 'none', '']:
                formula, smiles, peso = "N/A", None, None
            else:
                formula, smiles, peso = get_pubchem_data(nome_composto)
                time.sleep(0.1)
            
            formule.append(formula)
            smiles_list.append(smiles)
            pesi_list.append(peso)
            
            famiglie_list.append(classifica_famiglia(nome_composto, rules_df))
            
            c = estrai_atomi(formula, 'C')
            o = estrai_atomi(formula, 'O')
            n = estrai_atomi(formula, 'N')
            
            c_list.append(c); o_list.append(o); n_list.append(n)
            oc_list.append(round(o/c, 3) if c > 0 else None)
            
            righe_processate += 1
            if totale_righe_complessivo > 0:
                progress_bar.progress(int((righe_processate / totale_righe_complessivo) * 100))

        df['Formula Bruta'] = formule
        df['SMILES'] = smiles_list
        df['Peso Molecolare'] = pesi_list
        df['Famiglia Assegnata'] = famiglie_list
        df['Atomi_C'] = c_list
        df['Atomi_O'] = o_list
        df['Atomi_N'] = n_list
        df['Rapporto O/C'] = oc_list
        
        if 'Component Area' in df.columns:
            df = df.drop(columns=['Component Area'])
        
        dati_elaborati[sheet_name] = df
    
    st.session_state.enriched_data = dati_elaborati
    status_text.text("Elaborazione completata! Puoi scaricare i risultati qui sotto o passare alla Tab 3.")
    st.success("Dati arricchiti con successo!")

# --- INIZIALIZZAZIONE SESSION STATE ---
if 'enriched_data' not in st.session_state:
    st.session_state.enriched_data = None
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None

# --- UI: SIDEBAR ISTRUZIONI ---
with st.sidebar:
    st.title("📖 Guida all'Uso")
    try:
        with open("manuale_istruzioni.md", "r", encoding="utf-8") as f:
            st.markdown(f.read())
    except FileNotFoundError:
        st.info("Benvenuto! Il manuale d'istruzioni dettagliato non è stato ancora caricato su GitHub come 'manuale_istruzioni.md'.")

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
    usa_demo = False
    
    # 1. GESTIONE FILE DEMO
    if not uploaded_csvs:
        st.info("💡 Non hai dati a disposizione in questo momento? Puoi provare le funzionalità dell'app con dei dati di test.")
        usa_demo = st.checkbox("Usa Dati di Esempio (Demo)")
        if usa_demo and not os.path.exists("sample_data.csv"):
            st.error("⚠️ File 'sample_data.csv' non trovato. Assicurati di averlo caricato su GitHub.")
            usa_demo = False

    soglia_match = st.slider("Soglia Match Factor (i composti sotto questo valore verranno azzerati):", 0, 100, 60)
    st.session_state.last_soglia = soglia_match # Memorizziamo la soglia scelta per la Fase 2

    if (uploaded_csvs or usa_demo) and st.button("Genera Excel Elaborato"):
        output_buffer = io.BytesIO()
        processed_dfs_for_state = {}
        
        with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # Definizione stili
            input_fmt = workbook.add_format({'bg_color': '#FFF2CC', 'border': 1, 'bold': True, 'align': 'center', 'valign': 'vcenter'})
            header_fmt = workbook.add_format({'bold': True, 'bottom': 2, 'bg_color': '#D9D9D9', 'align': 'center'})
            gray_strikethrough_fmt = workbook.add_format({'bg_color': '#F2F2F2', 'font_color': '#A6A6A6', 'font_strikeout': True})
            num_fmt = workbook.add_format({'num_format': '0.00'})
            sci_fmt = workbook.add_format({'num_format': '0.00E+00'})
            bold_fmt = workbook.add_format({'bold': True})
            
            files_to_process = uploaded_csvs if uploaded_csvs else ["sample_data.csv"]
            
            for file_obj in files_to_process:
                # Gestione se è un file vero o il percorso del file demo stringa
                if isinstance(file_obj, str):
                    sheet_name = "Campione_Demo"
                    df = pd.read_csv(file_obj)
                else:
                    sheet_name = file_obj.name.replace('.csv', '')[:31]
                    df = pd.read_csv(file_obj)
                    
                df = df.sort_values(by='Component Area', ascending=False).reset_index(drop=True)
                
                # FIX 3: Calcolo per st.session_state reso numericamente sicuro a prova di errore
                df_for_state = df.copy()
                df_for_state['Match Factor'] = pd.to_numeric(df_for_state['Match Factor'], errors='coerce').fillna(0)
                df_for_state['Component Area'] = pd.to_numeric(df_for_state['Component Area'], errors='coerce').fillna(0)
                
                df_for_state['New Component Area'] = df_for_state.apply(lambda x: x['Component Area'] if x['Match Factor'] >= soglia_match else 0, axis=1)
                tot_area = df_for_state['New Component Area'].sum()
                df_for_state['New Area %'] = df_for_state['New Component Area'].apply(lambda x: (x / tot_area * 100) if tot_area > 0 else 0)
                processed_dfs_for_state[sheet_name] = df_for_state

                start_row, num_rows = 5, len(df)
                last_row = start_row + num_rows
                worksheet = workbook.add_worksheet(sheet_name)
                
                worksheet.write('B2', 'Soglia Match Factor:', bold_fmt)
                worksheet.write('C2', soglia_match, input_fmt)
                worksheet.write('E2', 'Area Totale Originale:', bold_fmt)
                worksheet.write_formula('F2', f'=SUM(D6:D{last_row})', sci_fmt) 
                worksheet.write('E3', 'Nuova Area Totale:', bold_fmt)
                worksheet.write_formula('F3', f'=SUM(F6:F{last_row})', sci_fmt) 
                
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
                    
                worksheet.set_column('A:A', 14); worksheet.set_column('B:B', 38); worksheet.set_column('C:C', 15)
                worksheet.set_column('D:D', 18); worksheet.set_column('E:E', 10); worksheet.set_column('F:F', 20); worksheet.set_column('G:G', 14)
                
                worksheet.conditional_format(f'A6:G{last_row}', {'type': 'formula', 'criteria': '=$C6<$C$2', 'format': gray_strikethrough_fmt})
                worksheet.freeze_panes(5, 0)
        
        st.session_state.processed_data = processed_dfs_for_state
        
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
    
    # Tasto rapido per i "Pigri"
    if st.session_state.processed_data is not None:
        st.markdown("---")
        st.success("✨ **Scorciatoia disponibile!** Hai già elaborato dei dati in Fase 1.")
        if st.button("🚀 Bypassa il caricamento e vai diretto all'Arricchimento"):
            esegui_arricchimento(st.session_state.processed_data, rules_df)

    # 2. MENU A TENDINA PER LE REGOLE
    with st.expander("⚙️ Opzioni di Classificazione Famiglie"):
        st.write("Di default l'app usa il file `gcms_classification_rules.csv` caricato su GitHub.")
        uploaded_rules = st.file_uploader("Carica un file di regole alternativo (opzionale)", type="csv")
    
    # Caricamento regole (Custom o Default)
    rules_df = load_rules(uploaded_rules)
    if rules_df is not None:
        st.success(f"✅ Regole caricate: {len(rules_df)} parole chiave pronte per il match.")
    else:
        st.warning("⚠️ Nessun file di regole trovato. Verrà usata la classificazione di base.")

    if uploaded_excel:
        if st.button("🚀 Avvia Arricchimento PubChem dal File"):
            xls = pd.ExcelFile(uploaded_excel)
            dict_dfs = {}
            for sheet_name in xls.sheet_names:
                df_raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)
                header_idx = 0
                for idx, row in df_raw.iterrows():
                    if 'Compound Name' in row.values:
                        header_idx = idx
                        break
                df = pd.read_excel(xls, sheet_name=sheet_name, header=header_idx)
                dict_dfs[sheet_name] = df
            
            esegui_arricchimento(dict_dfs, rules_df)

    if st.session_state.enriched_data is not None:
        output_buffer_enriched = io.BytesIO()
        with pd.ExcelWriter(output_buffer_enriched, engine='xlsxwriter') as writer:
            for sheet, df_out in st.session_state.enriched_data.items():
                df_out.to_excel(writer, sheet_name=sheet, index=False)
        
        st.download_button(
            label="⬇️ Scarica Risultati_GCMS_Arricchiti.xlsx",
            data=output_buffer_enriched.getvalue(),
            file_name="Risultati_GCMS_Arricchiti.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ==========================================
# TAB 3: INTERACTIVE DASHBOARD
# ==========================================
with tab3:
    st.header("Fase 3: Visualizzazione Interattiva")
    
    if st.session_state.enriched_data is None:
        st.warning("⚠️ Esegui prima l'arricchimento dei dati nella Tab 2 per visualizzare la dashboard.")
    else:
        sheet_selezionato = st.selectbox("Seleziona il Campione (Foglio)", list(st.session_state.enriched_data.keys()))
        df_display = st.session_state.enriched_data[sheet_selezionato]
        
        # 3. GRAFICO A TORTA DELLE FAMIGLIE
        st.subheader("📊 Distribuzione Famiglie")
        # Conta le frequenze delle famiglie escludendo i nulli
        family_counts = df_display['Famiglia Assegnata'].value_counts().reset_index()
        family_counts.columns = ['Famiglia', 'Conteggio Composti']
        
        if not family_counts.empty:
            # Creazione del grafico Plotly (Hole crea un grafico a ciambella, molto elegante)
            fig = px.pie(family_counts, values='Conteggio Composti', names='Famiglia', 
                         hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_layout(height=400, margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nessun dato sulle famiglie disponibile per questo foglio.")
            
        st.divider() # Linea di separazione
        
        # Visualizzazione Tabella
        cols_to_show = ['Component RT', 'Compound Name', 'Match Factor', 'New Area %', 'Formula Bruta', 'Peso Molecolare', 'Famiglia Assegnata', 'Rapporto O/C']
        df_visual = df_display[[c for c in cols_to_show if c in df_display.columns]]
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Dati del Campione")
            event = st.dataframe(
                df_visual,
                use_container_width=True,
                selection_mode="single-row",
                on_select="rerun"
            )
        
        with col2:
            st.subheader("Dettaglio Molecola")
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
                        st.info("Su Streamlit Cloud mancano alcune librerie di sistema necessarie a RDKit.\n\n**Per risolvere:** Inserisci in `packages.txt`:\n`libxrender1`\n`libsm6`\n`libxext6`")
                else:
                    st.info("Nessuna struttura SMILES disponibile per questo composto.")
            else:
                st.info("👈 Clicca su una riga della tabella per visualizzare la struttura chimica.")





