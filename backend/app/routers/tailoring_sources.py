from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.tailoring_schemas import ActivateSource, SourceImport, SourceList, SourcePreview
from app.services import tailoring_source_service as service

router = APIRouter(prefix="/api/profile/tailoring-sources", tags=["tailoring sources"])


@router.get("", response_model=SourceList)
def list_sources(db: Session = Depends(get_db)):
    return service.list_sources(db)


@router.post("/import", response_model=SourcePreview, status_code=201)
def import_source(payload: SourceImport, response: Response, db: Session = Depends(get_db)):
    source, created = service.import_source(db, payload)
    response.status_code = 201 if created else 200
    return service.preview(db, source)


@router.get("/{source_id}", response_model=SourcePreview)
def preview_source(source_id: str, db: Session = Depends(get_db)):
    return service.preview(db, service.get_source(db, source_id))


@router.post("/{source_id}/activate", response_model=SourcePreview)
def activate_source(source_id: str, payload: ActivateSource, db: Session = Depends(get_db)):
    source = service.get_source(db, source_id)
    return service.preview(db, service.change_activation(db, source, payload))


@router.post("/{source_id}/revoke", response_model=SourcePreview)
def revoke_source(source_id: str, payload: ActivateSource, db: Session = Depends(get_db)):
    source = service.get_source(db, source_id)
    return service.preview(db, service.change_activation(db, source, payload, revoke=True))
