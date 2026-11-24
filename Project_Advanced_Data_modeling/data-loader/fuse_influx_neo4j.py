from influxdb_client import InfluxDBClient
from neo4j import GraphDatabase


INFLUX_URL = "http://influxdb:8086"  # Dentro Docker: usa il nome del servizio
INFLUX_TOKEN = "il_mio_super_token_segreto_123"
INFLUX_ORG = "torino_org"
INFLUX_BUCKET = "torino_mobility"

NEO4J_URI = "bolt://torino_neo4j:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password123"

def fusione_dati_traffico():
    print("--- AVVIO SCRIPT DI FUSIONE: INFLUXDB ──▶ NEO4J ---")

    print("1. Interrogazione di InfluxDB (Media ultimi 7 giorni)...")
    influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    query_api = influx_client.query_api()

    # La query Flux raggruppa i dati per tratta univoca e ne calcola la media matematica
    flux_query = f"""
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -30d)
      |> filter(fn: (r) => r["_measurement"] == "traffic_edges_grafana")
      |> filter(fn: (r) => r["_field"] == "delay_sec")
      |> group(columns: ["route_id", "source", "target"])
      |> mean()
    """
    
    tabelle = query_api.query(flux_query)
    
    # Raccogliamo le medie calcolate in una lista di dizionari
    dati_traffico = []
    for table in tabelle:
        for record in table.records:
            dati_traffico.append({
                "route_id": record.values.get("route_id"),
                "source_id": record.values.get("source"),
                "target_id": record.values.get("target"),
                "ritardo_medio": round(float(record.get_value()), 2) # Arrotondiamo a 2 decimali
            })
            
    influx_client.close()
    print(f"   -> Calcolate le medie storiche per {len(dati_traffico)} tratte stradali.")


    print("2. Iniezione dei pesi (ritardi medi) nel grafo Neo4j...")
    neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    # Query Cypher: Cerca l'arco specifico della linea tra le due fermate e aggiorna la proprietà
    cypher_query = """
    MATCH (a:Fermata {stop_id: $source_id})-[r:TRATTO {route_id: $route_id}]->(b:Fermata {stop_id: $target_id})
    SET r.ritardo_medio_7g = $ritardo_medio
    """
    
    aggiornati = 0
    with neo4j_driver.session() as session:
        for tratto in dati_traffico:
            # Eseguiamo l'aggiornamento su Neo4j
            result = session.run(cypher_query, 
                                 source_id=tratto["source_id"], 
                                 target_id=tratto["target_id"], 
                                 route_id=tratto["route_id"], 
                                 ritardo_medio=tratto["ritardo_medio"])
            
            aggiornati += 1
            if aggiornati % 500 == 0:
                print(f"   -> Aggiornati {aggiornati} archi...")

    neo4j_driver.close()


if __name__ == "__main__":
    fusione_dati_traffico()