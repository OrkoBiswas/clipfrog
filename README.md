# ClipForge

Production-oriented video clipping workspace, built against [the master specification](CODEX_BUILD_PROMPT_VIDEO_CLIPPER_SAAS.md). **In development; the full video-processing MVP is not yet complete.** See [phase status](docs/IMPLEMENTATION.md).

## Requirements

- Docker Desktop with the Linux engine running; at least 8 GB RAM recommended for development.
- The initial MinIO build compiles its official source release because upstream container images are unavailable. Allow extra time for the first build. See `infra/minio.Dockerfile` for the pinned release (AGPLv3).
- For host development: Node.js 22+, Python 3.12, FFmpeg/ffprobe.

## Full local stack

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
curl http://localhost:8000/ready
```

PowerShell: use `Copy-Item .env.example .env`. Open http://localhost:3000 and register. Email links arrive in Mailpit at http://localhost:8025. API docs: http://localhost:8000/docs. MinIO console: http://localhost:9001. Its local credentials are `clipforge_local` / `clipforge_local_password`; use unique credentials in production. The bucket is created automatically and stays private.

Compose runs migrations before API/worker startup. To run explicitly:

```bash
docker compose run --rm migrate
docker compose logs -f api worker
docker compose exec worker celery -A clipforge_worker.celery_app:celery inspect ping
python scripts/check_services.py
python scripts/check_auth.py
```

## Host development

```bash
docker compose up -d postgres redis minio minio-init mailpit
npm install
python -m venv .venv
# Activate .venv (Windows: .venv\Scripts\Activate.ps1; POSIX: source .venv/bin/activate)
pip install -e '.[dev]'
alembic -c apps/api/alembic.ini upgrade head
uvicorn clipforge_api.main:app --reload --port 8000
```

In separate terminals with the environment activated:

```bash
celery -A clipforge_worker.celery_app:celery worker -l INFO -Q analysis,render,maintenance --concurrency=1
npm run dev
```

Run Celery in Docker on Windows (Celery does not support Windows prefork).

## Checks

```bash
npm run lint
npm run typecheck
npm test
npm run build
ruff check .
mypy
pytest
alembic -c apps/api/alembic.ini check
npx playwright install chromium
npm run test:e2e
```

E2E tests require a running stack and create isolated real accounts/projects. API unit tests use a temporary SQLite database to test authorization and validation; integration/E2E checks use actual PostgreSQL, Redis and MinIO.

Generate the E2E upload fixture first:

```bash
mkdir -p .local
docker compose exec -T worker python scripts/make_fixture.py
docker compose cp worker:/tmp/fixture.mp4 .local/fixture.mp4
python scripts/check_brands.py
npm run test:e2e
```

On PowerShell, use `New-Item -ItemType Directory -Force .local` instead of `mkdir -p`. PostgreSQL is bound to `127.0.0.1:55432` to avoid conflicts with an existing local server. `docker-compose.dev.yml` optionally mounts Python source for development: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d api worker`. Restart the worker after Python changes.

Uploads go directly from the browser to signed multipart URLs. Pause/retry preserves completed parts; after a page refresh, select the same file to resume. Completion is validated against actual storage parts and queued for ffprobe. If storage completed an upload before an interrupted database commit, resuming recovers it without re-uploading. Canceling or expiring that session also removes its stored object. Project deletion queues remote asset cleanup before removing database records.

Run `python scripts/check_upload_recovery.py` after generating `.local/fixture.mp4` to exercise interrupted completion and cancellation against real storage. The scheduled maintenance worker expires uploads and authentication sessions and republishes stale jobs only when their worker lock is available. After running the speech pipeline checks below, `python scripts/check_recovery.py` verifies that a live worker lock is respected, an interrupted cancellation completes, and a committed-but-undelivered job recovers.

After validation, choose **Analyze video** for real faster-whisper transcription, scene detection and sampled face analysis. The first analysis downloads the open-source speech model to the persistent model cache. Choose **Find highlights** to score natural sentence windows, audio energy and visual signals, then select distinct moments. Results include score explanations; a short source may produce fewer clips than requested. Render the selected highlights, preview MP4s, edit trims/captions/framing and render new revisions. Manual clips support validated sources without speech. Completed clips can be downloaded individually or packaged as a ZIP.

## Brand kits

Open **Brand Kit** to save a reusable logo, primary/secondary caption colors, caption style/font/size, opening-title style, watermark text and position, and preferred output ratios. Platform presets select the matching aspect ratio; clip duration remains a project setting. Logos accept PNG, JPEG or WebP up to 2 MB/four million pixels and are normalized to private PNG assets. Logo storage counts toward your allowance.

On a project, use **Project branding → Apply brand kit**. New manual/highlight clips inherit the settings. Select **Also update existing clips** to apply the appearance to existing clips while preserving edited caption text, then re-render them. The clip editor supports nine logo positions, dragging, size, opacity and margins. Removing a project kit clears its logo when updating existing clips; caption and text styling remains editable.

Projects retain a copy of applied settings and logo assets, so editing/deleting a reusable kit does not break existing renders. Project deletion cleans up its saved logo copies. Optional intro/outro assets are not implemented.

`python scripts/check_brands.py` exercises real authentication, private storage, ownership checks, project snapshots, FFmpeg logo rendering and reapplication. It requires the running stack, host FFmpeg and `.local/fixture.mp4`, and prepares the logo fixture used by browser E2E tests. Diagnostic MP4/PNG outputs remain in ignored `.local/`.

To verify the processing pipeline with your own speech fixture, save a real video at `.local/speech.mp4`, then run these commands with the virtual environment activated:

```bash
python scripts/check_analysis.py
python scripts/check_highlights.py
python scripts/check_render.py
python scripts/check_export.py
```

These commands create an isolated account, upload through multipart storage, analyze speech, select highlights, render a portrait MP4, download/ffprobe it, edit/re-render, and verify ZIP/subtitle exports. Test account details stay in ignored `.local/analysis-test.json`.

## Interactive clip editor

Open a project and choose **Edit clip** (or **Create manual clip**). The composition preview shows the cropped source, captions, title, watermark and logo. Drag the source to override automatic framing, or drag captions/the logo to reposition them. Automatic static framing stays fixed within each detected source shot and switches immediately at a scene cut. Low framing scores block automatic rendering; manually inspect and correct the crop when needed. Footage without reliable face detections is explicitly unscored.

Choose among 25 caption templates, then change typography, colors, stroke, position, word grouping and animation. Save custom templates and manage favorites, recent choices and your default. Brand Kit can reuse these settings. Fonts are bundled with their license files in `apps/web/public/fonts`.

**Render 4-second preview** uses the same FFmpeg pipeline as final output and counts toward render usage. The instant browser preview approximates animation and text wrapping; use the rendered preview to judge exact appearance. Preview clips stay out of the clip library and ZIP exports, but their stored media counts toward storage until the project is deleted.

Run `python scripts/check_editor_media.py` for all 25 real caption renders and a deterministic hard-cut crop pixel check. Outputs are written to `.local/editor-validation/`. The editor browser test also confirms identical preview/final MP4 hashes for the same four-second composition. Synthetic face annotations test crop geometry; they do not establish real-world face-detector or active-speaker accuracy.

Local upload is available after creating a project, in **Source video → Choose source video → Upload video**. YouTube URL ingestion is not implemented; the original build specification starts with local files.

## Environment and deployment

`.env.example` is the shared environment contract for API and worker. Frontend only reads `NEXT_PUBLIC_API_URL` (browser) and `API_INTERNAL_URL` (server). No secrets belong in public variables. Set `COOKIE_SECURE=true` behind HTTPS and set `APP_URL` to the exact frontend origin. Browser mutations enforce that origin, in addition to SameSite cookies and strict CORS. Database sessions can be revoked. Password reset revokes all sessions.

Use managed PostgreSQL/Redis, private S3-compatible storage, TLS termination, backups, and dedicated worker containers for production. Never expose database, Redis or MinIO admin ports publicly. Configure storage CORS for your frontend origin. Run migrations as a single release job before rolling API/worker updates. Do not run FFmpeg inside serverless request handlers.

CPU defaults: `WORKER_DEVICE=cpu`, `WHISPER_COMPUTE_TYPE=int8`. GPU deployment needs a CUDA-compatible worker image and device access; setting `WORKER_DEVICE=cuda` alone is insufficient. Optional semantic scoring requires `AI_PROVIDER=openai-compatible`, `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL` and project opt-in. Provider failures retain local scores. `HIGHLIGHT_WEIGHTS` accepts seven nonnegative integer weights totaling 100.

Optional Stripe checkout, customer portal and signed subscription webhooks are implemented. Configure `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_CREATOR` and `STRIPE_PRICE_PRO` for your test account and send webhooks to `/api/v1/billing/webhook`. Live provider acceptance still requires your Stripe credentials; automated tests mock the provider. Local clipping works without billing or AI credentials, within the configured free-plan quotas.

To stop without deleting data: `docker compose down`. Local data lives in named volumes; only use `docker compose down -v` when deliberately discarding all local accounts and media.

