from pathlib import Path
from tempfile import TemporaryDirectory

from clipforge_api.config import settings
from clipforge_api.db import SessionLocal
from clipforge_api.models import Analysis, MediaAsset, ProcessingJob, Project, Scene, Transcript
from clipforge_api.storage import s3
from sqlalchemy import delete

from clipforge_worker.celery_app import celery
from clipforge_worker.jobs.runtime import run_job, succeed
from clipforge_worker.media.probe import probe
from clipforge_worker.media.proxy import create_proxy, extract_audio
from clipforge_worker.scenes.detector import detect_scenes
from clipforge_worker.transcription.faster_whisper_provider import FasterWhisperProvider
from clipforge_worker.vision.face_detector import MediaPipeFaceDetector


@celery.task(name="clipforge.analyze", soft_time_limit=14400, time_limit=14500)
def analyze_project(job_id: str) -> None:
    with run_job(job_id, "ANALYZING") as context:
        if context is None:
            return
        with SessionLocal() as db:
            job = db.get(ProcessingJob, context.id)
            assert job
            project = db.get(Project, job.project_id)
            assert project and project.source_asset_id
            asset = db.get(MediaAsset, project.source_asset_id)
            assert asset
            project_id, key, language = project.id, asset.storage_key, project.language
        with TemporaryDirectory(prefix=f"clipforge-{job_id}-") as directory:
            root = Path(directory)
            source, proxy, audio = root / "source", root / "proxy.mp4", root / "audio.wav"
            context.progress("Reading media", 3)
            s3().download_file(settings().s3_bucket, key, str(source))
            info = probe(source)
            if not info.has_audio:
                raise ValueError(
                    "No audio stream was found. Add an audio track or use manual clips."
                )
            context.progress("Creating analysis proxy", 8)
            create_proxy(source, proxy)
            context.progress("Extracting audio", 15)
            extract_audio(source, audio)
            context.progress("Transcribing", 20)
            transcript = FasterWhisperProvider().transcribe(
                audio,
                None if language == "auto" else language,
                lambda value: context.progress("Transcribing", 20 + round(40 * value)),
            )
            if not transcript.segments:
                raise ValueError(
                    "No speech was detected. Try a different language or create manual clips."
                )
            context.progress("Detecting scenes", 65)
            scenes = detect_scenes(proxy)
            context.progress("Detecting faces", 75)
            warnings: list[str] = []
            try:
                faces = MediaPipeFaceDetector().analyze(
                    proxy, lambda value: context.progress("Detecting faces", 75 + round(20 * value))
                )
            except (RuntimeError, OSError, ValueError):
                faces = []
                warnings.append("Face analysis was unavailable; center-crop fallback will be used.")
            if not any(frame.faces for frame in faces):
                warnings.append(
                    "No reliable face was detected. You can set the crop anchor manually."
                )
            context.progress("Saving analysis", 97)
            with SessionLocal() as db:
                for table in (Transcript, Scene, Analysis):
                    db.execute(delete(table).where(table.project_id == project_id))
                db.add(
                    Transcript(
                        project_id=project_id,
                        language=transcript.language,
                        full_text=" ".join(s.text for s in transcript.segments),
                        segments=[s.model_dump() for s in transcript.segments],
                    )
                )
                db.add_all(
                    Scene(
                        project_id=project_id,
                        start_ms=round(start * 1000),
                        end_ms=round(end * 1000),
                    )
                    for start, end in scenes
                )
                db.add(
                    Analysis(
                        project_id=project_id,
                        face_frames=[f.model_dump() for f in faces],
                        warnings=warnings,
                    )
                )
                db.commit()
        succeed(context, "READY_FOR_CLIPS")
