import streamlit as st
import pandas as pd
from data_cleaner import SleepDataCleaner
from sleep_calculator import SleepCalculator
import io

st.set_page_config(page_title="Analizzatore Sonno", page_icon="😴", layout="wide")

def format_hours_to_hhmm(hours):
    """Formatta ore decimali in formato hh h mm min."""
    if pd.isna(hours) or hours == 0:
        return "0h 0min"
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h}h {m}min"

def format_delta_hours(delta_hours):
    """Formatta delta ore con segno."""
    if pd.isna(delta_hours):
        return ""
    sign = "+" if delta_hours >= 0 else ""
    abs_delta = abs(delta_hours)
    h = int(abs_delta)
    m = int((abs_delta - h) * 60)
    if h == 0:
        return f"{sign}{m}min"
    if m == 0:
        return f"{sign}{h}h"
    return f"{sign}{h}h {m}min"

def format_minutes(mins):
    """Formatta minuti."""
    if pd.isna(mins) or mins == 0:
        return "0 min"
    return f"{mins:.0f} min"

# ==================== UI ====================

st.title("😴 Analizzatore Dati del Sonno")
st.markdown("**Carica file Excel, seleziona il cliente e ottieni risultati validati**")

uploaded_file = st.file_uploader(
    "📁 Carica file Excel del diario del sonno",
    type=['xlsx', 'xls']
)

if uploaded_file:
    try:
        # Carica dati
        df = pd.read_excel(uploaded_file)
        st.success(f"✅ File caricato! {len(df)} righe trovate.")

        # Pulisci dati
        cleaner = SleepDataCleaner()
        df = cleaner.clean_data(df)

        # Filtra righe con nome valido
        df_clean = df[df['nome_cliente_normalizzato'].notna()].copy()

        if 'data_compilazione' in df_clean.columns:
            df_clean = df_clean.sort_values('data_compilazione', ascending=True).reset_index(drop=True)

        clienti = sorted(df_clean['nome_cliente_normalizzato'].dropna().unique())

        st.markdown("---")

        # Selezione cliente
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            selected_client = st.selectbox(
                "👤 Seleziona il cliente da analizzare:",
                options=["Tutti i clienti"] + list(clienti),
                index=0
            )

        with col2:
            st.metric("Clienti totali", len(clienti))

        with col3:
            st.metric("Notti totali", len(df_clean))

        # Filtra per cliente
        if selected_client != "Tutti i clienti":
            df_filtered = df_clean[df_clean['nome_cliente_normalizzato'] == selected_client].copy()
            st.info(f"📊 Analizzando {len(df_filtered)} notti per **{selected_client}**")
        else:
            df_filtered = df_clean.copy()
            st.info(f"📊 Analizzando {len(df_filtered)} notti per tutti i clienti")

        if st.button("🚀 Analizza Dati", type="primary"):
            with st.spinner("Calcolo in corso..."):
                # Calcola metriche
                calculator = SleepCalculator()
                df_results = calculator.process_dataframe(df_filtered)

                st.success("✅ Analisi completata!")

                # ==================== STATISTICHE ====================

                st.markdown("---")
                st.subheader("📊 Statistiche Globali (Tutto il Periodo)")

                # Filtra righe con dati validi per statistiche
                df_valid = df_results[
                    df_results['tempo_totale_a_letto_ore'].notna() &
                    df_results['durata_sonno_ore'].notna()
                ].copy()

                if len(df_valid) == 0:
                    st.warning("⚠️ Nessun dato valido trovato!")
                else:
                    # Medie globali SOLO su dati validi
                    avg_tib = df_valid['tempo_totale_a_letto_ore'].mean()
                    avg_tst = df_valid['durata_sonno_ore'].mean()
                    avg_eff = df_valid['efficienza_sonno'].mean()
                    avg_latency = df_valid['latenza_minuti'].mean()
                    avg_waso = df_valid['veglia_infrasonno_minuti'].mean()

                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        st.metric("TIB Medio", format_hours_to_hhmm(avg_tib))

                    with col2:
                        st.metric("TST Medio", format_hours_to_hhmm(avg_tst))

                    with col3:
                        st.metric("Efficienza Media", f"{avg_eff:.1f}%")

                    with col4:
                        st.metric("Latenza Media", format_minutes(avg_latency))

                    with col5:
                        st.metric("WASO Medio", format_minutes(avg_waso))

                    # ==================== ULTIMI 7 GIORNI ====================

                    st.markdown("---")
                    st.subheader("📈 Statistiche Ultimi 7 Giorni")

                    # Ultimi 7 dati validi (anche se < 7)
                    df_last_7 = df_valid.tail(7)

                    if len(df_last_7) < 7:
                        st.caption(f"⚠️ Medie calcolate sulle ultime {len(df_last_7)} notti valide (meno di 7 disponibili)")
                    else:
                        st.caption("Medie calcolate sulle ultime 7 notti valide")

                    avg_tib_7 = df_last_7['tempo_totale_a_letto_ore'].mean()
                    avg_tst_7 = df_last_7['durata_sonno_ore'].mean()
                    avg_eff_7 = df_last_7['efficienza_sonno'].mean()
                    avg_latency_7 = df_last_7['latenza_minuti'].mean()
                    avg_waso_7 = df_last_7['veglia_infrasonno_minuti'].mean()

                    col1, col2, col3, col4, col5 = st.columns(5)

                    with col1:
                        delta = avg_tib_7 - avg_tib
                        st.metric("TIB Medio", format_hours_to_hhmm(avg_tib_7), 
                                 delta=f"{format_delta_hours(delta)} vs globale")

                    with col2:
                        delta = avg_tst_7 - avg_tst
                        st.metric("TST Medio", format_hours_to_hhmm(avg_tst_7),
                                 delta=f"{format_delta_hours(delta)} vs globale")

                    with col3:
                        delta = avg_eff_7 - avg_eff
                        st.metric("Efficienza Media", f"{avg_eff_7:.1f}%",
                                 delta=f"{delta:+.1f}% vs globale")

                    with col4:
                        delta = avg_latency_7 - avg_latency
                        st.metric("Latenza Media", format_minutes(avg_latency_7),
                                 delta=f"{delta:+.0f} min vs globale")

                    with col5:
                        delta = avg_waso_7 - avg_waso
                        st.metric("WASO Medio", format_minutes(avg_waso_7),
                                 delta=f"{delta:+.0f} min vs globale")

                    # ==================== TABELLA DATI ====================

                    st.markdown("---")
                    st.subheader("📋 Dati Elaborati")

                    display_cols = [
                        'nome_cliente_normalizzato',
                        'data_compilazione',
                        'tempo_totale_a_letto_ore',
                        'durata_sonno_ore',
                        'efficienza_sonno',
                        'tempo_sveglio_letto_ore',
                        'latenza_minuti',
                        'veglia_infrasonno_minuti',
                        'media_rolling_7gg_tib',
                        'media_rolling_7gg_durata',
                        'media_rolling_7gg_efficienza'
                    ]

                    display_cols_available = [c for c in display_cols if c in df_results.columns]
                    df_display = df_results[display_cols_available].copy()

                    # Formatta data
                    if 'data_compilazione' in df_display.columns:
                        df_display['Data'] = pd.to_datetime(df_display['data_compilazione']).dt.strftime('%Y-%m-%d')
                        df_display = df_display.drop('data_compilazione', axis=1)

                    # Rinomina colonne per visualizzazione
                    rename_map = {
                        'nome_cliente_normalizzato': 'Cliente',
                        'tempo_totale_a_letto_ore': 'TIB (ore)',
                        'durata_sonno_ore': 'TST (ore)',
                        'efficienza_sonno': 'Efficienza (%)',
                        'tempo_sveglio_letto_ore': 'Tempo Sveglio (ore)',
                        'latenza_minuti': 'Latenza (min)',
                        'veglia_infrasonno_minuti': 'WASO (min)',
                        'media_rolling_7gg_tib': 'TIB Media 7gg',
                        'media_rolling_7gg_durata': 'TST Media 7gg',
                        'media_rolling_7gg_efficienza': 'Eff Media 7gg'
                    }
                    df_display = df_display.rename(columns=rename_map)

                    # Arrotonda valori numerici
                    for col in df_display.columns:
                        if df_display[col].dtype in ['float64', 'float32']:
                            df_display[col] = df_display[col].round(2)

                    st.dataframe(df_display, use_container_width=True, hide_index=True)

                    if len(df_results) > 50:
                        st.caption(f"💡 Mostrate prime righe. Scarica l'Excel per vedere tutto.")

                    # ==================== DOWNLOAD ====================

                    st.markdown("---")
                    st.subheader("💾 Download Risultati")

                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_results.to_excel(writer, index=False, sheet_name='Risultati')
                    output.seek(0)

                    filename = f"risultati_{selected_client.replace(' ', '_')}.xlsx" if selected_client != "Tutti i clienti" else "risultati_tutti_clienti.xlsx"

                    st.download_button(
                        label="📥 Scarica Excel con tutti i risultati",
                        data=output,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

    except Exception as e:
        st.error(f"❌ Errore durante l'elaborazione: {str(e)}")
        st.exception(e)

else:
    st.info("👆 Carica un file Excel per iniziare l'analisi")

# ==================== TEST INFO ====================

with st.expander("ℹ️ Info sui Calcoli"):
    st.markdown("""
    ### Formule
    - **TIB** (Tempo Totale a Letto) = N - H = Ora Alzato - Ora Letto
    - **TST** (Durata Sonno Effettiva) = M - I - J - L = Ora Sveglia Finale - Ora Spento Luci - Latenza - WASO
    - **Tempo Sveglio** = TIB - TST
    - **Efficienza Sonno** = (TST / TIB) × 100

    ### Validazione Outlier
    - Latenza > 120 min → rimosso
    - TIB < 2h o > 20h → rimosso
    - TST < 1h o > 16h → rimosso
    - Testi non numerici → gestiti automaticamente

    ### Formati Supportati
    - Orari: `23:00`, `23,00`, `23;00`, `23.00`, `24:30` (→ 00:30)
    - Durate: `15`, `15 min`, `10/15` (→ media), `01:30` (→ 90 min)
    - Testi: `"Non ho dormito"`, `"Non ricordo"` → gestiti come valori nulli
    """)
