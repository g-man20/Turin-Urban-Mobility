import pandas as pd
import random
from datetime import datetime, timedelta

# Caricamento dei file necessari
mapping = pd.read_csv('geo_mapping_stops_sensors.csv')
stop_times = pd.read_csv('stop_times.txt')
trips = pd.read_csv('trips.txt')
calendar = pd.read_csv('calendar.txt')

def get_traffic_multiplier(hour):
    """Definisce quanto è pesante il traffico in base all'ora."""
    if 7 <= hour <= 9: return 2.5  # Picco mattino
    if 17 <= hour <= 19: return 2.0 # Picco sera
    if 22 <= hour or hour <= 5: return 0.3 # Notte
    return 1.0 # Normale

def generate_month_data(start_date_str, num_weeks=4):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    records = []

    for d in range(num_weeks * 7):
        current_day = start_date + timedelta(days=d)
        day_name = current_day.strftime('%A').lower() # es: 'monday'
        
        # 1. Filtra i service_id attivi per questo giorno della settimana
        active_services = calendar[calendar[day_name] == 1]['service_id'].tolist()
        
        # 2. Prendi i viaggi (trips) collegati a quei servizi
        daily_trips = trips[trips['service_id'].isin(active_services)]
        
        # Per brevità, simuliamo solo un campione di viaggi (es. 100 trips al giorno)
        sample_trips = daily_trips.sample(n=min(100, len(daily_trips)))

        for _, trip in sample_trips.iterrows():
            # Prendi le fermate di questo viaggio
            trip_stops = stop_times[stop_times['trip_id'] == trip['trip_id']]
            
            cumulative_delay = 0
            for _, stop in trip_stops.iterrows():
                # Controlla se la fermata ha un sensore associato
                match = mapping[mapping['stop_id'] == stop['stop_id']]
                
                # Calcola ritardo base
                base_delay = 0
                if not match.empty:
                    # Se c'è un sensore, simuliamo un ritardo basato sull'ora
                    hour = int(stop['arrival_time'].split(':')[0])
                    base_delay = random.randint(30, 180) * get_traffic_multiplier(hour)
                
                # Aggiungi variabilità random (il "rumore")
                random_noise = random.randint(-15, 45)
                current_stop_delay = base_delay + random_noise
                cumulative_delay += max(0, current_stop_delay) # Il ritardo si accumula

                # Creazione record per InfluxDB
                records.append({
                    "measurement": "bus_delays",
                    "tags": {
                        "stop_id": stop['stop_id'],
                        "route_id": trip['route_id'],
                        "day_type": "weekend" if day_name in ['saturday', 'sunday'] else "weekday"
                    },
                    "fields": {
                        "scheduled_time": stop['arrival_time'],
                        "delay_sec": float(cumulative_delay),
                        "actual_arrival": (datetime.combine(current_day, datetime.min.time()) + 
                                          timedelta(seconds=cumulative_delay)).timestamp()
                    },
                    "time": current_day.isoformat()
                })
    return pd.DataFrame(records)

# --- ESECUZIONE ---
df_final = generate_month_data("2026-05-18")
df_final.to_csv('influx_import_data.csv', index=False)
print(f"Generati {len(df_final)} record per InfluxDB!")