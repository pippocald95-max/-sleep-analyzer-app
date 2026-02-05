import pandas as pd
import numpy as np
from datetime import datetime, time
import re

class SleepDataCleaner:
    """Pulisce i dati del diario del sonno gestendo formati inconsistenti e input 'umani'."""

    def __init__(self, max_latency_minutes=240, max_waso_minutes=720):
        self.max_latency_minutes = max_latency_minutes
        self.max_waso_minutes = max_waso_minutes

        self.column_mapping = {
            'A che ora sei andato a letto? (utilizza il formato hh:mm)': 'ora_letto',
            'A che ora hai spento le luci per andare a dormire? (utilizza il formato hh:mm)': 'ora_spento_luci',
            'Quanto tempo hai impiegato per addormentarti? (indica il tempo in minuti, utilizza solo cifre numeriche)': 'latenza_minuti',
            'Quante volte ti sei svegliato la scorsa notte?': 'num_risvegli',
            "Quanto tempo sei stato sveglio durante la notte? (utilizza il formato hh:mm, ad esempio, se sei stato sveglio un'ora e mezza scrivi 01:30)": 'veglia_infrasonno',
            "A che ora ti sei svegliato per l'ultima volta stamattina? (utilizza il formato hh:mm)": 'ora_sveglia_finale',
            'A che ora ti sei alzato dal letto? (utilizza il formato hh:mm)': 'ora_alzato',
            "All'incirca, quante ore hai dormito la scorsa notte? (utilizza il formato hh:mm)": 'ore_dormite_stimate',
            'Start time': 'data_compilazione',
            'Completion time': 'data_completamento'
        }

        self.name_mappings = {
            'maria': 'Maria Iob',
            'maria iob': 'Maria Iob',
            'sarah c': 'Sarah Cetola',
            'sarah c.': 'Sarah Cetola',
            'sarah cetola': 'Sarah Cetola',
            'raia claudia': 'Claudia Raia',
            'claudia raia': 'Claudia Raia'
        }

    # -----------------------
    # Nomi
    # -----------------------
    def normalize_client_name(self, name):
        if pd.isna(name) or str(name).strip() == '':
            return None
        name = str(name).strip()
        name_lower = re.sub(r'\s+', ' ', name.lower()).replace('.', '').replace(',', '')
        if name_lower in self.name_mappings:
            return self.name_mappings[name_lower]
        return ' '.join(w.capitalize() for w in name_lower.split())

    def smart_merge_similar_names(self, df, nome_col):
        if nome_col not in df.columns:
            return df

        df = df.copy()
        df['nome_temp'] = df[nome_col].apply(self.normalize_client_name)
        unique_names = df['nome_temp'].dropna().unique()
        merge_map = {}

        for name in unique_names:
            if name in merge_map:
                continue

            name_parts = name.lower().split()
            for other in unique_names:
                if name == other:
                    continue

                other_parts = other.lower().split()

                if len(name_parts) == 2 and len(other_parts) == 2:
                    if set(name_parts) == set(other_parts) and name_parts != other_parts:
                        merge_map[max(name, other)] = min(name, other)
                        continue

                if len(name_parts) < len(other_parts):
                    if all(p in other_parts for p in name_parts):
                        merge_map[name] = other
                        break

                if len(name_parts) == 2 and len(other_parts) == 2:
                    if (name_parts[0] == other_parts[0] and
                        len(name_parts[1]) == 1 and
                        other_parts[1].startswith(name_parts[1])):
                        merge_map[name] = other
                        break

        df['nome_cliente_normalizzato'] = df['nome_temp'].replace(merge_map)
        df.drop('nome_temp', axis=1, inplace=True)
        return df

    # -----------------------
    # Clean main
    # -----------------------
    def clean_data(self, df):
        df = df.copy()

        nome_col = None
        for col in df.columns:
            cl = str(col).lower()
            if 'nome' in cl and 'cognome' in cl:
                nome_col = col
                break

        if nome_col:
            df['nome_cliente_originale'] = df[nome_col]
            df = self.smart_merge_similar_names(df, nome_col)

        rename_dict = {}
        for old_col in df.columns:
            for key, val in self.column_mapping.items():
                if key in str(old_col):
                    rename_dict[old_col] = val
                    break
        df.rename(columns=rename_dict, inplace=True)

        if 'ora_spento_luci' in df.columns:
            df['ora_spento_luci_clean'] = df['ora_spento_luci'].apply(self.parse_time)

        if 'ora_alzato' in df.columns:
            df['ora_alzato_clean'] = df['ora_alzato'].apply(self.parse_time)

        if 'ora_sveglia_finale' in df.columns:
            df['ora_sveglia_finale_clean'] = df['ora_sveglia_finale'].apply(self.parse_time)

        if 'latenza_minuti' in df.columns:
            df['latenza_minuti'] = df['latenza_minuti'].apply(self.parse_latency_minutes)

        if 'veglia_infrasonno' in df.columns:
            df['veglia_infrasonno_minuti'] = df['veglia_infrasonno'].apply(self.parse_waso_minutes)

        if 'num_risvegli' in df.columns:
            df['num_risvegli'] = df['num_risvegli'].apply(self.parse_number)

        if 'data_compilazione' in df.columns:
            df['data_compilazione'] = pd.to_datetime(
                df['data_compilazione'], format='mixed', dayfirst=False, errors='coerce'
            )

        return df

    # -----------------------
    # Parsing time (ROBUSTO)
    # -----------------------
    def _normalize_sep(self, s: str) -> str:
        s = s.strip().lower()
        s = s.replace(' ', '')
        s = s.replace(';', ':').replace(',', ':').replace('.', ':')
        s = re.sub(r'[^0-9:]', '', s)
        if s.count(':') > 1:
            first = s.find(':')
            s = s[:first+1] + s[first+1:].replace(':', '')
        return s

    def _fix_hours(self, h_str: str):
        digits = re.sub(r'\D', '', str(h_str))
        if digits == '':
            return None
        h = int(digits)

        if h == 24:
            return 0
        if 0 <= h <= 23:
            return h

        # Caso tipo "223" -> 23
        if len(digits) >= 2:
            h2 = int(digits[-2:])
            if h2 == 24:
                return 0
            if 0 <= h2 <= 23:
                return h2

        return None

    def _fix_minutes(self, m_str: str):
        digits = re.sub(r'\D', '', str(m_str))
        if digits == '':
            return 0

        # 1 cifra -> prendila così com'è
        if len(digits) == 1:
            m = int(digits)
            return m if 0 <= m <= 59 else None

        # 2 cifre
        if len(digits) == 2:
            m = int(digits)
            return m if 0 <= m <= 59 else None

        # 3 cifre: prova a "saltare" la cifra centrale (125 -> 15)
        if len(digits) == 3:
            candidates = [
                int(digits[0] + digits[2]),  # 125 -> 15
                int(digits[-2:]),            # 125 -> 25
                int(digits[:2])              # 125 -> 12
            ]
        else:
            # 4+ cifre: fallback su ultime 2, poi prime 2
            candidates = [
                int(digits[-2:]),
                int(digits[:2])
            ]

        for m in candidates:
            if 0 <= m <= 59:
                return m
        return None

    def parse_time(self, value):
        """Converte vari formati di orario in datetime.time, includendo '24:00' e input corrotti."""
        if pd.isna(value) or value == '' or value == 0:
            return None

        if isinstance(value, str) and not any(ch.isdigit() for ch in value):
            return None

        if isinstance(value, time):
            return value

        if isinstance(value, datetime):
            return value.time()

        # Excel time fraction
        if isinstance(value, (float, int, np.number, np.floating)):
            v = float(value)
            if 0 <= v < 1:
                total_seconds = int(round(v * 24 * 3600))
                hh = (total_seconds // 3600) % 24
                mm = (total_seconds % 3600) // 60
                return time(hh, mm)

            hh = int(v)
            dec = v - hh

            if hh == 24 and abs(dec) < 1e-9:
                return time(0, 0)

            mm = int(round(dec * 60))
            if hh == 24 and mm == 0:
                return time(0, 0)
            if 0 <= hh < 24 and 0 <= mm < 60:
                return time(hh, mm)
            return None

        s = self._normalize_sep(str(value))

        # "24" o "24:00" o "24:0"
        if re.fullmatch(r'24(:0{1,2})?', s):
            return time(0, 0)

        # hhmm senza separatore (es. 2315)
        if ':' not in s:
            digits = re.sub(r'\D', '', s)
            if len(digits) == 4:
                hh = self._fix_hours(digits[:2])
                mm = self._fix_minutes(digits[2:])
                if hh is not None and mm is not None:
                    return time(hh, mm)
            return None

        parts = s.split(':')
        if len(parts) != 2:
            return None

        hh = self._fix_hours(parts[0])
        mm = self._fix_minutes(parts[1])

        if hh is None or mm is None:
            return None

        return time(hh, mm)

    # -----------------------
    # Minutes / durations
    # -----------------------
    def _parse_minutes_general(self, value):
        if pd.isna(value) or str(value).strip() == '':
            return 0.0

        if isinstance(value, (int, float, np.number)):
            return float(value)

        s = str(value).strip().lower()
        if 'non' in s or 'no' in s or 'secondi' in s:
            return 0.0

        s = s.replace(' ', '').replace(';', ':').replace(',', ':').replace('.', ':')

        if ':' in s:
            parts = s.split(':')
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                a = int(parts[0])
                b = int(parts[1])

                # caso "30:00" inteso come 30 minuti
                if b == 0 and a <= 300:
                    return float(a)

                if 0 <= b < 60:
                    return float(a * 60 + b)

        if '/' in s:
            nums = re.findall(r'\d+', s)
            if len(nums) >= 2:
                return (float(nums[0]) + float(nums[1])) / 2

        nums = re.findall(r'\d+', s)
        return float(nums[0]) if nums else 0.0

    def parse_latency_minutes(self, value):
        minutes = self._parse_minutes_general(value)
        if minutes < 0:
            return 0.0
        if minutes > self.max_latency_minutes:
            return 0.0
        return float(minutes)

    def parse_duration_to_minutes(self, value):
        if pd.isna(value) or str(value).strip() == '':
            return 0.0

        if isinstance(value, (int, float, np.number)):
            v = float(value)
            # Excel time fraction (frazione di giorno)
            if 0 < v < 1:
                return v * 24 * 60
            return v

        if isinstance(value, time):
            return float(value.hour * 60 + value.minute)

        s = str(value).strip().lower()
        if 'non' in s or 'no' in s or 'secondi' in s:
            return 0.0

        s = s.replace(' ', '').replace(';', ':').replace(',', ':').replace('.', ':')

        if '/' in s:
            nums = re.findall(r'\d+', s)
            if len(nums) >= 2:
                return (float(nums[0]) + float(nums[1])) / 2

        m = re.match(r'^(\d{1,3}):(\d{1,3})$', s)
        if m:
            hh = int(m.group(1))
            mm = int(m.group(2))
            if 0 <= mm < 60 and hh >= 0:
                return float(hh * 60 + mm)

        nums = re.findall(r'\d+', s)
        return float(nums[0]) if nums else 0.0

    def parse_waso_minutes(self, value):
        minutes = self.parse_duration_to_minutes(value)
        if minutes < 0:
            return 0.0
        if minutes > self.max_waso_minutes:
            return float(self.max_waso_minutes)
        return float(minutes)

    def parse_number(self, value):
        if pd.isna(value) or str(value).strip() == '':
            return 0.0
        if isinstance(value, (int, float, np.number)):
            return float(value)

        s = str(value).strip().lower()
        if '/' in s:
            nums = re.findall(r'\d+', s)
            if len(nums) >= 2:
                return (float(nums[0]) + float(nums[1])) / 2

        nums = re.findall(r'\d+', s)
        return float(nums[0]) if nums else 0.0
