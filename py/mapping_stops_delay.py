import pandas as pd
import xml.etree.ElementTree as ET
from math import radians, cos, sin, asin, sqrt

def haversine(lon1, lat1, lon2, lat2):
    """Calcola la distanza in metri tra due punti geografici."""
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371000 # Raggio della Terra in metri
    return c * r

def get_sensors_from_xml(xml_file):
    """Estrae i sensori con le loro coordinate dall'XML."""
    tree = ET.parse(xml_file)
    root = tree.getroot()
    namespace = {'ns': 'https://simone.5t.torino.it/ns/traffic_data.xsd'}
    
    sensors = []
    for fdt in root.findall('ns:FDT_data', namespace):
        sensors.append({
            'sensor_id': fdt.get('lcd1'),
            'road_name': fdt.get('Road_name'),
            'lat': float(fdt.get('lat')),
            'lon': float(fdt.get('lng')),
            'speed': float(fdt.find('ns:speedflow', namespace).get('speed', 0))
        })
    return sensors

def geo_match(stops_file, sensors, max_dist_meters=500):
    """Associa ogni fermata al sensore più vicino entro un raggio massimo."""
    stops_df = pd.read_csv(stops_file)
    mapping = []

    print(f"Inizio matching geospaziale (Raggio: {max_dist_meters}m)...")
    
    for _, stop in stops_df.iterrows():
        closest_sensor = None
        min_dist = max_dist_meters
        
        for sensor in sensors:
            dist = haversine(stop['stop_lon'], stop['stop_lat'], sensor['lon'], sensor['lat'])
            
            if dist < min_dist:
                min_dist = dist
                closest_sensor = sensor
        
        if closest_sensor:
            mapping.append({
                'stop_id': stop['stop_id'],
                'stop_name': stop['stop_name'],
                'sensor_id': closest_sensor['sensor_id'],
                'road_name': closest_sensor['road_name'],
                'distance_m': round(min_dist, 2)
            })

    return pd.DataFrame(mapping)

# --- ESECUZIONE ---
sensors_data = get_sensors_from_xml('get_fdt.xml')
result_df = geo_match('stops.txt', sensors_data)

result_df.to_csv('geo_mapping_stops_sensors.csv', index=False)
print(f"Matching completato! Trovate {len(result_df)} associazioni.")
print(result_df.head())