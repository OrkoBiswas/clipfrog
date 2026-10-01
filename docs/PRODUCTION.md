# Deployment guide

The repository is still being implemented; do not launch it as a finished clipping service until the master specification's acceptance checks pass.

Deploy the Next.js standalone container, FastAPI API and Celery workers separately. PostgreSQL, Redis and object storage need private service networking and backups. Compose is the local/reference topology, not a managed production deployment.

## Release procedure

1. Install from committed npm/Python locks, build and test container images.
2. Back up PostgreSQL. Run `alembic -c apps/api/alembic.ini upgrade head` once using the release image.
3. Roll out API and workers, then web. Require `/ready` before admitting traffic.
4. Run the service smoke check and a real upload/render acceptance test.

## Network and credentials

Terminate TLS at a trusted reverse proxy. Set `COOKIE_SECURE=true`, exact `APP_URL`, browser-accessible `NEXT_PUBLIC_API_URL`, and internal `API_INTERNAL_URL`. Never use development passwords. Set storage CORS to the exact web origin and expose only signed object URLs. Use a least-privilege bucket-scoped identity, not a MinIO root account, in production.

MinIO community images are no longer available at the original registry paths. Local Compose builds a pinned official source release; review its AGPLv3 license and upstream maintenance state before using it outside development. The application storage adapter supports other S3-compatible providers without changing project data models.

## Workers

Use bounded concurrency (CPU default: one job per process) and separate `analysis`, `render`, and `maintenance` queues when scaling. Reserve working disk for the largest permitted upload and output set. Do not put FFmpeg work in HTTP request handlers. GPU workers need an NVIDIA runtime, compatible CUDA/cuDNN libraries, and appropriate model compute types; the API/web images never need CUDA.

## Operations

Monitor readiness, queue age, failure rate, PostgreSQL connections, free temporary disk, and storage growth. Preserve database and object-store backups together. Test restoration. Keep Redis persistence enabled for queued jobs. Service logs must not contain passwords, session tokens, presigned URLs, or private transcript text.
