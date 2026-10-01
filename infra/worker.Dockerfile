FROM python:3.12-slim AS worker
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl libgles2 libegl1 fonts-dejavu-core fonts-noto-core fonts-bebas-neue fonts-lato fonts-montserrat fonts-open-sans fonts-roboto && rm -rf /var/lib/apt/lists/*
COPY requirements-dev.lock requirements-media.lock /app/
RUN pip install --no-cache-dir -r requirements-dev.lock -r requirements-media.lock
RUN mkdir -p /opt/models && curl --fail --location --retry 3 https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite -o /opt/models/blaze_face_short_range.tflite
RUN useradd --create-home appuser && mkdir -p /home/appuser/.cache/clipforge && chown -R appuser:appuser /home/appuser/.cache
COPY pyproject.toml ./
COPY apps/api apps/api
COPY workers/media workers/media
COPY scripts scripts
RUN pip install --no-cache-dir --no-deps .
USER appuser
