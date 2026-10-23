import os

# Must be set before app modules import settings: keeps the test client's
# lifespan from running real migrations against the dev database.
os.environ.setdefault("AUTO_MIGRATE", "0")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def pin_generation_version(monkeypatch):
    """Exercise real historical contracts after the default version advances."""
    from app.services import generation_inputs, resume_generation
    from app.services.resume_validation import prompt_versions, STAGES
    from app.services.intake_preferences import digest
    from app.resume_prompts import system_for
    original = generation_inputs.capture
    def pin(version):
        def capture(db, job):
            state = original(db, job)
            snapshot = state['snapshot']
            snapshot['generation_version'] = version
            snapshot['prompt_versions'] = prompt_versions(snapshot)
            snapshot['prompt_hashes'] = {stage: digest(system_for(stage, version)) for stage in STAGES}
            state['input_hash'] = digest(snapshot)
            return state
        monkeypatch.setattr(generation_inputs, 'capture', capture)
        monkeypatch.setattr(resume_generation, 'capture', capture)
    return pin


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
