# Turin Mobility Data Platform

This project builds a small data platform for Turin mobility data. It combines:

- MongoDB for geographic and static data
- InfluxDB for time-series traffic data
- Neo4j for graph-based routing and network topology
- Grafana for dashboards
- Flask API for exposing routing and map data

The platform is orchestrated with Docker Compose so that all services can be started with a few terminal commands.

---

## 1. Prerequisites

Make sure the following are installed on your machine:

- Docker Desktop or Docker Engine
- Docker Compose
- Git

On macOS, Docker Desktop is usually enough.

Verify Docker is installed:

```bash
docker --version
docker compose version
```

---

## 2. Clone the Repository

```bash
git clone https://github.com/AlexVhro/Project_Advanced_Data_modeling
cd Project_Advanced_Data_modeling
```

---

## 3. Start the Full Platform

From the project root, run:

```bash
docker compose up --build -d
```

This command will:

- start MongoDB
- start InfluxDB
- start Neo4j
- start Grafana
- start Mongo Express
- build and run the data loader
- start the Flask routing API

---

## 4. Check That Everything Is Running

To verify the containers:

```bash
docker compose ps
```

You should see all services in the `Up` state.

If you want to inspect the loader logs:

```bash
docker compose logs -f data-loader
```

If you want to inspect the Flask API logs:

```bash
docker compose logs -f routing-api
```

---

## 5. Access the Services

Once the stack is running, use these URLs:

- Mongo Express: http://localhost:8081
- Grafana: http://localhost:3000
- Neo4j Browser: http://localhost:7474
- Flask API: http://localhost:5005

### Default Credentials

- Mongo Express: no authentication required
- InfluxDB:
  - username: `admin`
  - password: `passwordSicurissima123`
  - organization: `torino_org`
  - bucket: `torino_mobility`
- Neo4j:
  - username: `neo4j`
  - password: `password123`
- Grafana:
  - username: `admin`
  - password: `admin`

---

## 6. API Endpoints

The Flask API exposes several endpoints.

### Example routes

Get a bus route recommendation:

```bash
curl "http://localhost:5005/api/percorso-bus"
```

Get a bike route recommendation:

```bash
curl "http://localhost:5005/api/percorso"
```

Get all stops as GeoJSON:

```bash
curl "http://localhost:5005/api/fermate_geojson"
```

Get the map as GeoJSON:

```bash
curl "http://localhost:5005/api/mappa_geojson"
```

---

## 7. Populate the Databases Manually (Optional)

The data loader runs automatically at startup, but you can also run it manually if needed.

```bash
docker compose up -d data-loader
```

If you want to rebuild and rerun the loader:

```bash
docker compose build data-loader
docker compose up -d --force-recreate data-loader
```

---

## 8. Stop the Platform

To stop all services:

```bash
docker compose stop
```

To stop and remove containers:

```bash
docker compose down
```

To remove also the volumes and reset all stored data:

```bash
docker compose down -v
```

---

## 9. Rebuild After Code Changes

If you change Python code or Docker configuration, rebuild the affected services:

```bash
docker compose build --no-cache
docker compose up -d --force-recreate
```

---

## 10. Troubleshooting

### Containers do not start

Check the logs:

```bash
docker compose logs
```

### The data loader seems stuck

Inspect its logs:

```bash
docker compose logs -f data-loader
```

### The API is not reachable

Make sure the `routing-api` container is running:

```bash
docker compose ps routing-api
```

If needed, restart it:

```bash
docker compose restart routing-api
```

### Reset everything

If you want a clean restart:

```bash
docker compose down -v
docker compose up --build -d
```

---

## 11. Project Structure Summary

The main folders are:

- `data-loader/` : Python scripts, Dockerfile, and data files
- `docker-compose.yml` : full service orchestration

The main components are:

- `load_data.py` : loads data into MongoDB and InfluxDB
- `orchestrator.py` : runs the full initialization pipeline
- `import_stops_neo4j.py` : imports stops into Neo4j
- `import_edges_csv.py` : imports graph edges into Neo4j
- `fuse_influx_neo4j.py` : enriches Neo4j edges with traffic delay data
- `app.py` : Flask API that exposes routing and GeoJSON endpoints

---

## 12. Notes

The project is designed to run entirely with Docker, so you normally do not need to install Python dependencies manually. The container image handles that for you.

If you want to work locally outside Docker, you can install the requirements from `data-loader/requirements.txt`:

```bash
pip install -r data-loader/requirements.txt
```
