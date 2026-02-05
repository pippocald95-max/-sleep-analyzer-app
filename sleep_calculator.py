from datetime import datetime, timedelta
import pandas as pd

class SleepCalculator:
    """Calcola metriche del sonno con validazione outlier."""

    def __init__(self):
        pass

    def time_diff_minutes(self, time1, time2):
        """Calcola differenza gestendo mezzanotte."""
        if time1 is None or time2 is None:
            return 0

        base_date = datetime(2026, 1, 1)
        dt1 = datetime.combine(base_date, time1)
        dt2 = datetime.combine(base_date, time2)

        # Se time2 <= time1, assume che sia il giorno successivo
        if dt2 <= dt1:
            dt2 += timedelta(days=1)

        diff_minutes = (dt2 - dt1).total_seconds() / 60
        return max(0, diff_minutes)

    def calculate_total_time_in_bed(self, row):
        """TIB = N - H (ora_alzato - ora_letto)"""
        if row.get('ora_letto_clean') is None or row.get('ora_alzato_clean') is None:
            return None

        tib_minutes = self.time_diff_minutes(row['ora_letto_clean'], row['ora_alzato_clean'])
        tib_hours = tib_minutes / 60

        # VALIDAZIONE: TIB tra 2 e 20 ore è realistico
        if tib_hours < 2 or tib_hours > 20:
            return None  # Outlier

        return tib_hours

    def calculate_sleep_duration(self, row):
        """TST = M - I - J - L (ora_sveglia_finale - ora_spento_luci - latenza - veglia)"""
        if row.get('ora_spento_luci_clean') is None or row.get('ora_sveglia_finale_clean') is None:
            return None

        # Tempo base: da spento luci a sveglia finale
        tempo_base_minutes = self.time_diff_minutes(
            row['ora_spento_luci_clean'], 
            row['ora_sveglia_finale_clean']
        )

        # Sottrai latenza e veglia
        latenza = row.get('latenza_minuti', 0) or 0
        waso = row.get('veglia_infrasonno_minuti', 0) or 0

        tst_minutes = tempo_base_minutes - latenza - waso
        tst_hours = tst_minutes / 60

        # VALIDAZIONE: TST tra 1 e 16 ore è realistico
        if tst_hours < 1 or tst_hours > 16:
            return None  # Outlier

        return max(0, tst_hours)

    def calculate_all_metrics(self, row):
        """Calcola tutte le metriche con validazione."""
        metrics = {}

        # TIB
        metrics['tempo_totale_a_letto_ore'] = self.calculate_total_time_in_bed(row)

        # TST
        metrics['durata_sonno_ore'] = self.calculate_sleep_duration(row)

        # Tempo sveglio
        tib = metrics['tempo_totale_a_letto_ore']
        tst = metrics['durata_sonno_ore']

        if tib is not None and tst is not None:
            metrics['tempo_sveglio_letto_ore'] = max(0, tib - tst)

            # Efficienza
            if tib > 0:
                metrics['efficienza_sonno'] = min(100, (tst / tib) * 100)
            else:
                metrics['efficienza_sonno'] = None
        else:
            metrics['tempo_sveglio_letto_ore'] = None
            metrics['efficienza_sonno'] = None

        return metrics

    def process_dataframe(self, df):
        """Processa tutto il dataframe."""
        df = df.copy()

        # Ordina per data
        if 'data_compilazione' in df.columns:
            df = df.sort_values('data_compilazione', ascending=True).reset_index(drop=True)

        # Calcola metriche
        metrics_list = []
        for idx, row in df.iterrows():
            metrics = self.calculate_all_metrics(row)
            metrics_list.append(metrics)

        metrics_df = pd.DataFrame(metrics_list)
        for col in metrics_df.columns:
            df[col] = metrics_df[col]

        # MEDIE ROLLING CON min_periods=1 (usa solo dati disponibili!)
        if 'data_compilazione' in df.columns:
            df['media_rolling_7gg_durata'] = df['durata_sonno_ore'].rolling(
                window=7, min_periods=1
            ).mean()
            df['media_rolling_7gg_efficienza'] = df['efficienza_sonno'].rolling(
                window=7, min_periods=1
            ).mean()
            df['media_rolling_7gg_tib'] = df['tempo_totale_a_letto_ore'].rolling(
                window=7, min_periods=1
            ).mean()

        return df
