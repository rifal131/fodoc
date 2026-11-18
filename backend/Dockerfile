# FODOC Backend API — Siap Deploy Gratis 24 Jam di Hugging Face Spaces (Docker, 16 GB RAM)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    YOLO_CONFIG_DIR=/tmp/Ultralytics \
    MPLCONFIGDIR=/tmp/matplotlib \
    HOME=/home/user

# Library sistem minimal yang dibutuhkan OpenCV & ONNX Runtime di Linux
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user UID 1000 sesuai standar Hugging Face Spaces
RUN useradd -m -u 1000 user
WORKDIR /app

# Install PyTorch CPU-only dulu (ringan ~180 MB, jauh lebih cepat daripada CUDA build 2.5 GB)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY requirements-docker.txt /app/requirements-docker.txt
RUN pip install --no-cache-dir -r /app/requirements-docker.txt

# Salin kode backend + model ML (ONNX & landmark .pt)
COPY --chown=user:user . /app
RUN mkdir -p /app/storage_data /tmp/Ultralytics /tmp/matplotlib && \
    chown -R user:user /app /tmp/Ultralytics /tmp/matplotlib

USER user
EXPOSE 7860

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-7860} --workers 1"]
