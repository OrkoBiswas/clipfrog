"""Cache original-footage detections so previews and exports compose the same people."""

import uuid
from collections.abc import Callable
from pathlib import Path

from clipforge_worker.vision.face_detector import (
    COLLAGE_DETECTOR_VERSION,
    CollageFaceDetector,
    FaceFrame,
    collage_analysis_ready,
    merge_collage_frames,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from clipforge_api.models import Analysis, Project


def collage_faces(
    db: Session,
    project_id: uuid.UUID,
    source: Path | str,
    start: float,
    end: float,
    progress: Callable[[float], None] = lambda value: None,
) -> list[FaceFrame]:
    analysis = db.scalar(select(Analysis).where(Analysis.project_id == project_id))
    frames = [FaceFrame.model_validate(frame) for frame in analysis.face_frames] if analysis else []
    if collage_analysis_ready(frames, start, end):
        return [
            frame
            for frame in frames
            if start <= frame.timestamp < end and frame.detector == COLLAGE_DETECTOR_VERSION
        ]
    refined = CollageFaceDetector().analyze(source, start, end, progress)
    # Lock the parent as well: a project without prior analysis has no child
    # row to lock yet, and simultaneous previews must create it only once.
    db.execute(select(Project.id).where(Project.id == project_id).with_for_update())
    # Re-read under the row lock so overlapping preview/render requests cannot
    # overwrite each other's completed analysis ranges.
    analysis = db.scalar(
        select(Analysis)
        .where(Analysis.project_id == project_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if analysis is None:
        analysis = Analysis(project_id=project_id, face_frames=[])
        db.add(analysis)
    latest = [FaceFrame.model_validate(frame) for frame in analysis.face_frames]
    analysis.face_frames = [
        frame.model_dump() for frame in merge_collage_frames(latest, refined, start, end)
    ]
    db.commit()
    return refined
