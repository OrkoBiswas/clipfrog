# Configuration ownership

Runtime settings live in `apps/api/clipforge_api/config.py` and are shared by the API and Celery worker. `.env.example` lists the local contract. Compose overrides only internal network addresses.

Reusable platform defaults live in `packages/shared/platforms.json`. They are product defaults, not guarantees about a platform’s changing upload limits.

The browser's API origin is `NEXT_PUBLIC_API_URL`. The Next.js server uses `API_INTERNAL_URL`. User-specific data is fetched with `cache: no-store` and server-validated cookies.
