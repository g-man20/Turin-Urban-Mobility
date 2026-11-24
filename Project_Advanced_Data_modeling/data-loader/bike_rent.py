# servizio_bici.py
import osmnx as ox
import networkx as nx
from pymongo import MongoClient


# Costanti statiche
VELOCITA_PIEDI = 1.25  # m/s (circa 4.5 km/h, andatura pedonale media standard)
VELOCITA_BICI  = 3.33  # m/s (circa 12 km/h, andatura ciclistica urbana ToBike)

# Connessione a MongoDB
MONGO_URI = "mongodb://mongodb:27017/"
client = MongoClient(MONGO_URI)
db = client["torino_mobility_db"]

# Gestione strade Torino
print("Caricamento della rete stradale/ciclabile di Torino da OpenStreetMap...")
G = ox.graph_from_place("Turin, Italy", network_type="walk")
print("Mappa stradale di Torino caricata con successo in memoria!")


# FUNZIONE DI GEOLOCALIZZAZIONE DELLE BICI 
def trova_stazione_bike_piu_vicina(lat, lon):
    stazione = db.bike_rent.find_one({
        "location": {
            "$near": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [float(lon), float(lat)]
                }
            }
        }
    })
    return stazione


# Crea i dati per Grafana 
def genera_punti_percorso(lista_nodi, tipo_mezzo, seq_partenza=0):
    punti = []
    for i, nodo in enumerate(lista_nodi):
        lat = G.nodes[nodo]['y']
        lon = G.nodes[nodo]['x']
        punti.append({
            "latitude": float(lat),
            "longitude": float(lon),
            "mezzo": tipo_mezzo,
            "sequenza": seq_partenza + i
        })
    return punti


#ALGORITMO DI ROUTING
def calcola_viaggio_bici(lat_partenza, lon_partenza, lat_arrivo, lon_arrivo):
    stazione_p = trova_stazione_bike_piu_vicina(lat_partenza, lon_partenza)
    stazione_a = trova_stazione_bike_piu_vicina(lat_arrivo, lon_arrivo)
    
    if not stazione_p or not stazione_a:
        return [{"errore": "Stazioni non trovate"}]

    coord_staz_p = (stazione_p['location']['coordinates'][1], stazione_p['location']['coordinates'][0])
    coord_staz_a = (stazione_a['location']['coordinates'][1], stazione_a['location']['coordinates'][0])
    
    print(f"Stazione Partenza trovata: {stazione_p['station_name']}")
    print(f"Stazione Arrivo trovata: {stazione_a['station_name']}")
    

# Tratta 1: A piedi alla stazione
    nodo_orig = ox.nearest_nodes(G, X=lon_partenza, Y=lat_partenza)
    nodo_staz_p = ox.nearest_nodes(G, X=coord_staz_p[1], Y=coord_staz_p[0])
    nodi_t1 = nx.shortest_path(G, nodo_orig, nodo_staz_p, weight="length") 
    dist_piedi_1 = nx.path_weight(G, nodi_t1, weight="length")
    tempo_piedi_1 = dist_piedi_1 / VELOCITA_PIEDI
    tratta_piedi_1 = genera_punti_percorso(nodi_t1, "piedi_andata", 0)

# Tratta 2: In bici
    nodo_staz_a = ox.nearest_nodes(G, X=coord_staz_a[1], Y=coord_staz_a[0])
    nodi_t2 = nx.shortest_path(G, nodo_staz_p, nodo_staz_a, weight="length")
    dist_bici = nx.path_weight(G, nodi_t2, weight="length")
    tempo_bici = dist_bici / VELOCITA_BICI
    tratta_bici = genera_punti_percorso(nodi_t2, "bici", 0)

# Tratta 3: A piedi alla meta
    nodo_dest = ox.nearest_nodes(G, X=lon_arrivo, Y=lat_arrivo)
    nodi_t3 = nx.shortest_path(G, nodo_staz_a, nodo_dest, weight="length")
    dist_piedi_2 = nx.path_weight(G, nodi_t3, weight="length")
    tempo_piedi_2 = dist_piedi_2 / VELOCITA_PIEDI
    tratta_piedi_2 = genera_punti_percorso(nodi_t3, "piedi_ritorno", 0)

    tappe_chiave = [
        {"latitude": float(G.nodes[nodo_orig]['y']), "longitude": float(G.nodes[nodo_orig]['x']), "tipo": "Partenza", "descrizione": "Partenza"},
        {"latitude": float(G.nodes[nodo_staz_p]['y']), "longitude": float(G.nodes[nodo_staz_p]['x']), "tipo": "Presa", "descrizione": f"Prendi bici: {stazione_p['station_name']}"},
        {"latitude": float(G.nodes[nodo_staz_a]['y']), "longitude": float(G.nodes[nodo_staz_a]['x']), "tipo": "Rilascio", "descrizione": f"Lascia bici: {stazione_a['station_name']}"},
        {"latitude": float(G.nodes[nodo_dest]['y']), "longitude": float(G.nodes[nodo_dest]['x']), "tipo": "Arrivo", "descrizione": "Arrivo"}
    ]         

    metri_totali = dist_piedi_1 + dist_bici + dist_piedi_2
    tempo_totale_minuti = (tempo_piedi_1 + tempo_bici + tempo_piedi_2) / 60
    
    #Calcoliamo i minuti arrotondati per ogni singola tratta
    min_p1 = round(tempo_piedi_1 / 60)
    min_bici = round(tempo_bici / 60)
    min_p2 = round(tempo_piedi_2 / 60)

    # Creiamo la frase riassuntiva dinamica
    tempo_totale_minuti_rounded = round(tempo_totale_minuti, 1)
    testo_riassunto = (
        f"To reach your destination, walk for {round(dist_piedi_1)}m ({min_p1} min) "
        f"to the '{stazione_p['station_name']}' station. Take a bike and cycle for {round(dist_bici)}m "
        f"({min_bici} min) to the '{stazione_a['station_name']}' station. Finally, walk for {round(dist_piedi_2)}m "
        f"({min_p2} min) to your destination. Total travel time: {tempo_totale_minuti_rounded} min."
    )

    return {
        "tratta_piedi_1": tratta_piedi_1,
        "tratta_bici": tratta_bici,
        "tratta_piedi_2": tratta_piedi_2,
        "statistiche": [{
            "metri_totali": round(metri_totali),
            "tempo_minuti": round(tempo_totale_minuti, 1),
            "risultato": testo_riassunto
        }],
        "tappe": tappe_chiave
    }


