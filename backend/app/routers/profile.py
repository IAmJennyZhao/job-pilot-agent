from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services import profile_asset_service, profile_service

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.get("", response_model=schemas.ResumeProfileRead | None)
def get_profile(db: Session = Depends(get_db)):
    return profile_service.get_active_profile(db)


@router.post("", response_model=schemas.ResumeProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(payload: schemas.ResumeProfileCreate, db: Session = Depends(get_db)):
    return profile_service.create_active_profile(db, payload)


@router.get("/resume-options", response_model=list[schemas.ResumeOptionRead])
def list_resume_options(db: Session = Depends(get_db)):
    return profile_asset_service.list_resume_options(db)


@router.post("/resume-options", response_model=schemas.ResumeOptionRead, status_code=status.HTTP_201_CREATED)
def create_resume_option(payload: schemas.ResumeOptionCreate, db: Session = Depends(get_db)):
    return profile_asset_service.create_resume_option(db, payload)


@router.post(
    "/resume-options/import",
    response_model=schemas.ResumeOptionRead,
    status_code=status.HTTP_201_CREATED,
)
async def import_resume_option(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    return profile_asset_service.import_resume_pdf(
        db,
        file.filename,
        file.content_type,
        content,
    )


@router.patch("/resume-options/{option_id}", response_model=schemas.ResumeOptionRead)
def update_resume_option(
    option_id: str,
    payload: schemas.ResumeOptionUpdate,
    db: Session = Depends(get_db),
):
    option = profile_asset_service.get_resume_option(db, option_id)
    if not option:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume option not found")
    return profile_asset_service.update_resume_option(db, option, payload)


@router.post("/resume-options/{option_id}/confirm", response_model=schemas.ResumeOptionRead)
def confirm_resume_option(
    option_id: str,
    payload: schemas.ResumeOptionConfirmRequest,
    db: Session = Depends(get_db),
):
    option = profile_asset_service.get_resume_option(db, option_id)
    if not option:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume option not found")
    return profile_asset_service.confirm_resume_option(db, option, payload)


@router.get("/resume-options/{option_id}/download")
def download_resume_option(option_id: str, db: Session = Depends(get_db)):
    option = profile_asset_service.get_resume_option(db, option_id)
    if not option:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume option not found")
    path = profile_asset_service.resume_option_file_path(option)
    return FileResponse(
        path,
        media_type=option.content_type or "application/pdf",
        filename=option.source_filename or path.name,
    )


@router.delete("/resume-options/{option_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume_option(option_id: str, db: Session = Depends(get_db)):
    option = profile_asset_service.get_resume_option(db, option_id)
    if not option:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume option not found")
    profile_asset_service.delete_resume_option(db, option)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/cover-letter-templates", response_model=list[schemas.CoverLetterTemplateRead])
def list_cover_letter_templates(db: Session = Depends(get_db)):
    return profile_asset_service.list_cover_letter_templates(db)


@router.post(
    "/cover-letter-templates",
    response_model=schemas.CoverLetterTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
def create_cover_letter_template(
    payload: schemas.CoverLetterTemplateCreate,
    db: Session = Depends(get_db),
):
    return profile_asset_service.create_cover_letter_template(db, payload)


@router.patch("/cover-letter-templates/{template_id}", response_model=schemas.CoverLetterTemplateRead)
def update_cover_letter_template(
    template_id: str,
    payload: schemas.CoverLetterTemplateUpdate,
    db: Session = Depends(get_db),
):
    template = profile_asset_service.get_cover_letter_template(db, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cover letter template not found")
    return profile_asset_service.update_cover_letter_template(db, template, payload)


@router.delete("/cover-letter-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cover_letter_template(template_id: str, db: Session = Depends(get_db)):
    template = profile_asset_service.get_cover_letter_template(db, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cover letter template not found")
    profile_asset_service.delete_cover_letter_template(db, template)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/coverage-gaps", response_model=schemas.CoverageGapResponse)
def generate_coverage_gaps(db: Session = Depends(get_db)):
    return profile_asset_service.generate_coverage_gaps(db)


@router.patch("/{profile_id}", response_model=schemas.ResumeProfileRead)
def update_profile(
    profile_id: str,
    payload: schemas.ResumeProfileUpdate,
    db: Session = Depends(get_db),
):
    profile = db.get(models.ResumeProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile_service.update_profile(db, profile, payload)
