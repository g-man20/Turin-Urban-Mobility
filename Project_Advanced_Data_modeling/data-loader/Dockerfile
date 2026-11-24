FROM python:3.9-slim

WORKDIR /app

# Installa le dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia lo script e tutti i file di dati
COPY . .

# Avvia lo script orchestratore che popola tutti i database
CMD ["python", "orchestrator.py"]