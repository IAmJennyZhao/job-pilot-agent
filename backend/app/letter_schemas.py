"""Cover-letter prose contracts; deliberately independent of resume bullet matching."""
from typing import Literal
from pydantic import Field
from app.tailoring_schemas import StrictModel
from app.generation_schemas import GenerateResume
from app.review_schemas import RevisionRequest

Kind = Literal["candidate_claim", "job_context", "motivation", "transition"]


class LetterOptions(StrictModel):
    count: int = Field(default=3, ge=1, le=3)
    length: Literal["short", "standard"] = "standard"
    template_id: str | None = Field(default=None, max_length=36)


class GenerateLetter(GenerateResume):
    options: LetterOptions = Field(default_factory=LetterOptions)


class LetterSentence(StrictModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    text: str = Field(min_length=1, max_length=2000)
    sentence_kind: Kind
    candidate_evidence_ids: list[str] = Field(max_length=8)
    job_evidence_ids: list[str] = Field(max_length=8)


class LetterParagraph(StrictModel):
    sentences: list[LetterSentence] = Field(min_length=1, max_length=10)


class LetterVariant(StrictModel):
    variant_id: str = Field(min_length=1, max_length=32)
    angle: Literal["concise professional", "technical contribution", "product/user impact"]
    paragraphs: list[LetterParagraph] = Field(min_length=1, max_length=5)


class LetterDraft(StrictModel):
    variants: list[LetterVariant] = Field(min_length=1, max_length=3)


class EvidenceQuote(StrictModel):
    source_kind: Literal["candidate", "job"]
    source_id: str
    quote: str = Field(min_length=1, max_length=2500)


class SentenceVerdict(StrictModel):
    sentence_id: str
    actual_kind: Kind
    supported: bool
    explanation: str = Field(min_length=1, max_length=1000)
    supports: list[EvidenceQuote] = Field(max_length=16)


class LetterAssessment(StrictModel):
    sentences: list[SentenceVerdict] = Field(max_length=150)


class SaveLetterEdit(RevisionRequest):
    edit: LetterDraft


class CheckLetter(RevisionRequest):
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
