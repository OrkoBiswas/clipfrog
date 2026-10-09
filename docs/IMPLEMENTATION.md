# Implementation record

## Current update — October 9, 2026

The workspace now includes the creator studio redesign, upload-first setup,
bulk clip actions, 24 browser caption presets, 16 bundled font families with 223
real weight/italic variants, and automatic two-to-four-person collage framing.
Caption presets are browser-local; the previous caption-library API is removed,
and a migration clears its retired rows. Native ASS renders all supported word
and phrase effects. Legacy external animation settings normalize to Word Pop.

Multiple screens is one toggle under Layout & safe area. Preview and rendering
inspect original footage with the bundled YuNet model and reuse cached sample
results. Profile and edge-positioned faces can receive separate panels without
being rejected for a low aesthetic score. Older automatic renders regenerate
when their detector version is outdated. Single-person shots stay full screen.

The v2 collage checks suppress overlapping detections of one head and bind
panels to persistent tracks observed together. Each shot keeps its checked crops
instead of selecting people again when combining shots. A sampled head cannot
appear in multiple automatic panels, including after widening a crop. Two-person
shots try the alternate collage arrangement if needed, then fall back to single
screen when distinct, visible crops cannot be established. The version change
invalidates older detections and automatic render plans on the next render.

Caption groups and their backgrounds clear during speech pauses in the editor,
rendered video and clip SRT downloads. Automatic highlights favor completed
statements and natural pauses, with a short tail after the final word. Local
editorial scoring and preference learning replace the optional cloud review.

Latest verification: 475 Python tests and 31 frontend unit tests passed. Python
lint/type checks and frontend lint/type/build checks passed. Browser acceptance
passed all 12 scenarios, covering the real speech-to-highlight/render pipeline and automatic collage,
caption pause timing, font persistence, and regeneration of older renders. An
additional isolated project verified actual two-person footage through detection,
preview, cached analysis and Celery rendering. Its output retained audio and
duration. Real-footage verification covers these samples, not every pose or source.
Brand kits with expanded caption template names remain readable after applying
them to a project; API validation matches the caption configuration schema.
The duplicate-person fix passed the automatic collage browser render test,
duplicate-detection and fragmented-track regressions, and a real FFmpeg check
that would repeat both heads with the original stacked crop. The existing
two-person source sample still renders distinct panels with audio and duration.

API, worker and web services run in Docker at localhost:3000/8000. The records
below describe earlier milestones; this section supersedes their caption-library,
animation, cloud-review and next-step descriptions. Active-speaker inference,
YouTube ingestion, load/retention testing and production deployment acceptance
remain open.

## Earlier milestones

Interactive editor milestone (2026-10-01): fixed the static-crop bug at its source: sustained-motion corrections were being emitted in static mode. Static mode now emits one fixed crop per detected source shot; scene-boundary keyframes remain discrete cuts in the FFmpeg expression. Added robust face samples, eye-line/headroom controls, left/right/two-person selection, configurable framing-quality rejection, manual drag overrides and administrator diagnostics. Two-person quality scoring evaluates both subjects. Active-speaker inference from audio/mouth motion is not implemented; stable primary-person selection is not speaker identification.

Removed the bundled caption preset catalog and clear existing caption-library rows in a one-time migration. Per-user custom template creation, editing, deletion, favorites, recents, and defaults remain available. Word Pop and Color Reveal are the only available caption animations; legacy animation values normalize to Word Pop. Both render natively through ASS. Font/weight/spacing/colors/stroke/background opacity/position/grouping/animation settings are consumed by ASS rendering. Added licensed browser fonts, interactive source/caption/logo composition, safe-zone guides, nine logo positions, normalized drag, size/opacity/margin controls and Brand Kit integration. Short previews are real quota-accounted renders, hidden from normal clip lists/exports. The additive `fa198ac32d70` migration stores the caption library and preview flag.

Validation: 65 Python tests, four frontend unit tests and four browser E2E tests pass; Python/frontend lint and type checks pass. Rebuilt production Docker services, applied migrations and confirmed no Alembic schema drift. Readiness and the Redis/Celery/PostgreSQL/MinIO connectivity checks pass. All 25 styles rendered through FFmpeg; inspected the contact sheet and desktop/mobile editor screenshots. Pixel checks verify fixed framing across a synthetic two-shot source and immediate crop changes at the hard cut. Browser acceptance uploads real media, applies/saves styling and logo settings, renders a preview and final output, and verifies identical MP4 hashes for the same four-second composition. CI includes these media checks.

Remaining scope from the expanded brief: real multi-person/podcast acceptance footage; audiovisual active-speaker selection; richer rounded/pill/individual-word caption backgrounds, keyword styling and detailed shadow/line-height controls; exact browser/ASS layout equivalence. The browser preview is an approximation, with the FFmpeg short preview provided for exact review. YouTube ingestion, full bulk actions, intro/outro branding, load/retention and production deployment acceptance remain outside this completed editor milestone. Do not interpret synthetic crop fixtures as evidence of real face-detection accuracy or claim the whole master specification is complete.

The master specification is `CODEX_BUILD_PROMPT_VIDEO_CLIPPER_SAAS.md`.

Initial inspection: workspace contained only that specification. Architecture: npm workspace with Next.js 16 web frontend, a typed FastAPI/SQLAlchemy package, and a separately importable Celery worker. PostgreSQL owns application state; Redis carries jobs; private MinIO stores media. Session tokens are random opaque secrets stored only as hashes in PostgreSQL. The frontend never handles database credentials.

Phases are tracked here with test evidence; file creation alone does not establish completion.

- Phase 1: validated. Docker services communicate; API readiness passes all four dependency checks; a real Redis/Celery task accesses PostgreSQL and MinIO. Python lint/types and frontend lint/types/build pass.
- Phase 2: validated. Browser registration, protected dashboard, project create/reload/update/delete pass. SMTP reset integration validates delivery, session revocation and token replay rejection.
- Phase 3: validated happy path. Browser uploads a real FFmpeg-generated MP4 directly to private MinIO; Celery runs ffprobe and saves dimensions/duration/codec/checksum. Multipart resume, cancel and server part validation implemented; edge-case integration tests still being expanded.
- Phase 4: persisted job progress, retry/cancel and cleanup implemented; hardening in progress.
- Phase 5: real analysis verified through the running stack: uploaded speech video, FFmpeg proxy/audio, faster-whisper word timestamps (13 segments), PySceneDetect and MediaPipe sampling, persisted transcript and scene results. Face-free footage reports an explicit fallback warning. Broader language and face-footage coverage remains.
- Phase 6: integrated. Real uploaded speech produced 26 candidate windows and two distinct selected moments. PostgreSQL persists candidates, scores, explanations and ranks; Celery measures real audio energy and combines transcript/scene/face signals. User controls minimum score, separation, overlap and keywords. Optional cloud review is opt-in and falls back to local scoring. Multilingual quality and long-source load coverage still need expansion.
- Phase 7: crop planner and geometry implemented. Twelve tests cover ratios, bounds, jitter, outliers, persistent-face selection and hard scene cuts. Real multi-person footage and prolonged subject departures still need acceptance review.
- Phase 8: real original-source FFmpeg MP4 rendering, audio normalization, seven ASS caption presets, title/text watermark, thumbnails and private storage implemented. Tests render all eight ratios; a real 1080x1920 speech clip with visible karaoke captions was inspected. Brand logos now render in all four corners with transparency, configured caption colors, title styles and watermark positioning. Broader caption controls remain.
- Phase 9: browser clip list, playback, trim/configuration/text edits, fixed manual anchor, zoom, save/re-render and download implemented. Browser E2E now uploads, renders, plays and downloads. Live checks verify edited re-render, ZIP and SRT exports. Full bulk selection/actions and visual crop editing remain.
- Phase 10: server-side usage reservations, quota enforcement, usage/billing pages and optional Stripe service implemented. Tests cover quotas, signature tampering/expiry, replay and subscription sync with only the external payment provider mocked. Live Stripe checkout requires deployment credentials and has not been performed.
- Phase 11: hardening in progress. The full master-spec definition of done is not yet met; remaining acceptance work includes the full wizard/preset flow, broader retention/recovery, expanded real-face fixtures and final production review.

Initial resume audit (2026-10-01): no Git metadata exists in this workspace, so history/diff cannot be inspected. The audit found one Python typing error in candidate generation, stale phase documentation and job cancellation/retry state edge cases. These were corrected before further acceptance checks.

Continuation validation (2026-10-01): rebuilt the API, worker, migration and web images from the project's Dockerfiles/locks; no manual dependency patching was needed. Fixed upload status recovery when MinIO completion succeeded before the database commit, and removal of the resulting object on cancellation or expiration. Transient upload-status failures now preserve the browser's resume identifier. Failed worker messages require explicit retry instead of silently restarting after redelivery. Fixed the frontend elapsed-time render purity error and added the missing migration for the existing brand-kit model (the brand-kit feature remains unfinished).

Validation evidence: 46 Python tests and four frontend tests pass; Python/frontend lint and type checks pass; Next.js production container build passes. Two browser E2E tests pass, including actual upload, render, playback and download. A fresh speech pipeline run transcribed 13 segments, generated 26 highlight candidates with two selected, rendered a 1080x1920 MP4, verified a two-second trim on re-render and downloaded valid ZIP/SRT exports. Alembic reports no schema drift. `scripts/check_upload_recovery.py` now runs in CI against real MinIO/PostgreSQL/Celery.

Live recovery checks also passed: interrupted upload completion, cancellation and expiration; honoring a held PostgreSQL worker lock; settling cancellation after lock release; and recovery of a committed-but-undelivered job exactly once.

Brand-kit milestone (2026-10-01): completed the existing brand-kit scaffold rather than replacing it. Connected authenticated CRUD and private logo upload/preview/removal; added the dashboard management page and project application controls; implemented immutable project-owned logo/settings copies and the additive `eb024915ac38` migration. New manual and generated clips inherit branding; optional application to existing clips increments revisions while retaining caption edits. Clip editing supports logo toggling and corner positioning. Storage quotas now count kit logos as well as project assets. Caption colors previously accepted by the schema but ignored in ASS output are now rendered, with configurable title styles and watermark position. Kit platform presets select output aspect ratios; full platform constraints remain part of the wizard milestone. Optional intro/outro assets remain deferred.

Milestone evidence: 51 Python tests, four frontend unit tests, frontend/Python lint and types, Docker production build, Alembic drift check and all three browser E2E tests pass. Real FFmpeg tests verify transparent logo geometry in all four corners. `scripts/check_brands.py` verifies actual PostgreSQL/MinIO/Celery operations, rejects foreign-kit/logo access, renders a project after deleting its original kit, and exercises logo toggling/reapplication. The live service readiness and worker connectivity checks pass. Desktop/mobile screenshots were inspected; a mobile fieldset overflow found by the browser test was fixed. CI includes the real brand acceptance script before browser tests.

Next implementation work: expand the wizard/platform presets and bulk clip actions, and validate reframing with real multi-person footage. Broader media retention, load testing, live Stripe acceptance and deployment review remain open. Local core upload-to-download and reusable branding are verified; this is not a claim that every master-spec feature is complete.

Validation found and fixed: occupied PostgreSQL host port (now 55432), Windows localhost IPv6 connection stalls (explicit 127.0.0.1 for PostgreSQL), unavailable MinIO binary images (official source build), and a production wizard button reuse bug causing premature submit. The browser regression tests cover this flow.

Decision: use npm workspaces because Node/npm are installed, avoiding a mandatory extra package manager. CPU worker baseline is Python 3.12 to preserve ML package compatibility. Optional OAuth is deferred; first-party email/password authentication uses Argon2id and revocable sessions.
