from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, model_validator
from app.schemas import JobCreate
from app.intake_facts import IntakeFacts


class IntakeReview(BaseModel):
    job: JobCreate
    facts: IntakeFacts = Field(default_factory=IntakeFacts)
    full_description_reviewed: bool = False

    @model_validator(mode="after")
    def valid_review(self):
        if not self.job.company.strip() or not self.job.role_title.strip():
            raise ValueError("Company and role title are required.")
        if len(self.job.source_content) > 100_000:
            raise ValueError("Job description exceeds 100,000 characters.")
        if self.job.pay_min is not None and self.job.pay_max is not None and self.job.pay_min > self.job.pay_max:
            raise ValueError("Minimum pay must not exceed maximum pay.")
        for link in self.job.links:
            url = urlsplit(link.url)
            if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
                raise ValueError("Job links must be HTTP or HTTPS URLs without embedded credentials.")
        return self


class IntakeSave(IntakeReview):
    request_key: str = Field(min_length=16, max_length=128)
    decision: Literal["save_later", "continue"]
    expected_evaluation_hash: str = Field(min_length=64, max_length=64)
    allow_duplicate: bool = False
