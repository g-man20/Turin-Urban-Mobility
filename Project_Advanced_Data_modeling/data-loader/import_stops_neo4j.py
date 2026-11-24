import csv
from neo4j import GraphDatabase

NEO4J_URI = "bolt://torino_neo4j:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "password123"  # Usa la password che hai messo nel docker-compose

def importa_fermate_da_csv(file_path):
    print("--- AVVIO IMPORTAZIONE FERMATE SU NEO4J ---")
    
    # 1. Connessione al database
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    # 2. La Query Cypher

    #Merge per non creare duplicati 
    query = """
    MERGE (f:Fermata {stop_id: $stop_id}) 
    SET f.nome = $stop_name,
        f.descrizione = $stop_desc,
        f.lat = toFloat($stop_lat),
        f.lon = toFloat($stop_lon),
        f.location = point({latitude: toFloat($stop_lat), longitude: toFloat($stop_lon)})
    """
    
    # 3. Lettura del CSV e scrittura nel DB
    conteggio = 0
    with driver.session() as session:
        # Apriamo il file CSV. 
        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                # Eseguiamo la query passando i valori esatti estratti dal CSV
                session.run(query, 
                            stop_id=row['stop_id'], 
                            stop_name=row['stop_name'],
                            stop_desc=row['stop_desc'],
                            stop_lat=row['stop_lat'], 
                            stop_lon=row['stop_lon'])
                
                conteggio += 1
                if conteggio % 500 == 0:
                    print(f"   -> Caricate {conteggio} fermate...")
                    
    driver.close()
    print(f"--- SUCCESSO! {conteggio} Nodi 'Fermata' creati in Neo4j. ---")

if __name__ == "__main__":
    from pathlib import Path
    data_dir = Path(__file__).resolve().parent / "data" / "stops.txt"
    importa_fermate_da_csv(str(data_dir))