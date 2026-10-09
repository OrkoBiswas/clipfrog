from pathlib import Path
from tempfile import TemporaryDirectory

from clipforge_api.config import settings
from clipforge_api.db import SessionLocal
from clipforge_api.models import (
    Analysis,
    ClipCandidate,
    HighlightFeedback,
    MediaAsset,
    ProcessingJob,
    Project,
    Scene,
    Transcript,
)
from clipforge_api.schemas import ProcessingConfig
from clipforge_api.services.highlight_learning import learning_report, rejected_moment
from clipforge_api.storage import s3
from sqlalchemy import delete, select

from clipforge_worker.celery_app import celery
from clipforge_worker.highlights.candidates import create_candidates
from clipforge_worker.highlights.heuristic_ranker import ENGINE_VERSION, HeuristicHighlightRanker
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
            learning = learning_report(db, project.user_id)
            content_type, language = project.content_type, transcript.language
            rejected = list(
                db.execute(
                    select(HighlightFeedback.start_ms, HighlightFeedback.end_ms).where(
                        HighlightFeedback.user_id == project.user_id,
                        HighlightFeedback.project_id == project.id,
                        HighlightFeedback.rating == "poor",
                    )
                ).tuples()
            )
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
        # This engine runs entirely locally, including preference training.
        ranker = HeuristicHighlightRanker(learning["weights"])
        ranked = ranker.score_candidates(
            candidates, config.keywords, content_type=content_type, language=language
        )
        context.progress("Selecting distinct moments", 80)
        selected = select_candidates(
            [
                c
                for c in ranked
                if not rejected_moment(round(c.start * 1000), round(c.end * 1000), rejected)
            ],
            config.clip_count,
            config.minimum_score,
            config.max_overlap,
            config.minimum_separation,
        )
        chosen = {(c.start, c.end): (i + 1, c) for i, c in enumerate(selected)}
        context.progress("Saving highlight candidates", 95)
        with SessionLocal() as db:
            job = db.get(ProcessingJob, context.id)
            assert job
            job.parameters = {
                **job.parameters,
                "highlight_engine": {
                    "version": ENGINE_VERSION,
                    "mode": "local",
                    "language": language,
                    "content_type": content_type,
                    "personalized": learning["status"] == "personalized",
                    "candidates_evaluated": len(ranked),
                    "selected": len(selected),
                },
            }
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
                        scoring_metadata={
                            "engine_version": ENGINE_VERSION,
                            "features": result.features,
                            "content_profile": result.content_profile,
                            "start_boundary_quality": result.start_boundary_quality,
                            "end_boundary_quality": result.end_boundary_quality,
                            "word_timing_coverage": result.word_timing_coverage,
                            "transcript_confidence": result.transcript_confidence,
                        },
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
