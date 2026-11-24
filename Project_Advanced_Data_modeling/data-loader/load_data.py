import time
import ast
from pathlib import Path
import pandas as pd
from pymongo import MongoClient
from influxdb_client import InfluxDBClient, Point, WriteOptions
from influxdb_client.client.write_api import SYNCHRONOUS

# CONFIGURAZIONI (Utilizziamo i nomi dei servizi Docker come host!)
MONGO_URI = "mongodb://mongodb:27017/"
INFLUX_URL = "http://influxdb:8086"
INFLUX_TOKEN = "il_mio_super_token_segreto_123"
INFLUX_ORG = "torino_org"
INFLUX_BUCKET = "torino_mobility"

DATA_DIR = Path(__file__).resolve().parent / "data"

def connetti_con_retry():
    """Attende che i servizi MongoDB e InfluxDB siano avviati e pronti."""
    print("In attesa che i database siano pronti...")
    mongo_client, influx_client = None, None
    
    while not mongo_client:
        try:
            mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
            mongo_client.server_info() # Forza la connessione
            print(" Connessione a MongoDB riuscita!")
        except Exception:
            print("MongoDB non è ancora pronto, riprovo tra 3 secondi...")
            time.sleep(3)
            
    while not influx_client:
        try:
            influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
            influx_client.health()
            print(" Connessione a InfluxDB riuscita!")
        except Exception:
            print("InfluxDB non è ancora pronto, riprovo tra 3 secondi...")
            time.sleep(3)
            
    return mongo_client, influx_client

def popola_mongodb(mongo_client):
    db = mongo_client["torino_mobility_db"]
    print("\n--- INIZIO POPOLAMENTO MONGODB ---")
    
    # 1. Caricamento STOPS (Fermate con formato GeoJSON)
    print("Caricamento fermate (Stops)...")
    stops_df = pd.read_csv(DATA_DIR / "stops.txt")
    db.stops.drop() # Pulisce se già esistente
    stops_docs = []
    for _, row in stops_df.iterrows():
        stops_docs.append({
            "stop_id": str(row["stop_id"]),
            "stop_name": row["stop_name"],
            "location": {
                "type": "Point",
                "coordinates": [float(row["stop_lon"]), float(row["stop_lat"])] # [Longitudine, Latitudine]
            }
        })
    db.stops.insert_many(stops_docs)
    db.stops.create_index([("location", "2dsphere")]) # Indice spaziale avanzato!
    print(f"Inserite {len(stops_docs)} fermate con indice GeoJSON.")

    # 2. Caricamento ROUTES (Linee)
    print("Caricamento linee (Routes)...")
    routes_df = pd.read_csv(DATA_DIR / "routes.txt")
    db.routes.drop()
    routes_docs = routes_df.to_dict(orient="records")
    db.routes.insert_many(routes_docs)

    # 3. Caricamento TRIPS (Viaggi) e integrazione STOP_TIMES (Embedding)
    print("Caricamento viaggi (Trips) e integrazione fermate (Stop Times)...")
    trips_df = pd.read_csv(DATA_DIR / "trips.txt")
    db.trips.drop()
    
    try:
        # Leggiamo il file stop_times
        stop_times_df = pd.read_csv(DATA_DIR / "stop_times.txt")
        
        print("Elaborazione e ordinamento delle sequenze delle fermate...")
        # Ordiniamo per garantire che la sequenza delle fermate sia corretta
        stop_times_df = stop_times_df.sort_values(by=["trip_id", "stop_sequence"])
        
        # Trasformiamo in un dizionario raggruppato per trip_id per essere super veloci
        stop_times_grouped = {}
        for _, row in stop_times_df.iterrows():
            t_id = row["trip_id"]
            fermata_info = {
                "stop_id": str(row["stop_id"]),
                "stop_sequence": int(row["stop_sequence"]),
                "arrival_time": str(row["arrival_time"]) if "arrival_time" in row else "",
                "departure_time": str(row["departure_time"]) if "departure_time" in row else ""
            }
            
            if t_id not in stop_times_grouped:
                stop_times_grouped[t_id] = []
            stop_times_grouped[t_id].append(fermata_info)
            
        print("Costruzione dei documenti embedded...")
        trips_docs = []
        for _, row in trips_df.iterrows():
            t_id = row["trip_id"]
            doc = row.to_dict() # Prende tutti i campi base (route_id, shape_id, ecc.)
            # Aggiunge l'array di fermate! Se non ne ha, mette una lista vuota
            doc["stop_sequence"] = stop_times_grouped.get(t_id, []) 
            trips_docs.append(doc)
            
    except FileNotFoundError:
        print("⚠️ ATTENZIONE: File stop_times.txt non trovato in data-loader/data/. Carico i trips base.")
        trips_docs = trips_df.to_dict(orient="records")

    # Inserimento massivo nel database
    if trips_docs:
        db.trips.insert_many(trips_docs)
    print(f"Inseriti {len(trips_docs)} viaggi in MongoDB (con fermate incorporate se presenti).")

    # 4. Caricamento SHAPES (Percorsi ottimizzati in GeoJSON LineString)
    print("Caricamento e ottimizzazione percorsi (Shapes)...")
    shapes_df = pd.read_csv(DATA_DIR / "shapes.txt")
    db.shapes.drop()
    
    # Raggruppiamo i punti per shape_id ordinandoli per sequenza per creare una LineString
    shapes_grouped = shapes_df.sort_values(by=["shape_id", "shape_pt_sequence"]).groupby("shape_id")
    shapes_docs = []
    for shape_id, group in shapes_grouped:
        coordinates = [[float(row["shape_pt_lon"]), float(row["shape_pt_lat"])] for _, row in group.iterrows()]
        if len(coordinates) > 1:
            shapes_docs.append({
                "shape_id": str(shape_id),
                "geo_path": {
                    "type": "LineString",
                    "coordinates": coordinates
                }
            })
    if shapes_docs:
        db.shapes.insert_many(shapes_docs)
    print(f"Inseriti {len(shapes_docs)} percorsi LineString in MongoDB.")

    # Servizio Bike sharing
    print("Caricamento stazioni Bike Sharing")
    bike_df = pd.read_csv(DATA_DIR / "stazioni_bike_sharing.csv", sep=";")
    db.bike_rent.drop()
    
    bike_docs = []
    for _, row in bike_df.iterrows():
        try:
            bike_docs.append({
                "station_id": int(row['station_id']),
                "station_name": str(row['station_name']),
                "location": {
                    "type": "Point",
                    "coordinates": [float(row['longitude']), float(row['latitude'])] # [Longitudine, Latitudine]
                }
            })
        except Exception as e:
            print(f"Errore nel saltare riga non valida: {e}")
            
    if bike_docs:
        db.bike_rent.insert_many(bike_docs)
        db.bike_rent.create_index([("location", "2dsphere")]) # Indice spaziale per le query geospaziali
    print(f"Inserite {len(bike_docs)} stazioni bike georeferenziate direttamente in WGS84.")

def popola_influxdb(influx_client):
    print("\n--- INIZIO POPOLAMENTO INFLUXDB ---")
    write_api = influx_client.write_api(write_options=SYNCHRONOUS)
    
    print("Lettura del file delle serie temporali corretto...")
    df = pd.read_csv(DATA_DIR / "influx_data.csv")
    
    print(f"Scrittura di {len(df)} punti in corso. Attendere...")
    punti = []
    
    for idx, row in df.iterrows():
        tags_dict = ast.literal_eval(row['tags'])
        fields_dict = ast.literal_eval(row['fields'])
        
        point = Point(row['measurement'])
        
        # Inserimento TAGS (Dimensioni indicizzate)
        for k, v in tags_dict.items():
            point.tag(k, str(v))
            
        # Inserimento FIELDS (Metriche e orari)
        for k, v in fields_dict.items():
            if isinstance(v, (int, float)):
                point.field(k, float(v))
            else:
                point.field(k, str(v))
                
        # Impostiamo il timestamp reale corretto
        point.time(row['time'])
        punti.append(point)
        
        # Scrittura a blocchi (batch) per non saturare la memoria
        if len(punti) >= 5000:
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=punti)
            punti = []
            
    # Scrive gli ultimi punti rimasti
    if punti:
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=punti)
        
    print("Scrittura in InfluxDB completata con successo!")

if __name__ == "__main__":
    start_time = time.time()
    
    # FASE 1: Attesa e connessione
    mongo_cli, influx_cli = connetti_con_retry()
    
    # FASE 2: Scrittura dati statici su MongoDB
    popola_mongodb(mongo_cli)
    
    # FASE 3: Scrittura serie temporali su InfluxDB
    popola_influxdb(influx_cli)
    
    print(f"\n Pipeline completata con successo in {round(time.time() - start_time, 2)} secondi!")
    print("Il container data-loader ha terminato il suo compito e si spegnerà.")