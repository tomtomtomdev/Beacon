"""/resumes — upload (paste / .txt text), list, set-active, delete (§11 12b).

Transport only: parse the DTO, call one use case, serialize. The upload body is JSON text
(the frontend reads a .txt file client-side); a PDF path would add a multipart branch here
once PdfResumeParser lands behind the ResumeParser port.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from beacon.api.deps import ResumeParserDep, ResumeRepoDep
from beacon.application.resumes import (
    activate_resume,
    delete_resume,
    ingest_resume,
    list_resumes,
)
from beacon.domain.resume import Resume

router = APIRouter()


class ResumeCreate(BaseModel):
    label: str
    text: str
    target_countries: list[str] = Field(default_factory=list)


class ProfileOut(BaseModel):
    categories: list[str]
    level: str
    years: int | None
    skills: list[str]
    target_countries: list[str]


class ResumeOut(BaseModel):
    id: int
    label: str
    active: bool
    created_at: datetime | None
    resume_hash: str
    profile: ProfileOut


@router.post("/resumes", status_code=201)
def post_resume(body: ResumeCreate, resumes: ResumeRepoDep, parser: ResumeParserDep) -> ResumeOut:
    resume = ingest_resume(
        resumes,
        parser,
        data=body.text,
        kind="text",
        label=body.label,
        target_countries=frozenset(code.upper() for code in body.target_countries),
        created_at=datetime.now(UTC),
    )
    return _to_out(resume)


@router.get("/resumes")
def get_resumes(resumes: ResumeRepoDep) -> list[ResumeOut]:
    return [_to_out(resume) for resume in list_resumes(resumes)]


@router.put("/resumes/{resume_id}/active")
def put_resume_active(resume_id: int, resumes: ResumeRepoDep) -> ResumeOut:
    activated = activate_resume(resumes, resume_id)
    if activated is None:
        raise HTTPException(status_code=404, detail="resume not found")
    return _to_out(activated)


@router.delete("/resumes/{resume_id}", status_code=204)
def delete_resume_route(resume_id: int, resumes: ResumeRepoDep) -> Response:
    if not delete_resume(resumes, resume_id):
        raise HTTPException(status_code=404, detail="resume not found")
    return Response(status_code=204)


def _to_out(resume: Resume) -> ResumeOut:
    if resume.id is None:  # persisted rows always carry an id; guard narrows the type
        raise ValueError("persisted resume missing id")
    profile = resume.profile
    return ResumeOut(
        id=resume.id,
        label=resume.label,
        active=resume.active,
        created_at=resume.created_at,
        resume_hash=resume.resume_hash,
        profile=ProfileOut(
            categories=sorted(category.value for category in profile.categories),
            level=profile.level.value,
            years=profile.years,
            skills=sorted(profile.skills),
            target_countries=sorted(profile.target_countries),
        ),
    )
