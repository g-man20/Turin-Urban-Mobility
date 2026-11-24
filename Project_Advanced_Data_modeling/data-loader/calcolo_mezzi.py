import math
from datetime import datetime, timedelta
from pymongo import MongoClient
from influxdb_client import InfluxDBClient

# Connessioni ai database
mongo_client = MongoClient("mongodb://mongodb:27017/") # Uso nome container
db = mongo_client["torino_mobility_db"]

influx_client = InfluxDBClient(url="http://influxdb:8086", token="il_mio_super_token_segreto_123", org="torino_org")
query_api = influx_client.query_api()

def calcola_distanza_haversine(lat1, lon1, lat2, lon2):
    R = 6371000 # Raggio della Terra in metri
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi/2)**2 + math.cos(phi1)*math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

def calcola_percorso_ottimale(orario_desiderato, lat_partenza, lon_partenza, lat_arrivo, lon_arrivo):
    print(f"\n🚀 AVVIO MOTORE DI ROUTING IBRIDO - Orario Partenza: {orario_desiderato}")
    velocita_piedi = 83.3 
    formato_ora = "%H:%M:%S"
    
    # --- PASSO 1: ORIGINE ---
    fermate_partenza_raw = list(db.stops.find({
        "location": {"$near": {"$geometry": {"type": "Point", "coordinates": [float(lon_partenza), float(lat_partenza)]}}}
    }).limit(7))
    
    fermate_partenza = []
    print(f"\n📍 PARTENZA - Trovate {len(fermate_partenza_raw)} fermate vicine:")
    for f in fermate_partenza_raw:
        dist = calcola_distanza_haversine(lat_partenza, lon_partenza, f["location"]["coordinates"][1], f["location"]["coordinates"][0])
        fermate_partenza.append({
            "id": f["stop_id"], 
            "name": f["stop_name"], 
            "tempo_piedi": dist / velocita_piedi,
            "lat": f["location"]["coordinates"][1],
            "lon": f["location"]["coordinates"][0]
        })
        print(f"  - {f['stop_name']} ({round(dist)} metri)")

    # --- PASSO 2: DESTINAZIONE ---
    fermate_arrivo_raw = list(db.stops.find({
        "location": {"$near": {"$geometry": {"type": "Point", "coordinates": [float(lon_arrivo), float(lat_arrivo)]}}}
    }).limit(7))
    
    fermate_arrivo = []
    print(f"\n🏁 ARRIVO - Trovate {len(fermate_arrivo_raw)} fermate vicine:")
    for f in fermate_arrivo_raw:
        dist = calcola_distanza_haversine(lat_arrivo, lon_arrivo, f["location"]["coordinates"][1], f["location"]["coordinates"][0])
        fermate_arrivo.append({
            "id": f["stop_id"], 
            "name": f["stop_name"], 
            "tempo_piedi": dist / velocita_piedi,
            "lat": f["location"]["coordinates"][1],
            "lon": f["location"]["coordinates"][0]
        })
        print(f"  - {f['stop_name']} ({round(dist)} metri)")

    # --- PASSO 3: INCROCIO ---
    opzioni_percorso = []
    corse_dirette_trovate = 0
    
    print("\n🔄 Ricerca corse dirette (senza cambi) in corso...")
    for f_dep in fermate_partenza:
        for f_arr in fermate_arrivo:
            
            # Cerchiamo sia l'ID come stringa, sia come intero (per sicurezza!)
            id_partenza_str = str(f_dep["id"])
            id_partenza_int = int(f_dep["id"]) if str(f_dep["id"]).isdigit() else f_dep["id"]
            
            id_arrivo_str = str(f_arr["id"])
            id_arrivo_int = int(f_arr["id"]) if str(f_arr["id"]).isdigit() else f_arr["id"]

            # Query $in e $elemMatch per aggirare il problema dei tipi di dato su MongoDB
            query_trips = {
                "$and": [
                    {"stop_sequence": {"$elemMatch": {"stop_id": {"$in": [id_partenza_str, id_partenza_int]}}}},
                    {"stop_sequence": {"$elemMatch": {"stop_id": {"$in": [id_arrivo_str, id_arrivo_int]}}}}
                ]
            }
            
            viaggi_validi = list(db.trips.find(query_trips))
            
            if viaggi_validi:
                corse_dirette_trovate += len(viaggi_validi)
            
            for viaggio in viaggi_validi:
                sequenza = viaggio["stop_sequence"]
                
                # Cerchiamo l'elemento esatto indipendentemente dal tipo
                dati_f_dep = next((s for s in sequenza if str(s["stop_id"]) == str(f_dep["id"])), None)
                dati_f_arr = next((s for s in sequenza if str(s["stop_id"]) == str(f_arr["id"])), None)
                
                if not dati_f_dep or not dati_f_arr:
                    continue # Salta se c'è un'incoerenza interna all'array
                
                # Controllo Direzione
                if dati_f_dep["stop_sequence"] < dati_f_arr["stop_sequence"]:
                    if not dati_f_dep or not dati_f_arr:
                        continue # Salta se c'è un'incoerenza interna all'array
                    
                    # Controllo Direzione
                    if dati_f_dep["stop_sequence"] < dati_f_arr["stop_sequence"]:
                        
                        # FILTRO NOTTURNO GTFS: Normalizziamo le ore oltre la mezzanotte (es. 25:00 -> 01:00)
                        h_dep, m_dep, s_dep = map(int, dati_f_dep["departure_time"].split(':'))
                        dati_f_dep["departure_time"] = f"{h_dep % 24:02d}:{m_dep:02d}:{s_dep:02d}"
                        
                        h_arr, m_arr, s_arr = map(int, dati_f_arr["arrival_time"].split(':'))
                        dati_f_arr["arrival_time"] = f"{h_arr % 24:02d}:{m_arr:02d}:{s_arr:02d}"
                    
                    
                    try:
                        ora_limite_utente = (datetime.strptime(orario_desiderato, formato_ora) + timedelta(minutes=f_dep["tempo_piedi"])).time()
                        ora_passaggio_bus = datetime.strptime(dati_f_dep["departure_time"], formato_ora).time()
                        
                        # Controllo Orario
                        if ora_passaggio_bus >= ora_limite_utente:
                            t_teorico_dep = datetime.strptime(dati_f_dep["departure_time"], formato_ora)
                            t_teorico_arr = datetime.strptime(dati_f_arr["arrival_time"], formato_ora)
                            tempo_mezzo_teorico = (t_teorico_arr - t_teorico_dep).total_seconds() / 60
                            
                            # InfluxDB
                            ritardo_minuti = 0.0
                            
                            try:
                                # 1. Capiamo che ore sono in base alla richiesta dell'utente
                                ora_target = datetime.strptime(dati_f_dep["departure_time"], formato_ora).hour
                                
                                # 2. Capiamo il GIORNO ESATTO della settimana
                                # In Python: 0=Lunedì, 1=Martedì ... 6=Domenica
                                # (Se all'esame vuoi forzare un giorno specifico, es. Lunedì, scrivi: giorno_corrente_python = 0)
                                giorno_corrente_python = datetime.today().weekday()
                                
                                # TRADUZIONE CALENDARIO: Convertiamo il giorno Python nel formato Flux
                                # In Flux: 0=Domenica, 1=Lunedì, 2=Martedì ... 6=Sabato
                                giorno_corrente_flux = (giorno_corrente_python + 1) % 7

                                flux_query = f'''
                                    import "date"
                                    from(bucket: "torino_mobility")
                                      |> range(start: 2026-05-15T00:00:00Z, stop: 2026-06-20T00:00:00Z)
                                      |> filter(fn: (r) => r["_measurement"] == "bus_delays")
                                      |> filter(fn: (r) => r["route_id"] == "{viaggio["route_id"]}")
                                      |> filter(fn: (r) => r["_field"] == "delay_sec")
                                      |> filter(fn: (r) => date.hour(t: r._time) == {ora_target})
                                      |> filter(fn: (r) => date.weekDay(t: r._time) == {giorno_corrente_flux})
                                      |> mean()
                                '''
                                
                                tabelle = query_api.query(flux_query)
                                for t in tabelle:
                                    for r in t.records:
                                        ritardo_minuti = float(r.get_value()) / 60.0
                                        
                            except Exception as e:
                                print(f"Exception in Influx [{viaggio['route_id']}]: {e}")
                                pass
                            
                            ora_partenza_casa = datetime.strptime(orario_desiderato, formato_ora)
                            ora_arrivo_palina = ora_partenza_casa + timedelta(minutes=f_dep["tempo_piedi"])
                            
                            # 2. Calcoliamo a che ora parte REALMENTE il bus (teorico + ritardo Influx)
                            ora_bus_teorica = datetime.strptime(dati_f_dep["departure_time"], formato_ora)
                            ora_bus_reale = ora_bus_teorica + timedelta(minutes=ritardo_minuti)
                            
                            # 3. Calcoliamo quanto tempo stai fermo ad aspettare (in minuti)
                            tempo_attesa = (ora_bus_reale - ora_arrivo_palina).total_seconds() / 60
                            
                            # Se per qualche errore di orari l'attesa risulta negativa, la forziamo a 0
                            if tempo_attesa < 0:
                                tempo_attesa = 0

                            tempo_totale = f_dep["tempo_piedi"] + tempo_attesa + tempo_mezzo_teorico + f_arr["tempo_piedi"]
                            
                            opzioni_percorso.append({
                                "route_id": viaggio["route_id"],
                                "trip_id": viaggio["trip_id"],
                                "orario_partenza_bus": dati_f_dep["departure_time"],
                                
                                "da_fermata": f_dep["name"],
                                "lat_fermata_partenza": f_dep["lat"],
                                "lon_fermata_partenza": f_dep["lon"],
                                
                                "a_fermata": f_arr["name"],
                                "lat_fermata_arrivo": f_arr["lat"],
                                "lon_fermata_arrivo": f_arr["lon"],
                                
                                "piedi_partenza": round(f_dep["tempo_piedi"], 1),
                                "attesa_fermata": round(tempo_attesa, 1),
                                "tempo_bus_teorico": round(tempo_mezzo_teorico, 1),
                                "ritardo_influx": round(ritardo_minuti, 1),
                                "piedi_arrivo": round(f_arr["tempo_piedi"], 1),
                                "tempo_totale_stimato": round(tempo_totale, 1)
                            })
                            
                    except Exception as e:
                                print(f"⚠️ Debug Influx [{viaggio['route_id']}]: {e}") # <-- Aggiungiamo questa stampa!
                                pass

    print(f"✅ Trovate {corse_dirette_trovate} corse dirette tra i due gruppi di fermate.")
    print(f"✅ Di queste, {len(opzioni_percorso)} partono dopo le {orario_desiderato}.")
    
    percorsi_unici = {}
    
    opzioni_percorso = sorted(opzioni_percorso, key=lambda x: x["orario_partenza_bus"])
    
    for opz in opzioni_percorso:
        chiave_linea = opz["route_id"]
        
        # Se non abbiamo ancora inserito questa linea nei risultati finali, la aggiungiamo.
        # Così scartiamo tutte le corse successive della stessa linea.
        if chiave_linea not in percorsi_unici:
            percorsi_unici[chiave_linea] = opz

    # Trasformiamo il dizionario filtrato di nuovo in una lista
    lista_finale_pulita = list(percorsi_unici.values())

    lista_finale_pulita = sorted(lista_finale_pulita, key=lambda x: x["tempo_totale_stimato"])
    
    print(f"\n🏆 CLASSIFICA DEI PERCORSI PIÙ VELOCI (Raggruppati per Linea):")
    if not lista_finale_pulita:
        print("Nessun percorso idoneo trovato con i parametri attuali.")
        
    for i, opz in enumerate(lista_finale_pulita[:3]): 
        print(f"{i+1}° POSTO: Linea {opz['route_id']} (Corsa {opz['trip_id']})")
        print(f"Orario di passaggio previsto: {opz['orario_partenza_bus']}")
        print(f"A piedi alla fermata [{opz['da_fermata']}]: {opz['piedi_partenza']} min")
        print(f"Attesa alla fermata: {opz['attesa_fermata']} min")
        print(f"Tempo viaggio del mezzo: {opz['tempo_bus_teorico']} min (Ritardo previsto da Influx: +{opz['ritardo_influx']} min)")
        print(f"Dalla fermata [{opz['a_fermata']}] a destinazione: {opz['piedi_arrivo']} min")
        print(f"TEMPO TOTALE (Da punto a punto): {opz['tempo_totale_stimato']} min\n")
    
    if lista_finale_pulita:
        percorso_vincente = lista_finale_pulita[0]
        trip_id_vincente = percorso_vincente["trip_id"]
        
        print("\n🎨 Preparazione dati spaziali per Grafana...")
        
        corsa = db.trips.find_one({"trip_id": trip_id_vincente})
        shape_id = corsa["shape_id"]
        
        # 2. Recuperiamo la LineString (il disegno del percorso) dalla collezione shapes
        forma = db.shapes.find_one({"shape_id": shape_id})
        
        testo_didascalia = (
            f"Walk to stop: {percorso_vincente['da_fermata']}. "
            f"Take line {percorso_vincente['route_id']} and get off at stop: {percorso_vincente['a_fermata']}. "
            f"Continue on foot to your destination. Total time: {percorso_vincente['tempo_totale_stimato']} min."
        )

        if forma:
            documento_grafana = {
                "id_display": "percorso_attuale", 
                "route_id": percorso_vincente["route_id"],
                "orario_partenza": percorso_vincente["orario_partenza_bus"],
                "tempo_totale": percorso_vincente["tempo_totale_stimato"],
                "partenza_nome": percorso_vincente["da_fermata"],
                "arrivo_nome": percorso_vincente["a_fermata"],
                "geo_path": forma["geo_path"],
                "didascalia": testo_didascalia,
                
                "fermate": [
                    { "nome": percorso_vincente["da_fermata"], "lat": percorso_vincente["lat_fermata_partenza"], "lon": percorso_vincente["lon_fermata_partenza"], "tipo": "partenza" },
                    { "nome": percorso_vincente["a_fermata"], "lat": percorso_vincente["lat_fermata_arrivo"], "lon": percorso_vincente["lon_fermata_arrivo"], "tipo": "arrivo" }
                ],
                
                "punti_input": [
                    { "nome": "Origine", "lat": lat_partenza, "lon": lon_partenza },
                    { "nome": "Destinazione", "lat": lat_arrivo, "lon": lon_arrivo }
                ]
            }
            
            db.grafana_display.delete_many({}) 
            db.grafana_display.insert_one(documento_grafana)
            print(f"✅ Percorso della Linea {percorso_vincente['route_id']} calcolato!")
            
            return documento_grafana
        else:
            print("Impossibile trovare le geometrie per questa linea.")
            return None #Ritorna None in caso di errore
    
    # Se non trova nessuna lista finale
    return None