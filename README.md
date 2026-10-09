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
pip install -e '.[dev,vision]'
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

The redesigned workspace includes Dark/Light/System appearance, command search (Ctrl/Cmd+K), an upload-first project wizard, and an integrated clip/caption editor. New projects can also be configured as drafts before uploading. See [frontend progress and verification](CODEX_PROGRESS.md) and the [interface design system](design-system/clipforge/MASTER.md).

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

After validation, choose **Analyze video** for real faster-whisper transcription, scene detection and sampled face analysis. The first analysis downloads the open-source speech model to the persistent model cache. Choose **Find highlights** to compare complete ideas throughout the video. The local engine joins sentences across transcription chunks, evaluates alternative durations, marks uncertain word-aligned cuts, and ranks opening hooks, standalone context, explanation/action, examples, outcomes and delivery. Repetition, housekeeping, promotion and unresolved endings reduce scores. Face detection informs framing, not highlight value. Topic-aware diversity reduces repeated takes and related selections. Results include explanations; a short source may produce fewer clips than requested. Render the selected highlights, preview MP4s, edit trims/captions/framing and render new revisions. Manual clips support validated sources without speech. Completed clips can be downloaded individually or packaged as a ZIP.

**Preview moment**, **Good clip** and **Poor clip** are available beside each new highlight. A poor rating excludes that moment from the current render batch and substantially overlapping proposals from future searches in that project. Clicking a pressed rating clears it. Ratings survive highlight regeneration and remain private to the account that submitted them. Deleting a project also removes its feedback. Old results need **Find highlights** again before they can be rated.

The internal preference learner uses explicit ratings and the original scoring features, without external AI calls or self-generated training labels. It starts evaluating preferences after at least three good and three poor ratings; weights change only when a leave-one-rating-out check improves preference loss without reducing classification accuracy. Adjustments are bounded to 25% of the configured weights and remain on a 100-point scale. New searches use the learned weights; existing clips are not silently rescored. This is a local editorial ranker with supervised preference adaptation, not a pretrained semantic/video understanding model or a prediction of viral views. English, Bengali, Hindi and Spanish cue sets supplement language-neutral timing, punctuation, repetition and delivery checks; other languages receive the structural checks. No-word transcripts cannot be safely cut inside an oversized segment.

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

Under **Layout & safe area** in **Project settings > Edit project settings > Captions & brand**, the template customizer, or the clip editor's Captions panel, turn **Multiple screens** on or off. When enabled, the API and worker inspect the original footage with the bundled YuNet detector, cache its results, and automatically choose a two-person collage or a three/four-person grid. This includes profile faces and people near source edges. Panel crops focus on individual people; a low aesthetic framing score alone does not suppress a detected person. Single-person shots and footage without reliable detections stay full screen. Layout follows camera cuts and sustained changes in the number of people, holding through brief detector losses. Preview and export use the same crops, one playback clock and one audio track; captions, titles and logos apply over the complete composition. Saving project settings sets defaults for new clips; applying a template can update selected existing clips. Use **Render clip** to regenerate older automatic renders with the new detector, or **Save and render** after editing settings. The model and its license are in `assets/vision`.

Automatic highlights end at completed statements and natural pauses. Unanswered closing questions, ellipses and rushed continuations are excluded from selection. A sentence that starts within the target duration can finish up to 25% (at most 12 seconds) beyond it, with a short tail after the final word that stops before the next utterance. Clips remain capped at 180 seconds. Finding highlights again applies the new selection rules; generating from older highlights finishes a nearby answer when possible and asks for new highlights if it cannot find a safe ending. Manually chosen trims remain exact.

Captions use speech-bounded word timing shared by the editor, video renderer and clip SRT downloads. Text, backgrounds and word effects disappear during pauses of at least 250ms and restart when speech resumes. Unchanged transcript cues retain their word timestamps; edited wording is distributed over the source's spoken runs. Without a transcript, explicit cue times are used. Re-render existing videos to apply this timing.

Open a project and choose **Edit clip** (or **Create manual clip**). The composition preview shows the cropped source, captions, title, watermark and logo. Drag the source to override automatic framing, or drag captions/the logo to reposition them. Automatic static framing stays fixed within each detected source shot and switches immediately at a scene cut. Low framing scores block automatic rendering; manually inspect and correct the crop when needed. Footage without reliable face detections is explicitly unscored.

Open **Templates** for 24 creator-style, word-timed caption presets with animated previews, category/font search, and a customization workbench. Twelve speech-synchronized effects include spring, punch, rise, slide, tilt, focus, flip, elastic, highlight pill/block, underline and glow; legacy phrase effects remain available. Choose full-phrase emphasis, build-up sentences or centered single words, with adjustable active-word scale and inactive opacity. Motion follows transcript word timestamps; edited wording stays within the source's spoken runs. Long single words shrink to fit. Choose 16 bundled font families with 223 real weight/italic variants, including Medium and Black where the family supports them. Font width presets (Condensed, Normal, Wide and Extra wide) adjust letter proportions independently of caption box width. Adjust typography, colors, outline, shadow, background, placement, safe area, grouping and motion duration. The same controls are available in the clip editor and project wizard. Apply a style to existing clips without changing their transcript, then render them to update exported videos. Personal presets are saved per account in this browser; applied settings are persisted with each clip. Fonts ship with licenses in `assets/fonts/caption` and `apps/web/public/fonts/caption`; the shared catalog is `packages/shared/caption-fonts.json`. Only selected browser faces load, and the worker installs the same real faces for export. Regenerate from the pinned source lock with `python scripts/build_caption_fonts.py` (requires fonttools and brotli).

`node scripts/verify_caption_gallery.mjs` checks the gallery, customization, preset persistence and apply flow against an in-memory API on ports 3100/8101. It creates no accounts or projects in the live workspace. Screenshots and a preset manifest are written to ignored `.local/caption-collection/`.

**Render 4-second preview** uses the same FFmpeg pipeline as final output and counts toward render usage. The instant browser preview approximates animation and text wrapping; use the rendered preview to judge exact appearance. Preview clips stay out of the clip library and ZIP exports, but their stored media counts toward storage until the project is deleted.

Run `python scripts/check_editor_media.py` for all native caption animations and a deterministic hard-cut crop pixel check. Outputs are written to `.local/editor-validation/`. The editor browser test also confirms identical preview/final MP4 hashes for the same four-second composition. Synthetic face annotations test crop geometry; they do not establish real-world face-detector or active-speaker accuracy.

Local upload is available after creating a project, in **Source video → Choose source video → Upload video**. YouTube URL ingestion is not implemented; the original build specification starts with local files.

## Environment and deployment

`.env.example` is the shared environment contract for API and worker. Frontend only reads `NEXT_PUBLIC_API_URL` (browser) and `API_INTERNAL_URL` (server). No secrets belong in public variables. Set `COOKIE_SECURE=true` behind HTTPS and set `APP_URL` to the exact frontend origin. Browser mutations enforce that origin, in addition to SameSite cookies and strict CORS. Database sessions can be revoked. Password reset revokes all sessions.

Use managed PostgreSQL/Redis, private S3-compatible storage, TLS termination, backups, and dedicated worker containers for production. Never expose database, Redis or MinIO admin ports publicly. Configure storage CORS for your frontend origin. Run migrations as a single release job before rolling API/worker updates. Do not run FFmpeg inside serverless request handlers.

CPU defaults: `WORKER_DEVICE=cpu`, `WHISPER_COMPUTE_TYPE=int8`. GPU deployment needs a CUDA-compatible worker image and device access; setting `WORKER_DEVICE=cuda` alone is insufficient. Highlight scoring and preference learning run locally; the legacy `semantic_ranking` input is retained for compatibility and does not trigger cloud requests. `HIGHLIGHT_WEIGHTS` accepts seven nonnegative integer weights totaling 100.

Optional Stripe checkout, customer portal and signed subscription webhooks are implemented. Configure `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_CREATOR` and `STRIPE_PRICE_PRO` for your test account and send webhooks to `/api/v1/billing/webhook`. Live provider acceptance still requires your Stripe credentials; automated tests mock the provider. Local clipping works without billing or AI credentials, within the configured free-plan quotas.

To stop without deleting data: `docker compose down`. Local data lives in named volumes; only use `docker compose down -v` when deliberately discarding all local accounts and media.
