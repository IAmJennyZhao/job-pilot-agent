import json
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.request import Request, urlopen

from app.config import get_settings

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
MAX_SNIPPETS = 6
MAX_SNIPPET_CHARS = 1800
MAX_FETCH_BYTES = 250_000


@dataclass
class ResearchSnippet:
    title: str
    url: str
    content: str


@dataclass
class ResearchContext:
    snippets: list[ResearchSnippet]
    warnings: list[str]

    def prompt_text(self) -> str:
        if not self.snippets:
            return "No public web snippets were retrieved."
        blocks = []
        for index, snippet in enumerate(self.snippets, start=1):
            blocks.append(
                "\n".join(
                    [
                        f"Source {index}: {snippet.title}",
                        f"URL: {snippet.url}",
                        snippet.content,
                    ]
                )
            )
        return "\n\n".join(blocks)


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


def _trim(value: str, limit: int = MAX_SNIPPET_CHARS) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def _fetch_public_page_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "CareerPilot/0.1 (+https://localhost)",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=6) as response:
            content_type = response.headers.get("content-type", "")
            raw = response.read(MAX_FETCH_BYTES)
    except (OSError, URLError):
        return ""

    text = raw.decode("utf-8", errors="ignore")
    if "html" not in content_type.lower():
        return _trim(text)
    parser = _ReadableTextParser()
    parser.feed(text)
    return _trim(parser.text())


class TavilySearchProvider:
    def search(self, query: str, max_results: int = MAX_SNIPPETS) -> ResearchContext:
        settings = get_settings()
        api_key = settings.tavily_api_key.strip() if settings.tavily_api_key else ""
        if not api_key:
            return ResearchContext(snippets=[], warnings=["TAVILY_API_KEY is not configured; company research used limited context only."])

        payload = {
            "query": query,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": "text",
            "max_results": max_results,
        }
        request = Request(
            TAVILY_SEARCH_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=12) as response:
                body = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return ResearchContext(snippets=[], warnings=[f"Tavily search failed: {exc}"])

        snippets: list[ResearchSnippet] = []
        seen_urls: set[str] = set()
        for result in body.get("results", []):
            url = str(result.get("url") or "").strip()
            if not url or url.casefold() in seen_urls:
                continue
            seen_urls.add(url.casefold())
            title = str(result.get("title") or url).strip()
            content = str(result.get("raw_content") or result.get("content") or "").strip()
            if not content:
                content = _fetch_public_page_text(url)
            if content:
                snippets.append(ResearchSnippet(title=title, url=url, content=_trim(content)))
            if len(snippets) >= max_results:
                break

        warnings = []
        if not snippets:
            warnings.append("No accessible public company research snippets were retrieved.")
        return ResearchContext(snippets=snippets, warnings=warnings)


class CompanyResearchRetrievalAgent:
    def __init__(self, search_provider: TavilySearchProvider | None = None) -> None:
        self.search_provider = search_provider or TavilySearchProvider()

    def run(self, company: str, role_title: str) -> ResearchContext:
        query = f'"{company}" employer reviews careers culture news {role_title}'
        return self.search_provider.search(query=query, max_results=MAX_SNIPPETS)
