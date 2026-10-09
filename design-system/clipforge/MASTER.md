# ClipForge interface system

Updated October 4, 2026. The creator-studio redesign builds on the existing ClipForge components and preserves its mint brand identity.

## Direction

A creator's studio with warm graphite surfaces, mint primary actions, locally bundled Urbanist display typography, and Inter body text. The interface follows the real video workflow: source, analysis, highlights, then clips and export. Original podcast photography grounds the dashboard, authentication, and setup screens in the product's purpose. Secondary violet and peach accents distinguish creative tools.

## Foundations

Semantic tokens live in [design-system.css](../../apps/web/src/app/design-system.css); shared studio styling and dashboard composition live in [creator-studio.css](../../apps/web/src/app/creator-studio.css).

| Role | Dark | Light |
| --- | --- | --- |
| Brand/action | `#0be881` | `#0be881` with charcoal text |
| Brand charcoal | `#1e272e` | `#1e272e` |
| Brand white | `#f5f6fa` | `#f5f6fa` |
| App background | `#101312` | `#f3f5f0` |
| Surface | `#191d1b` | `#ffffff` |
| Primary text | `#f3f5ef` | `#19271e` |
| Secondary text | `#b6c0b8` | `#516256` |
| Accent text/focus | `#0be881` | `#06743f` |

Use semantic tokens for interface colors. Caption and brand colors remain user-controlled content. Urbanist and Inter are bundled locally; existing caption fonts remain available. Spacing follows a 4px rhythm, with 16/24/32/48px hierarchy. Radius tokens range from 6px controls to 24px dialogs. Lucide is the interface icon family.

## Interaction patterns

- Persist Dark, Light, or System appearance and sidebar preference. Initialize appearance before hydration.
- Keep the desktop navigation persistent and use a modal navigation drawer on small screens. Provide command search with Ctrl/Cmd+K, accessible names, visible focus, and Escape dismissal.
- Use native dialogs for focus containment, confirmation, and editor overlays. Nested dialogs share a scroll lock and restore scrolling after the final dialog closes.
- Guide project creation through Upload, Content, Clips, Style, and Review. Retain the uploaded draft ID across steps. Allow setting up a draft before uploading.
- Present clip results with real signed media, bulk actions, and status labels. Load the full editor on demand.
- Project cards link to the appropriate next step. Project tabs support hash and query deep links plus browser history. Keep panels mounted to preserve uploads and edits; pause media when a panel becomes hidden.
- The Clips page uses the full searchable library, with grid/list views, editing, downloading, and automatic refresh during rendering.
- Keep the editor canvas and inspector together on desktop; stack them on mobile with a full-width sheet and sticky save actions. Keep sample captions collapsed inside the editor because the actual composition is already visible.
- Preserve real upload progress, processing states, validation errors, retry/cancel actions, and download links. Do not fabricate usage, notifications, testimonials, or media.
- Use brief GSAP route reveals with context cleanup and reduced-motion support. Content remains available without animation.
- Reveal page sections in a short stagger. Use responsive format transitions in the dashboard sample, finite caption entrances, and subtle card/action feedback. Label generated media as a style preview. Never imply that the sample belongs to the user's projects or represents a completed render.
- Caption Studio uses a GSAP sample player with explicit playback, scrubbing, speed/loop controls, editable timed words, aspect ratios, and safe-area guides. Keep the preview beside its controls when space permits; suspend offscreen/background playback and disable autoplay/transform animation for reduced motion. Sample timing is illustrative, and actual clip output is checked through the existing rendered preview.

## Component ownership

| Concern | Files |
| --- | --- |
| Global tokens and shell styles | `src/app/design-system.css` |
| Dialogs, confirmation, toggles, status, skeletons | `src/components/ui/primitives.tsx` |
| Appearance and feedback | `src/components/ui/theme-provider.tsx`, `toast.tsx` |
| Navigation, search, job notifications | `src/components/shell.tsx` |
| Project wizard, upload, results | `project-form.tsx`, `source-upload.tsx`, `project-experience.css` |
| Clip editor, caption library, brand kit | `clip-editor.tsx`, `caption-studio.tsx`, `brand-kits.tsx`, `studio.css` |
| Authentication, settings, usage, billing, operations | `account-pages.css` and corresponding page/components |

Paths in the table are relative to `apps/web/`. See [CODEX_PROGRESS.md](../../CODEX_PROGRESS.md) for verification and current integration limits.
