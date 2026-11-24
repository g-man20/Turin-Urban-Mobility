#!/usr/bin/env python3
"""
Script Orchestratore per l'Inizializzazione Completa dei Database
Esegue la popolazione di MongoDB, InfluxDB e Neo4j in ordine corretto
"""

import time
import sys
from neo4j import GraphDatabase

# ==========================================
# FASE 1: Esecuzione di load_data.py
# ==========================================
def esegui_load_data():
    """Popola MongoDB e InfluxDB"""
    print("\n" + "="*70)
    print("FASE 1: POPOLAZIONE MONGODB E INFLUXDB")
    print("="*70)
    
    try:
        import load_data
        # Connessione con retry
        mongo_cli, influx_cli = load_data.connetti_con_retry()
        # Popola i database
        load_data.popola_mongodb(mongo_cli)
        load_data.popola_influxdb(influx_cli)
        print("✓ MongoDB e InfluxDB popolati con successo!")
        return True
    except Exception as e:
        print(f"✗ Errore durante il popolamento: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==========================================
# FASE 2: Esecuzione import_stops_neo4j.py
# ==========================================
def esegui_importazione_stops():
    """Crea i nodi Fermata in Neo4j"""
    print("\n" + "="*70)
    print("FASE 2: IMPORTAZIONE FERMATE IN NEO4J")
    print("="*70)
    
    try:
        from pathlib import Path
        import import_stops_neo4j
        data_dir = Path(__file__).resolve().parent / "data" / "stops.txt"
        import_stops_neo4j.importa_fermate_da_csv(str(data_dir))
        print("✓ Fermate importate con successo in Neo4j!")
        return True
    except Exception as e:
        print(f"✗ Errore durante l'importazione fermate: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==========================================
# FASE 3: Esecuzione import_edges_csv.py
# ==========================================
def esegui_importazione_edges():
    """Crea gli archi TRATTO in Neo4j"""
    print("\n" + "="*70)
    print("FASE 3: IMPORTAZIONE ARCHI TOPOLOGICI IN NEO4J")
    print("="*70)
    
    try:
        import import_edges_csv
        import_edges_csv.importa_archi_da_csv()
        print("✓ Archi topologici importati con successo in Neo4j!")
        return True
    except Exception as e:
        print(f"✗ Errore durante l'importazione archi: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==========================================
# FASE 4: Esecuzione fuse_influx_neo4j.py
# ==========================================
def esegui_fusione_dati():
    """Arricchisce gli archi di Neo4j con i dati di traffico da InfluxDB"""
    print("\n" + "="*70)
    print("FASE 4: FUSIONE DATI TRAFFICO (INFLUXDB → NEO4J)")
    print("="*70)
    
    try:
        import fuse_influx_neo4j
        fuse_influx_neo4j.fusione_dati_traffico()
        print("✓ Dati di traffico fusi con successo in Neo4j!")
        return True
    except Exception as e:
        print(f"✗ Errore durante la fusione dati: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==========================================
# ATTESA NEO4J
# ==========================================
def attendi_neo4j(max_tentativi=30, delay=2):
    """Attende che Neo4j sia pronto prima di procedere"""
    print("\nVerifica della disponibilità di Neo4j...")
    
    NEO4J_URI = "bolt://torino_neo4j:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "password123"
    
    for tentativo in range(max_tentativi):
        try:
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            with driver.session() as session:
                session.run("RETURN 1")
            driver.close()
            print("✓ Neo4j è pronto!")
            return True
        except Exception as e:
            print(f"  Tentativo {tentativo + 1}/{max_tentativi}: Neo4j non ancora pronto, riprovo tra {delay}s...")
            time.sleep(delay)
    
    print("✗ Neo4j non è diventato disponibile entro il tempo limite!")
    return False

# ==========================================
# MAIN
# ==========================================
def main():
    start_time = time.time()
    
    print("\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█" + "  SCRIPT ORCHESTRATORE DI INIZIALIZZAZIONE".center(68) + "█")
    print("█" + "  Database: MongoDB, InfluxDB, Neo4j".center(68) + "█")
    print("█" + " "*68 + "█")
    print("█"*70)
    
    # Attenda Neo4j
    if not attendi_neo4j():
        print("\n✗ ERRORE: Impossibile connettersi a Neo4j. Uscita...")
        sys.exit(1)
    
    # Esegui le fasi in ordine
    risultati = []
    
    risultati.append(("MongoDB + InfluxDB", esegui_load_data()))
    risultati.append(("Fermate Neo4j", esegui_importazione_stops()))
    risultati.append(("Archi Neo4j", esegui_importazione_edges()))
    risultati.append(("Fusione Traffico", esegui_fusione_dati()))
    
    # Riepilogo finale
    print("\n" + "="*70)
    print("RIEPILOGO ESECUZIONE")
    print("="*70)
    
    tutti_ok = True
    for fase, riuscita in risultati:
        status = "✓ SUCCESSO" if riuscita else "✗ ERRORE"
        print(f"{fase:.<40} {status}")
        if not riuscita:
            tutti_ok = False
    
    elapsed = round(time.time() - start_time, 2)
    print("="*70)
    
    if tutti_ok:
        print(f"\n✓ PIPELINE COMPLETATA CON SUCCESSO in {elapsed} secondi!")
        print("  Tutti i database sono stati popolati correttamente.")
        sys.exit(0)
    else:
        print(f"\n✗ PIPELINE COMPLETATA CON ERRORI in {elapsed} secondi!")
        print("  Controlla i messaggi di errore sopra.")
        sys.exit(1)

if __name__ == "__main__":
    main()
