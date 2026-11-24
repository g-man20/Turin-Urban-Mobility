from flask import Flask, jsonify,request
from flask_cors import CORS
from pymongo import MongoClient
from neo4j import GraphDatabase
import bike_rent
import calcolo_mezzi

app = Flask(__name__)
CORS(app)

# Ci connettiamo a MongoDB
client = MongoClient("mongodb://mongodb:27017/")
db = client["torino_mobility_db"]

##Connessione a Neo4j
NEO4J_URI = "bolt://torino_neo4j:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password123"

@app.route('/api/percorso-bus', methods=['GET'])
def get_percorso_bus():
    lat_p = float(request.args.get('lat_p', 45.0722))
    lon_p = float(request.args.get('lon_p', 7.6669))
    lat_a = float(request.args.get('lat_a', 45.0705))
    lon_a = float(request.args.get('lon_a', 7.6868))
    
    # Algoritmo di routing
    dati_percorso = calcolo_mezzi.calcola_percorso_ottimale(
        orario_desiderato="08:00:00",
        lat_partenza=lat_p, 
        lon_partenza=lon_p, 
        lat_arrivo=lat_a, 
        lon_arrivo=lon_a
    )
    
    if dati_percorso:
        dati_percorso.pop('_id', None)
        return jsonify(dati_percorso)
    else:
        return jsonify({"errore": "Nessun percorso idoneo trovato"}), 404

@app.route('/api/percorso', methods=['GET'])
def get_percorso():
    lat_p = float(request.args.get('lat_p', 45.0575))
    lon_p = float(request.args.get('lon_p', 7.6645))
    lat_a = float(request.args.get('lat_a', 45.0750))
    lon_a = float(request.args.get('lon_a', 7.6980))
    
    # Algoritmo
    dati_percorso = bike_rent.calcola_viaggio_bici(lat_p, lon_p, lat_a, lon_a)
    
    return jsonify(dati_percorso)

@app.route('/api/mappa_geojson', methods=['GET'])
def get_mappa_geojson():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    soglia_richiesta = float(request.args.get('soglia', 0.0))
    
    query = """
    MATCH (a:Fermata)-[r:TRATTO]->(b:Fermata)
    WHERE r.ritardo_medio_7g > $soglia
    RETURN a.lat AS lat_a, a.lon AS lon_a, a.nome AS nome_a,
           b.lat AS lat_b, b.lon AS lon_b, b.nome AS nome_b,
           r.route_id AS linea, r.ritardo_medio_7g AS ritardo
    """
    
    features = []
    with driver.session() as session:
        risultati = session.run(query, soglia=soglia_richiesta)
        for record in risultati:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [record["lon_a"], record["lat_a"]], 
                        [record["lon_b"], record["lat_b"]]  
                    ]
                },
                "properties": {
                    "linea": record["linea"],
                    "partenza": record["nome_a"],
                    "arrivo": record["nome_b"],
                    "ritardo": record["ritardo"]
                }
            }
            features.append(feature)
            
    driver.close()
    
    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }
    return jsonify(geojson_data)

@app.route('/api/fermate_geojson', methods=['GET'])
def get_fermate_geojson():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    # Cerchiamo in Neo4j tutti i nodi di tipo Fermata
    query = """
    MATCH (f:Fermata)
    WHERE f.lat IS NOT NULL AND f.lon IS NOT NULL
    RETURN f.nome AS nome, f.lat AS lat, f.lon AS lon
    """
    
    features = []
    with driver.session() as session:
        risultati = session.run(query)
        for record in risultati:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",          
                    "coordinates": [record["lon"], record["lat"]]
                },
                "properties": {
                    "nome": record["nome"]
                }
            }
            features.append(feature)
            
    driver.close()
    
    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }
    return jsonify(geojson_data)

@app.route('/api/mappa_geojson_filtrata', methods=['GET'])
def get_mappa_geojson_filtrata():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    soglia_richiesta = float(request.args.get('soglia', 0.0))
    
    # Leggiamo il parametro delle linee inviato da Grafana
    linee_richieste = request.args.get('linee', None)
    
    # Se l'utente ha selezionato delle linee specifiche e NON ha scelto "All"
    if linee_richieste and linee_richieste != "All":
        # Trasformiamo la stringa "3092E,40U" in una lista pulita spazi compresi: ['3092E', '40U']
        lista_linee = [l.strip() for l in linee_richieste.split(',')]
        
        # Query con il filtro IN sulla relazione del grafo
        query = """
        MATCH (a:Fermata)-[r:TRATTO]->(b:Fermata)
        WHERE r.ritardo_medio_7g > $soglia AND r.route_id IN $linee
        RETURN a.lat AS lat_a, a.lon AS lon_a, a.nome AS nome_a,
               b.lat AS lat_b, b.lon AS lon_b, b.nome AS nome_b,
               r.route_id AS linea, r.ritardo_medio_7g AS ritardo
        """
        parametri = {"soglia": soglia_richiesta, "linee": lista_linee}
    else:
        # Se ha scelto "All" o il parametro è vuoto, si comporta esattamente come la vecchia funzione (mostra tutto)
        query = """
        MATCH (a:Fermata)-[r:TRATTO]->(b:Fermata)
        WHERE r.ritardo_medio_7g > $soglia
        RETURN a.lat AS lat_a, a.lon AS lon_a, a.nome AS nome_a,
               b.lat AS lat_b, b.lon AS lon_b, b.nome AS nome_b,
               r.route_id AS linea, r.ritardo_medio_7g AS ritardo
        """
        parametri = {"soglia": soglia_richiesta}
    
    features = []
    with driver.session() as session:
        risultati = session.run(query, **parametri)
        for record in risultati:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [record["lon_a"], record["lat_a"]], 
                        [record["lon_b"], record["lat_b"]]  
                    ]
                },
                "properties": {
                    "linea": record["linea"],
                    "partenza": record["nome_a"],
                    "arrivo": record["nome_b"],
                    "ritardo": record["ritardo"]
                }
            }
            features.append(feature)
            
    driver.close()
    
    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }
    return jsonify(geojson_data)

if __name__ == '__main__':
    # Facciamo partire il server sulla porta 5000
    app.run(host='0.0.0.0', port=5000)