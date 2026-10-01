# Codex Build Prompt — Production SaaS AI Video Clipper

> **Project working name:** ClipForge AI  
> You may rename the product later.  
> **Goal:** Build a complete, production-oriented SaaS web application that turns long uploaded videos into multiple polished short-form clips for social media.

---

## 1. Role and Execution Instructions for Codex

Act as a **principal full-stack engineer, video-processing engineer, ML engineer, SaaS architect, product designer, DevOps engineer, and QA engineer**.

Build the application described in this document as a **working end-to-end product**, not a UI prototype.

### Non-negotiable execution rules

1. Do not stop after scaffolding.
2. Do not leave core buttons as fake/mock actions.
3. Do not use hard-coded demo responses where real processing can be implemented.
4. Build incrementally and run the app/tests after each major phase.
5. Fix TypeScript, Python, database, Docker, API, rendering, and test errors before considering a phase complete.
6. Prefer well-supported, stable libraries over experimental packages.
7. Keep external AI providers behind interfaces so providers can be changed later.
8. The core app must still work without a paid LLM API key:
   - video upload
   - transcription using local faster-whisper
   - scene detection
   - face detection
   - clip candidate generation
   - deterministic highlight scoring
   - reframing/cropping
   - caption rendering
   - export
9. If an optional cloud AI key is present, enhance highlight selection with semantic scoring.
10. Never claim a clip is guaranteed to “go viral.” Display an **AI Highlight Score** or **Engagement Potential Score** as a heuristic.
11. When a requested clip count is impossible because the source is too short, create the maximum number of high-quality non-overlapping clips and explain the limitation in the UI.
12. Use sensible defaults instead of repeatedly asking the developer questions.
13. Maintain a root `README.md` with exact local setup and production deployment instructions.
14. Maintain `.env.example` files for every required service.
15. All services must run locally with Docker Compose.

---

# 2. Product Vision

The SaaS accepts a long-form video such as:

- podcast
- interview
- talking-head video
- tutorial
- webinar
- course
- livestream recording
- business presentation
- gaming commentary
- educational content
- product demo

The user uploads the video, chooses target platforms, aspect ratios, desired clip count, preferred duration, visual/caption style, and processing mode.

The system analyzes the source and automatically produces the most useful self-contained moments as ready-to-post clips.

The user can preview, edit, regenerate, download, or export the generated clips.

---

# 3. Core User Journey

## Step 1 — Create Project

User clicks **New Project**.

Fields:

- Project name
- Video source:
  - local file upload first
  - architecture should allow URL/import providers later
- Content type:
  - Auto
  - Podcast
  - Interview
  - Talking Head
  - Tutorial
  - Webinar
  - Gaming
  - Presentation
  - Other
- Spoken language:
  - Auto detect
  - manual override

## Step 2 — Upload Video

Support:

- MP4
- MOV
- MKV
- WebM
- M4V where FFmpeg supports it

Use resumable or multipart upload for large files.

Show:

- filename
- file size
- upload progress
- upload speed if practical
- cancel upload
- retry upload
- validation errors

Do not send multi-GB files through a Next.js server action.

Use direct S3-compatible multipart upload / presigned upload.

Local development uses MinIO.

Production storage abstraction supports AWS S3 and other S3-compatible providers.

---

# 4. Clip Generation Configuration

The user must be able to configure the following before processing.

## Clip Count

Presets:

- 5
- 10
- 20
- 30
- 50
- 75
- 100

Also allow a custom number within a configurable safe maximum.

Default: 10.

If the source cannot support that many quality clips, return fewer clips and clearly show why.

## Clip Duration

Presets:

- 10 sec
- 15 sec
- 20 sec
- 25 sec
- 30 sec
- 35 sec
- 45 sec
- 60 sec
- 90 sec

Also support:

- custom exact duration
- duration range such as 20–35 sec
- Auto duration

For Auto duration, allow the algorithm to end clips on natural sentence/thought boundaries.

## Aspect Ratio

Support at minimum:

- 9:16 — TikTok, Reels, Shorts
- 16:9 — YouTube / X / landscape
- 1:1 — square
- 4:5 — Instagram/Facebook feed
- 3:4
- 4:3
- 21:9 — optional cinematic export
- Original

Allow one project to generate multiple ratios.

## Export Resolution Presets

Examples:

- 1080 × 1920 for 9:16
- 1920 × 1080 for 16:9
- 1080 × 1080 for 1:1
- 1080 × 1350 for 4:5

Allow configurable quality:

- Draft
- Standard
- High

Default final encode:

- container: MP4
- video: H.264
- audio: AAC
- pixel format: yuv420p
- fast-start enabled for web playback

Keep the encoding layer abstract enough to add HEVC/AV1 later.

---

# 5. Social Platform Presets

Add a platform selector:

- YouTube Shorts
- TikTok
- Instagram Reels
- Instagram Feed
- Facebook Reels
- Facebook Feed
- X
- LinkedIn
- YouTube Landscape
- Custom

A preset defines:

- preferred aspect ratio
- resolution
- safe caption region
- title safe area
- default max duration
- caption font sizing
- recommended padding
- default export settings

Do not hard-code business rules deep inside components. Put presets in a reusable configuration module/table.

---

# 6. Important-Moment / Highlight Detection

This is one of the most important features.

The application must not simply split a source into equal pieces.

It must find clip candidates that are:

- understandable without excessive previous context
- complete ideas
- useful
- surprising
- educational
- emotionally strong
- opinionated where appropriate
- story-like
- question-and-answer moments
- memorable quotes
- actionable tips
- strong hooks
- concise explanations
- high-energy moments
- topic transitions with standalone value

## Analysis inputs

Use a combination of:

1. transcript with word timestamps
2. sentence/paragraph boundaries
3. voice activity
4. pauses/silence
5. scene changes
6. speech density
7. audio emphasis/energy
8. face presence
9. visual stability
10. semantic importance
11. repeated-topic suppression
12. optional user keywords/topics

## Candidate generation

Generate many candidate windows, then score and rank them.

Candidate boundaries should prefer:

- sentence starts
- natural pauses
- scene boundaries
- completed ideas

Avoid:

- clipping the first/last word
- beginning with meaningless filler when possible
- ending before the point is completed
- excessive overlap between selected clips

## Suggested deterministic score

Create an explainable score, for example:

- Hook strength: 0–25
- Standalone completeness: 0–20
- Information/insight value: 0–20
- Speech/audio emphasis: 0–10
- Visual quality/face presence: 0–10
- Novelty vs already-selected clips: 0–10
- Clean boundaries: 0–5

Total: 0–100.

These weights should live in configuration and be tunable.

## Optional AI semantic ranker

Create an interface such as:

```python
class HighlightRanker(Protocol):
    def score_candidates(self, transcript, candidates, context) -> list[CandidateScore]:
        ...
```

Implement:

- `HeuristicHighlightRanker`
- one optional cloud LLM implementation controlled by environment variables

Do not tightly couple the pipeline to one vendor.

The AI scorer should return structured JSON with:

- score
- hook_score
- context_score
- insight_score
- emotional_score
- reason
- suggested_title
- suggested_hook_text
- tags

Validate the response strictly.

If the AI provider fails, automatically continue with heuristic scoring.

## Diversity

When selecting 10–100 clips:

- penalize duplicate transcript segments
- prevent near-identical ideas from filling the output
- enforce configurable minimum time separation where useful
- use transcript embeddings if available, otherwise lexical similarity

---

# 7. Podcast Mode — Static Subject Lock

This behavior is critical.

When **Podcast Mode** is enabled and the output is portrait/square, keep the principal speaker naturally around the middle of the output.

The result must **NOT constantly pan left and right following tiny head movement**.

## Required behavior

Implement a crop planner that supports:

1. `STATIC_SUBJECT_LOCK` — default for podcast
2. `SCENE_AWARE_LOCK`
3. `ACTIVE_SPEAKER_SWITCH` — optional advanced mode

### STATIC_SUBJECT_LOCK algorithm

For each output clip:

1. Sample source frames at a reasonable analysis FPS, for example 3–5 FPS.
2. Detect faces.
3. Track the most persistent primary face.
4. Collect the face center and bounding box over the clip.
5. Reject low-confidence outliers.
6. Calculate a robust median subject center.
7. Calculate headroom from face landmarks/bounding box.
8. Create **one stable crop anchor** for the shot/clip.
9. Clamp crop coordinates inside source bounds.
10. Keep eyes/head within a visually natural zone.
11. Only change anchor if:
   - a hard scene cut occurs
   - the speaker changes clearly
   - the primary face disappears for a sustained period
   - the subject exits a large dead-zone

### Anti-jitter rules

Implement:

- median filtering
- exponential smoothing where needed
- dead-zone around the current anchor
- minimum hold duration
- maximum movement speed
- minimum movement threshold

For normal podcast footage, the crop should look like an editor selected the correct fixed framing rather than an automated virtual camera chasing the head.

### Multiple people

When multiple people are visible:

- score persistence
- face size
- screen occupancy
- centrality
- optional speaking correlation

In static podcast mode, prefer stable framing.

In active-speaker mode, switches should happen at:

- sentence boundaries
- pauses
- scene changes

Never switch several times per second.

### Face missing fallback

If a face disappears:

1. retain previous stable anchor briefly
2. fall back to last reliable subject location
3. then fall back to geometric center

Never produce invalid crop coordinates.

---

# 8. Face and Subject Analysis

Primary option:

- MediaPipe Face Detector / Face Landmarker

Wrap face analysis behind an interface so a different detector can be substituted later.

Persist only derived metadata needed for processing unless the user explicitly enables deeper analysis.

Example frame result:

```json
{
  "timestamp_ms": 12340,
  "faces": [
    {
      "confidence": 0.97,
      "x": 0.31,
      "y": 0.14,
      "w": 0.22,
      "h": 0.37,
      "center_x": 0.42,
      "center_y": 0.325
    }
  ]
}
```

Use normalized values in stored analysis metadata.

---

# 9. Transcription

Use **faster-whisper** locally.

Requirements:

- word timestamps
- language detection
- VAD
- segment timestamps
- punctuation where available
- support multilingual sources

Create a transcription provider abstraction.

Store:

- transcript segments
- start/end times
- words and timestamps
- detected language
- confidence where exposed

Provide export:

- TXT
- SRT
- VTT
- JSON

---

# 10. Scene Detection

Use **PySceneDetect** as the first implementation.

Detect:

- hard cuts
- adaptive scene changes

Persist scene ranges.

Do not force every scene boundary to become a clip boundary; use scene data as one signal.

---

# 11. FFmpeg Rendering Pipeline

Use FFmpeg/ffprobe for media metadata and rendering.

The pipeline must support:

- accurate trim
- crop
- scale
- pad where required
- frame-rate handling
- audio normalization
- caption overlay
- title/hook overlay
- watermark/logo
- safe margins
- thumbnails
- waveform optional
- multiple aspect ratios

Avoid unnecessary generations.

Suggested architecture:

- analysis proxy for ML processing
- final render directly from the original source where possible

Use deterministic temporary working directories per job.

Clean temporary files after job completion or failure.

---

# 12. Caption System

Auto captions must be a first-class feature.

## Caption styles

Provide at least:

- Clean
- Bold
- Minimal
- Karaoke
- Creator
- Podcast
- High Contrast

## Options

- captions on/off
- sentence captions
- word-by-word highlighting
- max words per line
- 1 or 2 lines
- font family
- font weight
- text size
- text alignment
- screen position
- background box
- shadow
- outline
- highlight current word
- uppercase toggle
- punctuation toggle
- safe-zone positioning

Use subtitle safe zones so TikTok/Reels UI controls do not cover critical captions.

Use configurable fonts that are legal to bundle or require user-uploaded licensed fonts.

Do not bundle proprietary fonts without permission.

---

# 13. Hook / Title Overlay

Optional text at the top of the clip.

Modes:

- Off
- Auto-generate
- Custom text

Allow user to edit.

Examples of generated intent:

- summarize the most interesting point
- ask a short question
- expose the result
- frame the insight

Keep overlays concise.

Do not generate misleading clickbait that contradicts the source.

---

# 14. Smart Cleanup Options

Add configurable switches:

- remove long silences
- trim dead air at start/end
- reduce filler words when technically safe
- normalize loudness
- basic noise reduction
- auto captions
- auto hook
- face-centered reframe
- remove duplicate clips
- prefer complete sentences
- profanity masking optional
- add fade in/out optional
- smart zoom optional, OFF by default

Smart zoom must never be used as a substitute for stable podcast framing.

---

# 15. Brand Kit

User can create a reusable brand kit:

- logo
- watermark position
- primary brand color
- secondary color
- caption style
- default font
- hook/title style
- default intro/outro optional
- preferred platform presets

Apply a brand kit at project level.

---

# 16. Clip Editor

After generation, provide a lightweight browser editor.

Do not attempt to clone Premiere Pro.

Required editor functionality:

- video preview
- trim start
- trim end
- edit clip title
- edit hook
- edit transcript/captions
- caption style
- caption position
- aspect-ratio switch
- reframe anchor manually
- zoom amount
- watermark/logo toggle
- regenerate crop plan
- regenerate captions
- regenerate title
- save draft
- render updated version

Timeline can be simple but professional.

Show transcript alongside the video and allow clicking transcript segments to seek.

---

# 17. Clip Result Card

Each generated clip should show:

- thumbnail
- title
- duration
- source timestamp
- aspect ratio
- AI Highlight Score
- score explanation
- transcript excerpt
- processing status
- preview
- edit
- download
- duplicate
- regenerate
- delete
- select checkbox

Bulk actions:

- download selected
- render selected
- delete selected
- change ratio
- apply brand kit

Support ZIP download for multiple completed clips.

---

# 18. Professional SaaS Dashboard UX

Create a polished professional dashboard.

## Visual style

- modern
- clean
- premium
- subtle motion
- spacious
- strong typography
- responsive
- accessible
- dark and light modes

Avoid excessive gradients and visual clutter.

## Main navigation

Sidebar:

- Dashboard
- New Project
- Projects
- Clips
- Brand Kit
- Usage
- Billing
- Settings

User section:

- account
- plan
- sign out

## Dashboard page

Show:

- New Project CTA
- recent projects
- total videos
- clips created
- minutes processed
- storage used
- processing jobs
- usage allowance
- recent exports

## Project page

Sections:

- Overview
- Source
- Transcript
- Highlights
- Generated Clips
- Settings
- Activity

## Processing UI

Display detailed stages:

1. Upload complete
2. Reading media
3. Extracting audio
4. Transcribing
5. Detecting scenes
6. Detecting faces
7. Finding highlights
8. Planning crops
9. Rendering clips
10. Finalizing

Show:

- overall progress percentage
- current stage
- stage progress
- elapsed time
- error state
- retry action
- cancel action

Use Server-Sent Events or a reliable polling fallback for live progress.

---

# 19. Authentication

Implement production-ready authentication.

Minimum:

- email/password
- email verification architecture
- forgot/reset password
- secure session cookies
- Google OAuth optional if environment variables are present

Recommended approach:

- Auth.js/latest compatible stable authentication for Next.js
- persist users/sessions/accounts in PostgreSQL

If using passwords directly, use Argon2id.

Do not store plaintext passwords.

Add middleware/protection for app routes.

---

# 20. SaaS Billing and Usage

Integrate Stripe Billing behind a service abstraction.

Plans example:

## Free / Trial

- limited source minutes
- limited exports
- watermark optional
- lower max resolution if desired

## Creator

- increased monthly processing minutes
- HD export
- more storage
- brand kit

## Pro

- more monthly processing minutes
- batch clip generation
- priority processing
- multiple brand kits
- high limits

## Team later

Architecture should support organization/team ownership later even if v1 is single-user.

Track usage by:

- input video minutes processed
- export/render minutes
- storage bytes
- optional AI tokens/cost metadata

Use Stripe webhooks to sync subscriptions.

Never trust only client-side plan state.

Implement quotas server-side.

---

# 21. Technology Stack

Use this baseline unless a strong compatibility reason requires a small adjustment.

## Monorepo

Use a clear monorepo structure.

Recommended:

```text
clipforge/
  apps/
    web/
    api/
  workers/
    media/
  packages/
    shared/
    config/
  infra/
  scripts/
  docs/
  docker-compose.yml
  .env.example
  README.md
```

## Frontend

- Next.js 16.x, patched current stable/LTS
- React
- TypeScript strict mode
- Tailwind CSS
- shadcn/ui or equivalent accessible component primitives
- TanStack Query for server-state where useful
- React Hook Form
- Zod
- accessible charts only where useful

## Backend API

- Python 3.12+ compatible
- FastAPI
- Pydantic
- SQLAlchemy 2.x
- Alembic
- PostgreSQL

Use async database access where it improves API throughput, but do not make media workers depend on async complexity unnecessarily.

## Database

- PostgreSQL 18.x current supported minor for development image if compatible

## Queue / jobs

- Celery
- Redis

Create separate queues if needed:

- `analysis`
- `render`
- `maintenance`

Support concurrency configuration by environment.

## Cache / broker

- Redis

## Object storage

Local:

- MinIO

Production:

- S3-compatible storage

## Video / ML

- FFmpeg
- ffprobe
- PyAV where useful
- OpenCV where useful
- PySceneDetect
- faster-whisper
- MediaPipe Face Detector / Face Landmarker

## Billing

- Stripe

## Observability

Architecture for:

- structured logs
- request IDs
- job IDs
- health endpoints
- optional Sentry
- optional OpenTelemetry

---

# 22. Current Version Baseline

At the time this specification was prepared (2026-10-01), use patched stable/current-compatible releases rather than old tutorials.

Known useful baselines:

- Next.js 16.3.8 Active LTS or newer patched compatible release
- FastAPI 0.141.x or newer compatible stable release
- PostgreSQL 18.6 or newer supported 18.x minor
- Redis 8.10.x or an appropriate supported/LTS Redis 8.x release
- faster-whisper 1.2.1 or newer compatible stable release
- PySceneDetect 0.7.1 or newer compatible stable release

Do not blindly pin an insecure older patch.

---

# 23. Database Model

Use UUID primary keys unless there is a strong reason otherwise.

Core entities:

## User

- id
- email
- name
- password_hash nullable for OAuth
- avatar_url
- created_at
- updated_at

## Subscription

- id
- user_id
- provider
- customer_id
- subscription_id
- price_id
- status
- current_period_start
- current_period_end
- cancel_at_period_end

## UsageLedger

- id
- user_id
- project_id nullable
- metric
- quantity
- unit
- metadata
- created_at

## Project

- id
- user_id
- name
- content_type
- language
- status
- source_asset_id
- processing_config JSONB
- created_at
- updated_at

## MediaAsset

- id
- user_id
- project_id nullable
- type
- storage_key
- original_filename
- mime_type
- size_bytes
- width
- height
- duration_ms
- fps
- codec
- checksum
- created_at

## Transcript

- id
- project_id
- language
- full_text
- segments JSONB or normalized child table
- provider
- created_at

For scale, consider normalized transcript words/segments later; v1 may store chunked JSONB if query patterns remain simple.

## Scene

- id
- project_id
- start_ms
- end_ms
- confidence
- metadata

## AnalysisFrame / FaceTrack

Do not store every raw video frame.

Store compact derived analysis:

- project/clip
- time range
- face track id
- bounding-box summaries
- stable centers
- confidence

## ClipCandidate

- id
- project_id
- start_ms
- end_ms
- transcript_excerpt
- score_total
- score_breakdown JSONB
- reason
- rank
- metadata

## Clip

- id
- project_id
- candidate_id nullable
- title
- start_ms
- end_ms
- aspect_ratio
- status
- highlight_score
- crop_plan JSONB
- caption_config JSONB
- overlay_config JSONB
- render_config JSONB
- output_asset_id nullable
- thumbnail_asset_id nullable
- created_at
- updated_at

## ProcessingJob

- id
- user_id
- project_id
- clip_id nullable
- job_type
- queue
- status
- progress
- stage
- error_code
- error_message
- attempts
- started_at
- finished_at
- created_at

## BrandKit

- id
- user_id
- name
- logo_asset_id
- config JSONB
- created_at
- updated_at

---

# 24. API Design

Use versioned endpoints.

Example:

```text
/api/v1/health
/api/v1/me

/api/v1/projects
/api/v1/projects/{project_id}
/api/v1/projects/{project_id}/upload/initiate
/api/v1/projects/{project_id}/upload/complete
/api/v1/projects/{project_id}/analyze
/api/v1/projects/{project_id}/transcript
/api/v1/projects/{project_id}/candidates
/api/v1/projects/{project_id}/generate-clips
/api/v1/projects/{project_id}/jobs
/api/v1/projects/{project_id}/events

/api/v1/clips
/api/v1/clips/{clip_id}
/api/v1/clips/{clip_id}/render
/api/v1/clips/{clip_id}/download
/api/v1/clips/{clip_id}/thumbnail

/api/v1/brand-kits

/api/v1/usage
/api/v1/billing/checkout
/api/v1/billing/portal
/api/v1/billing/webhook
```

Apply authorization checks to every user-owned object.

Never accept a storage key from the client and blindly trust it.

---

# 25. Processing State Machine

Project states:

```text
DRAFT
UPLOADING
UPLOADED
QUEUED
ANALYZING
READY_FOR_CLIPS
GENERATING
COMPLETED
FAILED
CANCELED
```

Job states:

```text
PENDING
QUEUED
RUNNING
SUCCEEDED
FAILED
CANCELED
RETRYING
```

Make jobs idempotent where practical.

A retry must not create duplicate media assets or double-charge usage.

---

# 26. Detailed Media Pipeline

Implement a pipeline roughly like this:

## A. Probe

Run ffprobe:

- duration
- dimensions
- streams
- frame rate
- codecs
- audio channels
- sample rate

Reject invalid/corrupt files cleanly.

## B. Create analysis proxy

Create a lower-resolution proxy if source is large.

Use the proxy for:

- face analysis
- scene analysis
- preview

Use original source for final render.

## C. Extract audio

Create suitable mono/16 kHz analysis audio as needed by speech models.

## D. Transcribe

Run faster-whisper with:

- word timestamps
- VAD
- language auto-detection

## E. Scene detection

Run PySceneDetect.

## F. Face analysis

Analyze sampled frames.

Create stable face tracks and a compact crop-planning dataset.

## G. Candidate creation

Use transcript, silence, scenes, and duration constraints to create candidate ranges.

## H. Candidate scoring

Run heuristic ranker.

If configured, merge/augment with semantic AI ranker.

## I. Candidate selection

Choose requested count while enforcing:

- minimum score
- overlap threshold
- diversity
- valid duration
- natural boundaries

## J. Crop planning

For each clip/ratio:

- compute crop dimensions
- compute stable anchor
- headroom
- clamp
- generate crop plan

## K. Caption layout

Generate caption cues and style metadata.

## L. Render

FFmpeg creates final output.

## M. Thumbnail

Choose a representative high-quality frame with visible face where possible.

## N. Finalization

- upload to object storage
- update database
- update usage
- clean temporary files

---

# 27. Crop Math

Implement crop calculations in a tested pure-Python module.

Example output-ratio logic:

For source size `(W, H)` and target ratio `(rw, rh)`:

- target aspect = `rw / rh`
- source aspect = `W / H`

If source is wider than target:

- crop height = H
- crop width = H * target aspect

Else:

- crop width = W
- crop height = W / target aspect

Center the crop around the planned subject center.

Clamp:

```text
x = max(0, min(x, W - crop_width))
y = max(0, min(y, H - crop_height))
```

Round to encoder-compatible even pixel sizes.

Add unit tests for:

- landscape to portrait
- portrait to landscape
- square
- face at left edge
- face at right edge
- face at top
- missing face
- multiple face tracks
- source smaller than desired output
- odd source dimensions

---

# 28. Caption Rendering Strategy

Prefer rendering subtitles in a way that remains deterministic in worker containers.

Possible approach:

1. generate ASS subtitles for advanced styling
2. render with FFmpeg/libass

Keep original SRT/VTT separately for download.

Sanitize user caption text and file paths.

---

# 29. Usage and Cost Protection

Before queueing processing:

- validate account quota
- estimate source minutes
- verify upload ownership
- ensure subscription allows the requested resolution/count

Reserve usage before expensive work where appropriate.

On job failure, reconcile reservation correctly.

Add application-level limits:

- maximum source duration per plan
- maximum file size
- maximum concurrent jobs
- maximum clip count
- maximum render resolution

---

# 30. Security

Implement:

- secure cookies
- CSRF-safe auth flow
- strict CORS
- ownership checks
- signed upload/download URLs
- MIME and extension validation
- ffprobe validation
- file-size limit
- rate limiting
- webhook signature verification
- secret management
- no secrets in frontend bundles
- no shell interpolation of user-controlled filenames
- safe subprocess argument arrays
- temporary-directory isolation
- cleanup
- database constraints
- audit-friendly logs

Never build FFmpeg commands by concatenating raw user input into a shell string.

Use subprocess argument arrays.

---

# 31. Privacy and Data Retention

Provide settings for:

- delete project
- delete source
- delete generated clips
- retention policy architecture

Deleting a project must clean associated object-storage assets safely.

Use background cleanup jobs.

Do not silently retain deleted user video indefinitely.

---

# 32. Error Handling

Create user-friendly error categories:

- upload failed
- unsupported codec
- corrupt video
- no audio
- transcription failed
- no speech detected
- no face detected
- render failed
- storage failed
- quota exceeded
- billing restriction
- provider unavailable

If face detection fails, clip generation should still be possible using center crop/letterbox depending on selected fallback.

If transcription fails, allow manual rough splitting as a fallback instead of making the entire project unusable.

---

# 33. Admin / Operations

Create a protected admin section or at minimum admin API architecture.

Useful operational views:

- users
- subscriptions
- usage
- active jobs
- failed jobs
- worker status
- storage usage
- processing duration
- retries

Never expose it to normal users.

---

# 34. Local Development

The project must start locally using something close to:

```bash
cp .env.example .env
docker compose up -d postgres redis minio
pnpm install
pnpm dev
```

And a documented way to run:

- API
- worker
- web

Also provide a full Docker Compose mode.

Services should include:

- web
- api
- worker
- postgres
- redis
- minio

Optional:

- mail testing service
- monitoring tools

Provide health checks.

---

# 35. GPU Support

The product must work on CPU for development.

For production, faster-whisper/media analysis should optionally use NVIDIA GPU when available.

Detect worker capability via environment variables.

Example:

```env
WORKER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

GPU example:

```env
WORKER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

Do not make the web/API container require CUDA.

---

# 36. Environment Variables

Create documented `.env.example`.

Example categories:

```env
APP_URL=
API_URL=
NEXT_PUBLIC_API_URL=

DATABASE_URL=
REDIS_URL=

S3_ENDPOINT=
S3_REGION=
S3_BUCKET=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
S3_FORCE_PATH_STYLE=

AUTH_SECRET=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_CREATOR=
STRIPE_PRICE_PRO=

AI_PROVIDER=
AI_API_KEY=
AI_MODEL=

WORKER_DEVICE=
WHISPER_MODEL=
WHISPER_COMPUTE_TYPE=

MAX_UPLOAD_BYTES=
MAX_SOURCE_DURATION_MINUTES=
DEFAULT_CLIP_LIMIT=
```

Never commit real secrets.

---

# 37. Testing

Testing is mandatory.

## Frontend

- component tests for important forms
- validation tests
- core dashboard behavior
- clip configuration

## Backend

- auth/authorization tests
- project CRUD
- quota tests
- upload completion validation
- API schema tests

## Media worker unit tests

Test:

- time-range selection
- clip overlap logic
- score ranking
- duration rules
- crop math
- crop clamping
- static subject lock
- multi-face selection
- missing-face fallback
- caption cue generation

## Integration tests

Generate tiny synthetic media fixtures with FFmpeg.

Test:

- ffprobe
- trim
- crop/scale
- output creation
- audio preservation
- subtitle burn-in

Do not require a massive real video fixture in the repository.

## End-to-end

At least one happy path:

1. sign in
2. create project
3. upload a small fixture
4. process
5. generate clips
6. preview
7. render
8. download

Mock only unavoidable external payment/OAuth providers in automated tests.

---

# 38. CI

Create GitHub Actions CI:

- frontend lint
- typecheck
- frontend tests
- Python lint
- Python type checks where practical
- Python tests
- build containers
- migration check

Optionally run media integration tests in a container with FFmpeg.

---

# 39. Code Quality

Frontend:

- TypeScript strict
- no pervasive `any`
- server/client boundaries understood
- typed API client

Backend:

- type hints
- service/repository boundaries where useful
- avoid giant route files
- avoid giant worker function
- clear domain models
- explicit exception mapping

Media:

- separate:
  - probing
  - transcription
  - scenes
  - face analysis
  - highlights
  - crop planning
  - captions
  - rendering

Do not put the entire media pipeline in one 1,000-line file.

---

# 40. Suggested Worker Package Layout

```text
workers/media/
  app/
    config.py
    celery_app.py
    jobs/
      analyze_project.py
      render_clip.py
      cleanup.py
    media/
      probe.py
      proxy.py
      audio.py
      ffmpeg.py
    transcription/
      base.py
      faster_whisper_provider.py
    scenes/
      detector.py
    vision/
      face_detector.py
      face_tracking.py
    highlights/
      models.py
      candidates.py
      heuristic_ranker.py
      ai_ranker.py
      selector.py
    reframing/
      geometry.py
      subject_lock.py
      crop_planner.py
    captions/
      cues.py
      ass_renderer.py
    storage/
      s3.py
    tests/
```

---

# 41. Frontend Pages

Build:

```text
/
 /login
 /register
 /forgot-password

 /dashboard
 /projects
 /projects/new
 /projects/[id]
 /projects/[id]/editor/[clipId]
 /clips
 /brand-kit
 /usage
 /billing
 /settings
```

Optional marketing pages:

```text
/pricing
/features
/privacy
/terms
```

---

# 42. New Project Wizard UX

A polished multi-step wizard:

## 1. Upload

Dropzone and upload.

## 2. Content

Select Podcast / Interview / etc.

## 3. Output

- clip count
- duration
- ratios
- platforms

## 4. Style

- captions
- hook
- brand kit
- face centering
- cleanup

## 5. Review

Show processing summary and estimated usage.

CTA:

**Generate Clips**

---

# 43. Advanced Configuration

Put advanced options behind an expandable panel.

Options:

- minimum highlight score
- max overlap percentage
- minimum separation
- detection sampling FPS
- podcast crop mode
- headroom
- crop dead-zone
- silence trim threshold
- audio loudness target
- caption max words
- source language
- AI ranking on/off
- custom topic keywords
- words/topics to avoid
- include/exclude source time ranges

Do not overwhelm normal users with these by default.

---

# 44. Accessibility

Meet sensible WCAG AA practices:

- keyboard navigation
- labels
- visible focus
- color contrast
- reduced motion support
- accessible progress/status
- captions for video content
- no information conveyed by color alone

---

# 45. Performance

Frontend:

- lazy-load heavy editor pieces
- do not load large video blobs into JS memory unnecessarily
- signed streaming URLs
- optimized thumbnails

Backend:

- API must not block on video processing
- expensive work must be queue jobs

Worker:

- bounded concurrency
- memory-aware processing
- process proxy for analysis
- stream large files where possible
- clean intermediate files

---

# 46. Observability

Every processing request should have:

- request ID
- project ID
- job ID
- user ID where safe
- stage
- duration
- error code

Use structured logs.

Add:

```text
GET /health
GET /ready
```

Worker heartbeat/status should be visible operationally.

---

# 47. Production Deployment

Provide production deployment documentation.

Recommended split:

- frontend: container or compatible Next.js hosting
- API: container
- workers: CPU/GPU containers
- managed PostgreSQL
- managed Redis
- S3-compatible object storage
- CDN for generated clips where appropriate

Do not run expensive FFmpeg jobs in serverless request functions.

Provide:

- Dockerfiles
- production Compose for reference
- reverse-proxy notes
- migration command
- worker scaling notes
- GPU worker notes

---

# 48. MVP Definition

The MVP is only complete when this exact flow works:

1. User registers/signs in.
2. User creates a project.
3. User uploads a real MP4.
4. Upload is stored in MinIO locally.
5. API records media metadata.
6. Worker transcribes the source.
7. Worker detects scenes.
8. Worker performs sampled face analysis.
9. Worker creates and scores highlight candidates.
10. User requests 10 clips of 20–35 seconds.
11. System selects high-quality candidates.
12. User selects 9:16.
13. Podcast mode calculates stable subject-centered crops.
14. System renders actual MP4 clips.
15. Captions are actually burned into output.
16. User previews results in dashboard.
17. User edits a clip title/caption/crop anchor.
18. User re-renders the clip.
19. User downloads the final MP4.
20. Failed jobs are visible and retryable.

Do not mark the MVP complete if any of these are only mocked.

---

# 49. Acceptance Criteria for Podcast Centering

Create automated tests using synthetic face-track coordinates.

The stable subject lock passes when:

- small head movement does not change crop anchor every frame
- median face center is close to target framing
- outlier detections do not cause large jumps
- crop remains inside frame bounds
- scene changes allow a new anchor
- a sustained speaker change can create a new anchor
- missing detections do not crash
- fallback crop is valid
- movement is much less jittery than raw face-center tracking

Also include a debug visualization mode that can output:

- detected face boxes
- selected primary face
- crop rectangle
- stable anchor

This is developer-only and off in production by default.

---

# 50. Acceptance Criteria for Highlight Selection

Using transcript fixtures:

- strongest complete ideas score higher than filler
- candidates respect requested duration
- sentence boundaries are preferred
- selected clips are not mostly duplicates
- overlap limit is enforced
- count limit is enforced
- short source returns fewer clips gracefully
- AI-provider failure falls back to heuristic ranker
- selection is deterministic when AI is disabled

---

# 51. Acceptance Criteria for Rendering

For each supported ratio:

- valid playable MP4
- correct target dimensions
- audio present
- crop in bounds
- duration close to requested interval
- subtitles visible when enabled
- no subtitle when disabled
- logo placement respected
- fast-start enabled
- thumbnail produced

---

# 52. Development Order

Execute in these phases.

## Phase 1 — Repository foundation

- monorepo
- Next.js
- FastAPI
- PostgreSQL
- Redis
- MinIO
- Docker Compose
- lint/test setup

## Phase 2 — Auth and dashboard

- authentication
- protected routes
- professional dashboard
- project CRUD

## Phase 3 — Upload

- multipart/presigned upload
- media asset model
- ffprobe validation

## Phase 4 — Worker foundation

- Celery
- progress events
- job model
- retries/cancel

## Phase 5 — Analysis pipeline

- proxy
- audio
- transcription
- scenes
- face analysis

## Phase 6 — Highlight engine

- candidates
- heuristic scoring
- diversity selection
- optional AI scorer

## Phase 7 — Reframing

- ratios
- crop math
- static podcast subject lock
- tests

## Phase 8 — Rendering

- FFmpeg trim
- crop/scale
- captions
- thumbnail
- storage output

## Phase 9 — Results and editor

- clip list
- preview
- score explanation
- editor
- re-render

## Phase 10 — SaaS layer

- usage metering
- quotas
- Stripe
- billing page

## Phase 11 — Hardening

- security
- cleanup
- observability
- E2E
- CI
- docs

At the end of every phase:

1. run tests
2. run type checking
3. run lint
4. run relevant containers
5. fix errors
6. update README

---

# 53. Codex Working Method

Before large edits:

1. inspect existing repository
2. summarize current architecture in your working notes
3. identify the smallest safe implementation step
4. implement
5. run commands/tests
6. inspect failures
7. fix failures
8. continue

When creating files, use production-quality naming.

When making a design choice not covered here, choose the option that:

1. keeps video processing reliable
2. minimizes user-visible latency
3. prevents data loss
4. stays maintainable
5. avoids unnecessary vendor lock-in

---

# 54. Do Not Do These

Do not:

- build only a landing page
- build a fake dashboard
- store uploaded video in PostgreSQL
- process large video inside Next.js
- process video synchronously during an HTTP request
- hard-code one aspect ratio
- crop every portrait clip at geometric center when a face exists
- move crop every single frame based directly on face x/y
- return equal time chunks and call them AI highlights
- require a paid AI API for the core product to work
- expose object storage publicly by default
- trust client-supplied ownership IDs
- concatenate user filenames into shell commands
- permanently keep all temp files
- claim engagement/viral outcome is guaranteed

---

# 55. Nice-to-Have Features After Core Completion

Only implement these after the full core path works:

- YouTube URL import where legally/technically appropriate
- Google Drive/Dropbox import
- automatic speaker labels
- multi-camera podcast layouts
- side-by-side two-speaker layout
- automatic B-roll suggestions
- stock media integration
- music bed
- brand templates marketplace
- direct social publishing
- team workspaces
- comments/approval
- webhook API
- public developer API
- batch uploads
- auto content calendar
- clip performance analytics
- AI title/description/hashtags per platform
- thumbnail editor
- translation and dubbed captions
- separate language subtitle tracks

---

# 56. Final Deliverables

The repository must contain:

- fully working frontend
- fully working backend
- working media worker
- database migrations
- Dockerfiles
- Docker Compose
- object storage integration
- Redis jobs
- transcription pipeline
- scene detection
- face detection
- stable podcast crop planner
- highlight engine
- caption engine
- actual FFmpeg rendering
- downloadable clips
- auth
- quota architecture
- Stripe integration
- tests
- CI
- `.env.example`
- seed/dev utilities
- README
- production deployment notes

---

# 57. README Quick Start Must Be Copy/Paste Friendly

The generated README should clearly include:

```bash
git clone ...
cd clipforge
cp .env.example .env
docker compose up -d
```

Then any migration/setup commands.

Document:

- prerequisites
- CPU mode
- optional NVIDIA GPU mode
- MinIO credentials/bucket setup
- Stripe test mode
- optional AI provider key
- common FFmpeg problems
- common worker problems
- how to inspect job logs
- how to reset local data

---

# 58. Definition of Done

This project is done only when a developer can clone it on a clean machine with Docker, follow the README, upload a real video, generate real highlight clips, get stable podcast reframing, burn captions, preview the clips, edit one, re-render it, and download a playable final MP4.

Start building the repository now.

Do not return only architecture prose.

Create and edit the actual project files, run the application/tests, and keep going through the implementation phases until the repository satisfies the MVP acceptance criteria.
