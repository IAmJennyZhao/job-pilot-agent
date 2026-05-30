from html.parser import HTMLParser
from urllib.error import URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app import models, prompts, schemas
from app.services import ai_service, job_service
from app.services.concise_output import normalize_extraction_output

MAX_FETCH_BYTES = 600_000


class _ReadableTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._hidden_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._hidden_depth += 1
        if tag in {"p", "div", "li", "br", "section", "article", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._hidden_depth:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return "\n".join(part for part in self.parts if part.strip())


def _clean_text(value: str) -> str:
    return "\n".join(line.strip() for line in value.splitlines() if line.strip())


def fetch_job_page_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "CareerPilot/0.1 (+https://localhost)",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            content_type = response.headers.get("content-type", "")
            raw = response.read(MAX_FETCH_BYTES)
    except (OSError, URLError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not fetch readable job content from the URL: {exc}",
        ) from exc

    text = raw.decode("utf-8", errors="ignore")
    if "html" not in content_type.lower():
        return _clean_text(text)

    parser = _ReadableTextParser()
    parser.feed(text)
    return _clean_text(parser.text())


def _ensure_source_link(
    links: list[schemas.JobLinkBase],
    source_url: str | None,
) -> list[schemas.JobLinkBase]:
    if not source_url:
        return []
    return [
        schemas.JobLinkBase(
            kind=models.JobLinkKind.source,
            label="Job Posting",
            url=source_url,
        )
    ]


def extract_preview(
    db: Session,
    payload: schemas.JobExtractPreviewRequest,
) -> schemas.JobExtractPreview:
    source_url = str(payload.source_url) if payload.source_url else None
    source_content = _clean_text(payload.source_content or "")
    warnings: list[str] = []

    if not source_content and source_url:
        source_content = fetch_job_page_text(source_url)
        if source_content:
            warnings.append("Source content was fetched from the URL. Review extracted fields before saving.")

    if not source_content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No readable job content was available. Paste the job description or use manual fallback.",
        )

    output = ai_service.get_structured_output(
        schemas.JobExtractionOutput,
        prompts.SYSTEM_PROMPT,
        prompts.job_intake_prompt(source_url, source_content),
    )
    output = normalize_extraction_output(output)
    links = _ensure_source_link(output.links, source_url)
    duplicate_candidates = job_service.find_duplicate_candidates(
        db,
        output.company,
        output.role_title,
        [str(link.url) for link in links],
    )

    return schemas.JobExtractPreview(
        **output.model_dump(exclude={"links", "warnings"}),
        links=links,
        warnings=[*warnings, *output.warnings],
        source_url=source_url,
        source_content=source_content,
        duplicate_candidates=duplicate_candidates,
    )
