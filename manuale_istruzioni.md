# 📖 Manuale GC-MS Analyzer Pro

Benvenuto in **GC-MS Analyzer Pro**, lo strumento per elaborare, arricchire e visualizzare i tuoi dati di cromatografia.

## 🚀 Flusso di Lavoro (Workflow)

L'applicazione è divisa in tre fasi principali:

### 1️⃣ Fase 1: Normalizzazione Dati Grezzi

In questa fase devi caricare i file `.csv` grezzi esportati dal tuo strumento GC-MS.

- **Soglia Match Factor:** Tramite lo slider, puoi impostare un limite minimo (es. 60). Tutti i composti con un match factor inferiore a questa soglia verranno scartati, e la loro area ripartita in percentuale sugli altri composti validi (Colonna _New Area %_).
    
- **Output:** Puoi scaricare un file Excel formattato in cui i composti scartati sono evidenziati.
    
- **Uso Consigliato:** Scarica l'Excel, aprilo sul tuo PC e _correggi manualmente_ i nomi dei composti (Compound Name) che lo strumento ha interpretato male. Salva il file per la Fase 2!
    

### 2️⃣ Fase 2: Arricchimento (PubChem)

Qui l'app interroga il database mondiale **PubChem** per trovare formule e strutture chimiche (SMILES).

- **Flusso Standard:** Carica l'Excel che hai scaricato (e validato manualmente) nella Fase 1. Avvia Arricchimento PubChem.
    
- **Classificazione Famiglie:** puoi caricare le tue regole in base al campione analizzato o lasciare quelle di default. In fondo trovi la guida per la creazione di nuove regole.
    

### 3️⃣ Fase 3: Dashboard Interattiva

Visualizza i dati arricchiti.

- Clicca su una riga della tabella per generare in tempo reale la struttura chimica 2D della molecola.
    
- Esplora il grafico a torta per vedere la suddivisione delle famiglie chimiche.
    

## ⚙️ Creare Regole Famiglie Personalizzate

L'app legge automaticamente il file `gcms_classification_rules.csv` se presente. Questo file ti permette di assegnare una **Famiglia** a una specifica parola chiave presente nel nome della molecola.

**Come deve essere formattato il file CSV delle regole?**

Deve obbligatoriamente contenere queste colonne di intestazione:

`Keyword,Family,SubFamily,Source,Notes`

- **Keyword:** La parola chiave da cercare (es. _phthalate_, _decane_, _phenol_). L'app ignora le maiuscole/minuscole.
    
- **Family:** La Famiglia principale (es. _Plastica_, _Biomassa_, _Alcano_).
    
- **SubFamily:** (Opzionale) Sotto-famiglia.
    
- Le colonne _Source_ e _Notes_ sono ignorate dall'app, ma utili per te come promemoria.
    

**Esempio di Regole:**

```
Keyword,Family,SubFamily,Source,Notes
furan,Biomass_Starch,Furanic,,Deriva da Zuccheri
decane,Polymers_PE,Alkane,,Marker Polietilene
```
