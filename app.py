import streamlit as st
import pandas as pd
from data_cleaner import SleepDataCleaner
from sleep_calculator import SleepCalculator
import io

st.set_page_config(page_title="Sleep Data Analyzer", page_icon="😴", layout="wide")

def format_hours_to_hhmm(hours):
    if pd.isna(hours) or hours == 0:
        return "0h 0min"
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h}h {m}min"

def format_delta_hours(delta_hours):
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
    if pd.isna(mins) or mins == 0:
        return "0 min"
    return f"{mins:.0f} min"

st.title("😴 Analizzatore Dati del Sonno")
st.markdown("**Carica uno o più file Excel, seleziona il cliente e ottieni tutti i risultati automaticamente**")

uploaded_files = st.file_uploader(
    "📁 Carica uno o più file Excel del diario del sonno",
    type=['xlsx', 'xls'],
    accept_multiple_files=True
)

if uploaded_files:
    try:
        all_dfs = []
        total_rows = 0
        for uploaded_file in uploaded_files:
            df_temp = pd.read_excel(uploaded_file)
            total_rows += len(df_temp)
            all_dfs.append(df_temp)

        df = pd.concat(all_dfs, ignore_index=True)
        st.success(f"✅ {len(uploaded_files)} file caricati con successo! {total_rows} righe totali trovate.")

        cleaner = SleepDataCleaner()
        df = cleaner.clean_data(df)

        nome_col_normalizzato = 'nome_cliente_normalizzato'
        if nome_col_normalizzato not in df.columns:
            st.error("❌ Colonna del nome cliente non trovata!")
            st.write("Colonne disponibili:", list(df.columns))
            st.stop()

        df_clean = df[df[nome_col_normalizzato].notna()].copy()
        df_clean = df_clean[df_clean[nome_col_normalizzato].astype(str).str.strip() != ''].copy()

        if 'data_compilazione' in df_clean.columns:
            df_clean = df_clean.sort_values('data_compilazione', ascending=True).reset_index(drop=True)

        clienti = sorted(df_clean[nome_col_normalizzato].dropna().unique())
        st.markdown("---")

        with st.expander("📋 Dettagli file caricati"):
            for i, uploaded_file in enumerate(uploaded_files, 1):
                st.write(f"{i}. {uploaded_file.name} - {len(all_dfs[i-1])} righe")

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

        if selected_client != "Tutti i clienti":
            df_filtered = df_clean[df_clean[nome_col_normalizzato] == selected_client].copy()
            st.info(f"📊 Analizzando {len(df_filtered)} notti per **{selected_client}**")

            if 'data_compilazione' in df_filtered.columns and df_filtered['data_compilazione'].notna().any():
                date_min = df_filtered['data_compilazione'].min()
                date_max = df_filtered['data_compilazione'].max()
                st.caption(f"📅 Periodo: dal {date_min.strftime('%d/%m/%Y')} al {date_max.strftime('%d/%m/%Y')}")
        else:
            df_filtered = df_clean.copy()
            st.info(f"📊 Analizzando {len(df_filtered)} notti per tutti i clienti")

        client_counts = df_filtered[nome_col_normalizzato].value_counts()
        with st.expander("👥 Distribuzione notti per cliente"):
            for cliente, count in client_counts.items():
                st.write(f"- {cliente}: {count} notti")

        if st.button("🚀 Analizza Dati", type="primary"):
            with st.spinner("Pulizia e calcolo in corso..."):
                calculator = SleepCalculator()
                df_results = calculator.calculate_all_metrics(df_filtered)
                st.success("✅ Analisi completata!")

                st.markdown("---")
                st.subheader("📊 Statistiche Globali (Tutto il Periodo)")

                avg_duration_global = df_results['durata_sonno_ore'].mean()
                avg_efficiency_global = df_results['efficienza_sonno'].mean()
                avg_tib_global = df_results['tempo_a_letto_ore'].mean()
                avg_latency_global = df_results['latenza_minuti'].mean()
                avg_inerzia_global = df_results.get('inerzia_mattutina_min', pd.Series([0])).mean()

                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    st.metric("Durata Media Sonno", format_hours_to_hhmm(avg_duration_global))
                with col2:
                    st.metric("Efficienza Media", f"{avg_efficiency_global:.1f}%")
                with col3:
                    st.metric("Tempo a Letto Medio", format_hours_to_hhmm(avg_tib_global))
                with col4:
                    st.metric("Latenza Media", f"{avg_latency_global:.0f} min")
                with col5:
                    st.metric("Inerzia Mattutina", format_minutes(avg_inerzia_global))

                st.markdown("---")
                st.subheader("📈 Statistiche Ultimi 7 Giorni")

                if len(df_results) >= 7:
                    df_last_7 = df_results.tail(7)
                    caption_7gg = "Medie calcolate sulle ultime 7 notti"
                else:
                    df_last_7 = df_results
                    caption_7gg = f"Medie calcolate sulle ultime {len(df_results)} notti (meno di 7 disponibili)"
                st.caption(caption_7gg)

                avg_duration_7d = df_last_7['durata_sonno_ore'].mean()
                avg_efficiency_7d = df_last_7['efficienza_sonno'].mean()
                avg_tib_7d = df_last_7['tempo_a_letto_ore'].mean()
                avg_latency_7d = df_last_7['latenza_minuti'].mean()
                avg_inerzia_7d = df_last_7.get('inerzia_mattutina_min', pd.Series([0])).mean()

                col1, col2, col3, col4, col5 = st.columns(5)
                with col1:
                    delta_duration = avg_duration_7d - avg_duration_global
                    st.metric("Durata Media Sonno", format_hours_to_hhmm(avg_duration_7d), delta=f"{format_delta_hours(delta_duration)} vs globale")
                with col2:
                    delta_efficiency = avg_efficiency_7d - avg_efficiency_global
                    st.metric("Efficienza Media", f"{avg_efficiency_7d:.1f}%", delta=f"{delta_efficiency:+.1f}% vs globale")
                with col3:
                    delta_tib = avg_tib_7d - avg_tib_global
                    st.metric("Tempo a Letto Medio", format_hours_to_hhmm(avg_tib_7d), delta=f"{format_delta_hours(delta_tib)} vs globale")
                with col4:
                    delta_latency = avg_latency_7d - avg_latency_global
                    st.metric("Latenza Media", f"{avg_latency_7d:.0f} min", delta=f"{delta_latency:+.0f} min vs globale")
                with col5:
                    delta_inerzia = avg_inerzia_7d - avg_inerzia_global
                    st.metric("Inerzia Mattutina", format_minutes(avg_inerzia_7d), delta=f"{delta_inerzia:+.0f} min vs globale")

                st.markdown("")
                col1, col2 = st.columns(2)
                with col1:
                    avg_waso_global = df_results['veglia_infrasonno_minuti'].mean()
                    st.metric("WASO Globale", f"{avg_waso_global:.0f} min")
                with col2:
                    avg_waso_7d = df_last_7['veglia_infrasonno_minuti'].mean()
                    delta_waso = avg_waso_7d - avg_waso_global
                    st.metric("WASO Ultimi 7gg", f"{avg_waso_7d:.0f} min", delta=f"{delta_waso:+.0f} min vs globale")

                st.markdown("---")
                st.subheader("📋 Dati Elaborati")

                display_cols = [
                    nome_col_normalizzato,
                    'data_compilazione',
                    'durata_sonno_ore',
                    'efficienza_sonno',
                    'tempo_a_letto_ore',
                    'latenza_minuti',
                    'veglia_infrasonno_minuti',
                    'inerzia_mattutina_min',
                    'media_rolling_7gg_durata',
                    'media_rolling_7gg_efficienza',
                    'media_rolling_7gg_inerzia'
                ]

                display_cols_available = [c for c in display_cols if c in df_results.columns]
                df_display = df_results[display_cols_available].copy()

                if 'data_compilazione' in df_display.columns:
                    df_display['Data'] = pd.to_datetime(df_display['data_compilazione']).dt.strftime('%Y-%m-%d')
                    df_display['Ora'] = pd.to_datetime(df_display['data_compilazione']).dt.strftime('%H:%M')
                    df_display = df_display.drop('data_compilazione', axis=1)
                    cols = ['Data', 'Ora'] + [c for c in df_display.columns if c not in ['Data', 'Ora']]
                    df_display = df_display[cols]

                st.dataframe(df_display.head(50), use_container_width=True, hide_index=True)

                if len(df_results) > 50:
                    st.caption(f"Mostrate prime 50 righe su {len(df_results)} totali. Scarica l'Excel per vedere tutto.")

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
    st.info("👆 Carica uno o più file Excel per iniziare l'analisi")
