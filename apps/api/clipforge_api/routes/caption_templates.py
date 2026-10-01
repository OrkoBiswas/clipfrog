import uuid
from copy import deepcopy

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from clipforge_api.clip_schemas import CaptionConfig
from clipforge_api.models import CaptionLibrary, User
from clipforge_api.security import CurrentUser, Db
from clipforge_api.services.caption_templates import TEMPLATES

router = APIRouter(tags=["Caption templates"])


def library(db: Db, user: CurrentUser) -> CaptionLibrary:
    db.execute(select(User).where(User.id == user.id).with_for_update())
    row = db.get(CaptionLibrary, user.id)
    if not row:
        row = CaptionLibrary(
            user_id=user.id, data={"custom": [], "favorites": [], "recent": [], "default": None}
        )
        db.add(row)
        db.flush()
    return row


@router.get("/caption-templates")
def catalog(db: Db, user: CurrentUser) -> dict:
    row = db.get(CaptionLibrary, user.id)
    data = row.data if row else {}
    return {
        "items": [*TEMPLATES, *data.get("custom", [])],
        "favorites": data.get("favorites", []),
        "recent": data.get("recent", []),
        "default": data.get("default"),
    }


class TemplateInput(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"\S")
    config: CaptionConfig


@router.post("/caption-templates", status_code=201)
def create(body: TemplateInput, db: Db, user: CurrentUser) -> dict:
    row = library(db, user)
    data = deepcopy(row.data)
    if len(data["custom"]) >= 50:
        raise HTTPException(422, "Keep at most 50 custom templates.")
    identifier = str(uuid.uuid4())
    item = {
        "id": identifier,
        "name": body.name,
        "category": "My Templates",
        "config": {**body.config.model_dump(mode="json"), "template_id": identifier, "cues": None},
    }
    data["custom"].append(item)
    row.data = data
    db.commit()
    return item


@router.put("/caption-templates/{identifier}")
def update(identifier: str, body: TemplateInput, db: Db, user: CurrentUser) -> dict:
    row = library(db, user)
    data = deepcopy(row.data)
    item = next((item for item in data["custom"] if item["id"] == identifier), None)
    if not item:
        raise HTTPException(404, "Custom template not found.")
    item.update(
        name=body.name,
        config={**body.config.model_dump(mode="json"), "template_id": identifier, "cues": None},
    )
    row.data = data
    db.commit()
    return item


@router.delete("/caption-templates/{identifier}", status_code=204)
def delete(identifier: str, db: Db, user: CurrentUser) -> None:
    row = library(db, user)
    data = deepcopy(row.data)
    if not any(item["id"] == identifier for item in data["custom"]):
        raise HTTPException(404, "Custom template not found.")
    data["custom"] = [item for item in data["custom"] if item["id"] != identifier]
    for key in ["favorites", "recent"]:
        data[key] = [value for value in data[key] if value != identifier]
    if data["default"] == identifier:
        data["default"] = None
    row.data = data
    db.commit()


class Preference(BaseModel):
    action: str = Field(pattern="^(favorite|recent|default)$")


@router.post("/caption-templates/{identifier}/preference")
def preference(identifier: str, body: Preference, db: Db, user: CurrentUser) -> dict:
    row = library(db, user)
    data = deepcopy(row.data)
    if not any(item["id"] == identifier for item in [*TEMPLATES, *data["custom"]]):
        raise HTTPException(404, "Template not found.")
    if body.action == "favorite":
        data["favorites"] = (
            [value for value in data["favorites"] if value != identifier]
            if identifier in data["favorites"]
            else [*data["favorites"], identifier]
        )
    elif body.action == "recent":
        data["recent"] = [identifier, *[value for value in data["recent"] if value != identifier]][
            :12
        ]
    else:
        data["default"] = identifier
    row.data = data
    db.commit()
    return data
