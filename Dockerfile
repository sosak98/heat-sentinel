# HeatSentinel — image « Jetson-ready »
# Vision edge: le modèle (~2 Mo) + agent + dashboard tournent sur NVIDIA Jetson,
# hors-ligne. NON testée sur matériel réel (JetPack 5.x + ONNX Runtime) —
# ce Dockerfile documente la vision de déploiement (voir edge/jetson/README.md).
#
# Build (dev/PC):          docker build -t heatsentinel .
# Lancer:                  docker run -p 8000:8000 heatsentinel
# Sur Jetson (JetPack):    préférer une image basée sur l4t-base + ONNX Runtime,
#                          et exporter le modèle en ONNX (artifacts/model.onnx).

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# entraînement au build (~30 s) — le modèle est embarqué, l'edge est autonome
RUN python train.py

EXPOSE 8000
CMD ["python", "run_server.py"]
