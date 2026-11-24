import csv
from collections import defaultdict
from neo4j import GraphDatabase


NEO4J_URI = "bolt://torino_neo4j:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password123"

def importa_archi_da_csv():
    print("--- AVVIO COSTRUZIONE TOPOLOGIA SU NEO4J ---")
    
    from pathlib import Path
    data_dir = Path(__file__).resolve().parent / "data"
    
    # 1. Mappiamo i viaggi alle linee (trips.txt)
    print("1. Lettura di trips.txt in corso...")
    trip_to_route = {}
    with open(str(data_dir / 'trips.txt'), mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_to_route[row['trip_id']] = row['route_id']
            
    print(f"   -> Mappati {len(trip_to_route)} viaggi.")

    # 2. Ricostruiamo le sequenze (stop_times.txt)
    print("2. Lettura di stop_times.txt in corso (potrebbe richiedere qualche secondo)...")
    # Dizionario che associa ad ogni viaggio una lista di tuple: (sequenza, stop_id)
    viaggi_fermate = defaultdict(list)
    
    with open(str(data_dir / 'stop_times.txt'), mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trip_id = row['trip_id']
            if trip_id in trip_to_route: # Ignoriamo i viaggi orfani
                fermata = row['stop_id']
                sequenza = int(row['stop_sequence'])
                viaggi_fermate[trip_id].append((sequenza, fermata))
                
    print(f"   -> Estratte le fermate per {len(viaggi_fermate)} viaggi unici.")

    # 3. Calcoliamo gli archi univoci per non intasare Neo4j
    print("3. Calcolo degli archi topologici univoci...")
    archi_univoci = set() # Un set Python elimina automaticamente i duplicati
    
    for trip_id, fermate in viaggi_fermate.items():
        # Ordiniamo le fermate in base alla loro sequenza (1, 2, 3...)
        fermate_ordinate = sorted(fermate, key=lambda x: x[0])
        route_id = trip_to_route[trip_id]
        
        # Creiamo le coppie (partenza, arrivo)
        for i in range(len(fermate_ordinate) - 1):
            source_id = fermate_ordinate[i][1]
            target_id = fermate_ordinate[i+1][1]
            # Aggiungiamo al set: (A, B, Linea)
            archi_univoci.add((source_id, target_id, route_id))
            
    print(f"   -> Trovati {len(archi_univoci)} archi univoci da scrivere nel database.")

    # 4. Scrittura massiva su Neo4j
    print("4. Scrittura su Neo4j in corso...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    cypher_query = """
    MATCH (a:Fermata {stop_id: $source_id})
    MATCH (b:Fermata {stop_id: $target_id})
    MERGE (a)-[r:TRATTO {route_id: $route_id}]->(b)
    """
    
    inseriti = 0
    with driver.session() as session:
        for arco in archi_univoci:
            session.run(cypher_query, 
                        source_id=arco[0], 
                        target_id=arco[1], 
                        route_id=arco[2])
            inseriti += 1
            if inseriti % 1000 == 0:
                print(f"   -> Inseriti {inseriti} archi...")
                
    driver.close()
    print(f"--- SUCCESSO! La rete di Torino è completa con {inseriti} collegamenti. ---")

if __name__ == "__main__":
    importa_archi_da_csv()