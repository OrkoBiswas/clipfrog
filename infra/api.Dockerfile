FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY requirements-dev.lock requirements-vision.lock ./
RUN pip install --no-cache-dir -r requirements-dev.lock -r requirements-vision.lock
COPY apps/api apps/api
COPY workers/media workers/media
COPY scripts scripts
COPY assets/vision /opt/models
RUN pip install --no-cache-dir --no-deps .
RUN useradd --create-home appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "clipforge_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
