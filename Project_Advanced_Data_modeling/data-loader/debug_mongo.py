from pymongo import MongoClient

# Mi connetto al database (usando il nome del container per Docker)
client = MongoClient("mongodb://mongodb:27017/")
db = client["torino_mobility_db"]

print("--- RADIOGRAFIA DEL DATABASE ---")

# 1. Controlliamo come è salvata la fermata 3285 (Politecnico)
stop = db.stops.find_one({"stop_id": {"$in": ["3285", 3285]}})
print("\n1️⃣ DATI IN 'STOPS':")
print(stop)

# 2. Controlliamo se ESISTE un viaggio che passa di qua
trip = db.trips.find_one({"stop_sequence.stop_id": {"$in": ["3285", 3285]}})

if trip:
    print(f"\n2️⃣ VIAGGIO TROVATO! (Linea: {trip.get('route_id')}, Corsa: {trip.get('trip_id')})")
    print("Ecco come sono scritte le prime 3 fermate di questo viaggio:")
    for fermata in trip.get("stop_sequence")[:3]:
        print(f"  - {fermata}")
else:
    print("\n2️⃣ 🚨 NESSUN VIAGGIO PASSA PER LA FERMATA 3285!")
    print("Questo significa che nel file stop_times gli ID non corrispondono a quelli in stops.txt")
    
    # Peschiamo un viaggio a caso che abbia un array per vedere come sono scritti gli ID
    random_trip = db.trips.find_one({"stop_sequence.0": {"$exists": True}})
    if random_trip:
        print(f"\nEcco un viaggio a caso (Linea: {random_trip.get('route_id')}) per capire il formato:")
        for fermata in random_trip.get("stop_sequence")[:3]:
            print(f"  - {fermata}")
    else:
        print("\n🚨 PANICO: Nessun viaggio ha l'array stop_sequence popolato! L'embedding ha fallito.")