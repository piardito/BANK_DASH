# Image Python légère 
FROM python:3.10-slim

# Empêche Python de générer des fichiers .pyc
ENV PYTHONDONTWRITEBYTECODE=1
# Empêche Python de bufferiser la sortie (utile pour logs Azure)
ENV PYTHONUNBUFFERED=1

# Répertoire de travail
WORKDIR /app

# Installer les dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copier les dépendances Python
COPY requirements.txt .

# Installer les dépendances Python sans cache
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste du projet
COPY . .

# Streamlit écoute sur 8000 pour Azure
EXPOSE 8000

# Commande de démarrage optimisée
CMD ["streamlit", "run", "app.py", "--server.port=8000", "--server.address=0.0.0.0"]
