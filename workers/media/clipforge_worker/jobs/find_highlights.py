from pathlib import Path
from tempfile import TemporaryDirectory

from clipforge_api.config import settings
from clipforge_api.db import SessionLocal
from clipforge_api.models import (
    Analysis,
    ClipCandidate,
    MediaAsset,
    ProcessingJob,
    Project,
    Scene,
    Transcript,
)
from clipforge_api.schemas import ProcessingConfig
from clipforge_api.storage import s3
from sqlalchemy import delete, select

from clipforge_worker.celery_app import celery
from clipforge_worker.highlights.ai_ranker import OptionalCloudRanker
from clipforge_worker.highlights.candidates import create_candidates
from clipforge_worker.highlights.heuristic_ranker import HeuristicHighlightRanker
from clipforge_worker.highlights.selector import select_candidates
from clipforge_worker.highlights.signals import audio_energy, enrich
from clipforge_worker.jobs.runtime import run_job, succeed
from clipforge_worker.media.proxy import extract_audio
from clipforge_worker.transcription.base import Segment
from clipforge_worker.vision.face_detector import FaceFrame


@celery.task(name="clipforge.highlights", soft_time_limit=3600, time_limit=3700)
def find_highlights(job_id: str) -> None:
    with run_job(job_id, "FINDING_HIGHLIGHTS") as context:
        if context is None:
            return
        with SessionLocal() as db:
            job = db.get(ProcessingJob, context.id)
            assert job
            project = db.get(Project, job.project_id)
            assert project and project.source_asset_id
            asset = db.get(MediaAsset, project.source_asset_id)
            transcript = db.scalar(select(Transcript).where(Transcript.project_id == project.id))
            analysis = db.scalar(select(Analysis).where(Analysis.project_id == project.id))
            assert asset and asset.duration_ms and transcript
            config = ProcessingConfig.model_validate(project.processing_config)
            project_id, key, duration = project.id, asset.storage_key, asset.duration_ms / 1000
            segments = [Segment.model_validate(s) for s in transcript.segments]
            frames = [FaceFrame.model_validate(f) for f in analysis.face_frames] if analysis else []
            cuts = [
                s.start_ms / 1000
                for s in db.scalars(select(Scene).where(Scene.project_id == project.id))
            ]
        context.progress("Finding complete ideas", 10)
        candidates = create_candidates(segments, config.duration_min, config.duration_max, duration)
        with TemporaryDirectory(prefix=f"clipforge-highlights-{job_id}-") as directory:
            source, audio = Path(directory) / "source", Path(directory) / "audio.wav"
            context.progress("Measuring audio emphasis", 25)
            s3().download_file(settings().s3_bucket, key, str(source))
            extract_audio(source, audio)
            enrich(candidates, frames, audio_energy(audio), cuts)
        context.progress("Scoring highlights", 55)
        ranker = OptionalCloudRanker() if config.semantic_ranking else HeuristicHighlightRanker()
        ranked = ranker.score_candidates(candidates, config.keywords)
        context.progress("Selecting distinct moments", 80)
        selected = select_candidates(
            ranked,
            config.clip_count,
            config.minimum_score,
            config.max_overlap,
            config.minimum_separation,
        )
        chosen = {(c.start, c.end): (i + 1, c) for i, c in enumerate(selected)}
        context.progress("Saving highlight candidates", 95)
        with SessionLocal() as db:
            db.execute(delete(ClipCandidate).where(ClipCandidate.project_id == project_id))
            for candidate in ranked:
                choice = chosen.get((candidate.start, candidate.end))
                rank, result = choice if choice else (None, candidate)
                db.add(
                    ClipCandidate(
                        project_id=project_id,
                        start_ms=round(result.start * 1000),
                        end_ms=round(result.end * 1000),
                        transcript_text=result.text,
                        score_total=result.score,
                        score_breakdown=result.breakdown,
                        reason=result.reason,
                        title=result.title,
                        selected=choice is not None,
                        rank=rank,
                    )
                )
            db.commit()
        message = f"Selected {len(selected)} of {config.clip_count} requested highlights"
        if len(selected) < config.clip_count:
            message += "; limited by duration, quality or diversity"
        succeed(context, "READY_FOR_CLIPS", message[:100])
