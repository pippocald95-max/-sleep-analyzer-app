import pandas as pd
from datetime import datetime, timedelta

class SleepCalculator:
    """Calcola metriche del sonno da dati puliti del diario."""

    def __init__(self, max_inertia_minutes=30):
        self.max_inertia_minutes = max_inertia_minutes

    def time_diff_minutes(self, time1, time2):
        """Differenza in minuti tra due datetime.time; se time2 <= time1 assume giorno successivo.

        Usare questa funzione per intervalli che possono attraversare mezzanotte (es. 23:30 -> 05:15).
        """
        if time1 is None or time2 is None:
            return 0

        base_date = datetime(2026, 1, 1)
        dt1 = datetime.combine(base_date, time1)
        dt2 = datetime.combine(base_date, time2)

        # FIX mezzanotte
        if dt2 <= dt1:
            dt2 += timedelta(days=1)

        diff_minutes = (dt2 - dt1).total_seconds() / 60
        return max(0, diff_minutes)

    def time_diff_same_day_minutes(self, time1, time2):
        """Differenza in minuti tra due datetime.time sullo STESSO giorno.

        Usare questa funzione quando la sottrazione deve essere "semplice" (es. sveglia -> alzata al mattino).
        Se time2 < time1, ritorna 0 (non forza il passaggio al giorno successivo).
        """
        if time1 is None or time2 is None:
            return 0

        base_date = datetime(2026, 1, 1)
        dt1 = datetime.combine(base_date, time1)
        dt2 = datetime.combine(base_date, time2)

        diff_minutes = (dt2 - dt1).total_seconds() / 60
        return max(0, diff_minutes)

    def calculate_time_in_bed(self, row):
        if row.get('ora_spento_luci_clean') is None or row.get('ora_alzato_clean') is None:
            return 0
        tib_minutes = self.time_diff_minutes(row['ora_spento_luci_clean'], row['ora_alzato_clean'])
        return tib_minutes / 60

    def calculate_morning_inertia_minutes(self, row):
        """Inerzia mattutina (minuti): ora_alzato - ora_sveglia_finale.

        Richiesta: sottrazione semplice tra colonna N (alzato) e M (sveglia finale), senza gestire mezzanotte.
        """
        if row.get('ora_sveglia_finale_clean') is None or row.get('ora_alzato_clean') is None:
            return 0
        return self.time_diff_same_day_minutes(row['ora_sveglia_finale_clean'], row['ora_alzato_clean'])

    def calculate_sleep_duration(self, row):
        if row.get('ora_spento_luci_clean') is None or row.get('ora_alzato_clean') is None:
            return 0

        tib_minutes = self.time_diff_minutes(row['ora_spento_luci_clean'], row['ora_alzato_clean'])
        if tib_minutes <= 0:
            return 0

        latency = row.get('latenza_minuti', 0) or 0
        waso = row.get('veglia_infrasonno_minuti', 0) or 0

        inertia_raw = self.calculate_morning_inertia_minutes(row)
        inertia_used = min(inertia_raw, self.max_inertia_minutes)

        tst_minutes = tib_minutes - latency - waso - inertia_used
        tst_minutes = max(0, min(tst_minutes, tib_minutes))
        tst_minutes = min(tst_minutes, 960)

        return tst_minutes / 60

    def calculate_sleep_efficiency(self, row):
        if row.get('tempo_a_letto_ore', 0) == 0:
            return 0
        efficiency = (row.get('durata_sonno_ore', 0) / row['tempo_a_letto_ore']) * 100
        return min(efficiency, 100)

    def calculate_all_metrics(self, df):
        df = df.copy()

        if 'data_compilazione' in df.columns:
            if not df['data_compilazione'].is_monotonic_increasing:
                df = df.sort_values('data_compilazione', ascending=True).reset_index(drop=True)

        df['tempo_a_letto_ore'] = df.apply(self.calculate_time_in_bed, axis=1)

        # Inerzia mattutina: valore grezzo e valore usato nel TST
        df['inerzia_mattutina_min'] = df.apply(self.calculate_morning_inertia_minutes, axis=1)
        df['inerzia_mattutina_usata_min'] = df['inerzia_mattutina_min'].clip(upper=self.max_inertia_minutes)

        df['durata_sonno_ore'] = df.apply(self.calculate_sleep_duration, axis=1)
        df['efficienza_sonno'] = df.apply(self.calculate_sleep_efficiency, axis=1)

        if 'data_compilazione' in df.columns:
            df['media_rolling_7gg_durata'] = df['durata_sonno_ore'].rolling(window=7, min_periods=1).mean()
            df['media_rolling_7gg_efficienza'] = df['efficienza_sonno'].rolling(window=7, min_periods=1).mean()
            df['media_rolling_7gg_inerzia'] = df['inerzia_mattutina_min'].rolling(window=7, min_periods=1).mean()
        else:
            df['media_rolling_7gg_durata'] = df['durata_sonno_ore']
            df['media_rolling_7gg_efficienza'] = df['efficienza_sonno']
            df['media_rolling_7gg_inerzia'] = df['inerzia_mattutina_min']

        return df
