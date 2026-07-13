FROM python:3.11-slim

# Logs non bufferisés
ENV PYTHONUNBUFFERED=1

# Répertoire de travail
WORKDIR /app

# Installer les dépendances
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier l'app
COPY app.py .

# Copier les données à la racine /data
# (../../data/... depuis /app pointe vers /data/...)
COPY data /data

# Port exposé par Streamlit
EXPOSE 8501

# Lancer l'app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]