import re
import pandas as pd
import numpy as np
from datetime import datetime, time

class SleepDataCleaner:
    """Pulisce i dati del sonno gestendo TUTTI i formati sporchi per tutti i clienti."""

    def __init__(self):
        pass

    def parse_time_string(self, time_str):
        """Converte QUALSIASI formato di orario in datetime.time."""
        if pd.isna(time_str) or time_str == '' or time_str is None:
            return None

        time_str = str(time_str).strip()

        # Rimuovi testo descrittivo
        text_indicators = ['non', 'dormito', 'divano', 'ricordo', 'addormentato', 'penso']
        if any(word in time_str.lower() for word in text_indicators):
            return None

        # Rimuovi parte dopo slash se presente (es. "10:40/11:00" → "10:40")
        if '/' in time_str:
            time_str = time_str.split('/')[0].strip()

        # Gestisci typo comuni: "223;15" → "23:15"
        if time_str.startswith('2') and len(time_str) > 5:
            time_str = time_str[1:]  # Rimuovi primo 2 se sembra un typo

        # Sostituisci separatori NON standard
        time_str = time_str.replace('.', ':')    # Punto → due punti
        time_str = time_str.replace(',', ':')    # Virgola → due punti  
        time_str = time_str.replace(';', ':')    # Punto e virgola → due punti
        time_str = time_str.replace("'", ':')    # Apostrofo → due punti
        time_str = time_str.replace(' ', '')     # Rimuovi spazi

        # Gestisci "24:XX" e "24.XX" (ore oltre 24)
        parts = time_str.split(':')
        if len(parts) >= 2:
            try:
                hours = int(parts[0])
                minutes = int(parts[1])

                # Se ore >= 24, converti in formato 00-23
                if hours >= 24:
                    hours = hours - 24

                # Validazione
                if 0 <= hours <= 23 and 0 <= minutes <= 59:
                    return time(hours, minutes)
            except:
                pass

        # Prova numero intero (es. "22" → 22:00)
        try:
            num = float(time_str)
            hours = int(num)

            if hours >= 24:
                hours = hours - 24

            if 0 <= hours <= 23:
                return time(hours, 0)
        except:
            pass

        return None

    def parse_duration_minutes(self, duration_str):
        """Converte QUALSIASI formato di durata in minuti."""
        if pd.isna(duration_str) or duration_str == '' or duration_str is None:
            return 0

        duration_str = str(duration_str).strip().lower()

        # Casi speciali testuali = 0
        text_zero = ['0', '00', 'secondi', 'non saprei', 'no', 'non ricordo', 'nessuna']
        if duration_str in text_zero:
            return 0

        # Testi descrittivi che indicano valori non affidabili = None
        unreliable_texts = ['non ho dormito', 'quasi tutta', 'tutta notte', 'penso di non', 'non penso']
        if any(text in duration_str for text in unreliable_texts):
            return None  # Segna come dato non affidabile

        # Rimuovi testo comune
        duration_str = duration_str.replace('min', '').replace('minuti', '').replace('mi', '').strip()

        # Range con slash (es. "10/15" → media)
        if '/' in duration_str:
            parts = duration_str.split('/')
            try:
                nums = [float(re.findall(r'\d+', p)[0]) for p in parts if re.findall(r'\d+', p)]
                if nums:
                    return sum(nums) / len(nums)
            except:
                pass

        # Formato HH:MM (potenziale outlier!)
        if ':' in duration_str:
            parts = duration_str.split(':')
            try:
                hours = int(parts[0])
                minutes = int(parts[1])
                total_minutes = hours * 60 + minutes

                # OUTLIER DETECTION: latenza > 2 ore è irrealistico
                if total_minutes > 120:
                    return None  # Marca come outlier

                return total_minutes
            except:
                pass

        # Estrai primo numero
        numbers = re.findall(r'\d+', duration_str)
        if numbers:
            value = float(numbers[0])

            # OUTLIER DETECTION: latenza > 120 min è irrealistico
            if value > 120:
                return None

            return value

        return 0

    def clean_data(self, df):
        """Pulisce tutti i dati del dataframe."""
        df = df.copy()

        # Mappatura colonne basata sul file Excel reale
        col_map = {
            'nome_cliente': 6,  # Colonna "Inserisci il tuo Nome e Cognome"
            'ora_letto': 7,     # Colonna H
            'ora_spento_luci': 8,  # Colonna I
            'latenza': 9,       # Colonna J
            'num_risvegli': 10,
            'veglia_notte': 11,  # Colonna L
            'ora_sveglia_finale': 12,  # Colonna M
            'ora_alzato': 13,   # Colonna N
            'data_compilazione': 1  # Start time
        }

        # 1. Nome cliente normalizzato
        df['nome_cliente_normalizzato'] = df.iloc[:, col_map['nome_cliente']].apply(
            lambda x: str(x).strip().title() if pd.notna(x) else None
        )

        # 2. Data compilazione
        df['data_compilazione'] = pd.to_datetime(df.iloc[:, col_map['data_compilazione']], errors='coerce')

        # 3. Orari puliti
        df['ora_letto_clean'] = df.iloc[:, col_map['ora_letto']].apply(self.parse_time_string)
        df['ora_spento_luci_clean'] = df.iloc[:, col_map['ora_spento_luci']].apply(self.parse_time_string)
        df['ora_sveglia_finale_clean'] = df.iloc[:, col_map['ora_sveglia_finale']].apply(self.parse_time_string)
        df['ora_alzato_clean'] = df.iloc[:, col_map['ora_alzato']].apply(self.parse_time_string)

        # 4. Latenza in minuti (con gestione outlier)
        df['latenza_minuti'] = df.iloc[:, col_map['latenza']].apply(self.parse_duration_minutes)

        # 5. Veglia infrasonno in minuti (con gestione outlier)
        df['veglia_infrasonno_minuti'] = df.iloc[:, col_map['veglia_notte']].apply(self.parse_duration_minutes)

        # 6. Sostituisci None con 0 per latenza e veglia (dopo outlier detection)
        df['latenza_minuti'] = df['latenza_minuti'].fillna(0)
        df['veglia_infrasonno_minuti'] = df['veglia_infrasonno_minuti'].fillna(0)

        return df
