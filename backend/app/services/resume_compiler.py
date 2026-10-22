"""Bounded local pdfLaTeX execution; no model text or imported commands are run."""
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import unicodedata
from pathlib import Path

import pymupdf

from app.config import BACKEND_DIR, get_settings

MAX_PDF_BYTES = 5 * 1024 * 1024
TIMEOUT_SECONDS = 30
_slots = threading.BoundedSemaphore(2)


def compiler():
    configured = get_settings().resume_pdflatex
    portable = BACKEND_DIR / "storage" / "texlive" / "bin" / ("windows/pdflatex.exe" if os.name == "nt" else "x86_64-linux/pdflatex")
    path = configured or shutil.which("pdflatex") or (str(portable) if portable.is_file() else None)
    if not path:
        raise ValueError("pdfLaTeX is not installed. Configure RESUME_PDFLATEX and install the documented template packages, then retry preview.")
    try:
        result = subprocess.run([path, "--version"], capture_output=True, timeout=5, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        raise ValueError("The configured pdfLaTeX compiler could not start. Check RESUME_PDFLATEX.") from None
    version = result.stdout.decode("utf-8", "replace").splitlines()[0]
    if "pdfTeX" not in version or "TeX Live" not in version:
        raise ValueError("This renderer requires TeX Live pdfLaTeX. Other engines must be validated before use.")
    return path, version


def compile_pdf(tex, executable):
    if len(tex.encode("utf-8")) > 200_000:
        raise ValueError("Resume exceeds the rendering input limit; shorten the saved content.")
    if not _slots.acquire(blocking=False):
        raise ValueError("Two previews are already rendering. Retry after they finish.")
    try:
        # OS-managed private temporary directories; no paths derived from imported data.
        with tempfile.TemporaryDirectory(prefix="job-pilot-render-") as directory:
            root = Path(directory)
            (root / "resume.tex").write_text(tex, encoding="utf-8")
            # No API credentials, custom TeX search paths, shell escape or font generators.
            env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE") if k in os.environ}
            env.update(PATH=str(Path(executable).resolve().parent), openin_any="p", openout_any="p", shell_escape="f",
                       MKTEXPK="0", MKTEXTFM="0", MKTEXFMT="0", SOURCE_DATE_EPOCH="946684800", FORCE_SOURCE_DATE="1")
            args = [executable, "-no-shell-escape", "-no-parse-first-line", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "resume.tex"]
            with (root / "compiler-output.txt").open("wb") as log:
                process = subprocess.Popen(args, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                try:
                    deadline = time.monotonic() + TIMEOUT_SECONDS
                    while process.poll() is None:
                        if time.monotonic() > deadline:
                            raise ValueError("PDF rendering timed out. Your saved revision is unchanged; retry explicitly.")
                        if sum(p.stat().st_size for p in root.iterdir() if p.is_file()) > 15 * 1024 * 1024:
                            raise ValueError("PDF rendering exceeded the output limit. Shorten the saved revision.")
                        time.sleep(0.05)
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
            log = (root / "resume.log").read_text(encoding="utf-8", errors="replace") if (root / "resume.log").exists() else ""
            if process.returncode or not (root / "resume.pdf").is_file():
                # Never return raw logs: they may contain resume text or local paths.
                if "Unicode character" in log:
                    raise ValueError("pdfLaTeX cannot display a character in this revision. Correct its supported spelling in the source or editor; no characters were silently replaced.")
                raise ValueError("PDF compilation failed. Check the installed template packages and supported characters. Saved content is unchanged.")
            pdf = (root / "resume.pdf").read_bytes()
            if len(pdf) > MAX_PDF_BYTES:
                raise ValueError("PDF exceeds the 5 MB artifact limit.")
            warnings = []
            if re.search(r"Overfull \\[hv]box", log):
                warnings.append("Text exceeds a layout box. Shorten the affected content and preview a new saved revision.")
            if "Missing character:" in log:
                warnings.append("The font could not display every character.")
            return pdf, warnings
    finally:
        _slots.release()


def normalized(text):
    # Ignore layout whitespace/separators and PDF ligature encoding, not substantive text.
    text = unicodedata.normalize("NFKC", text).replace("--", "–")
    return re.sub(r"[\s|•]+", "", text).replace("–", "-").replace("—", "-")


def inspect_pdf(pdf, text, compiler_warnings=()):
    issues = list(compiler_warnings)
    if len(pdf) > MAX_PDF_BYTES or not pdf.startswith(b"%PDF-"):
        raise ValueError("Invalid or oversized PDF artifact.")
    with pymupdf.open(stream=pdf, filetype="pdf") as document:
        if document.is_encrypted or not 1 <= len(document) <= 20:
            raise ValueError("Unreadable or excessive PDF pages.")
        if len(document) != 1:
            issues.append(f"Resume is {len(document)} pages. Save a shorter revision; body text and margins will not be reduced.")
        extracted = ""
        for page in document:
            if abs(page.rect.width - 612) > 1 or abs(page.rect.height - 792) > 1:
                issues.append("PDF must use US Letter pages.")
            extracted += page.get_text(sort=False)
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        x0, y0, x1, y1 = span["bbox"]
                        # Font ascenders/descenders may extend slightly beyond the nominal box.
                        if x0 < 41 or x1 > 571 or y0 < 24 or y1 > 768:
                            issues.append("Text extends beyond the safe page margins.")
                        if span["size"] < 9.8:
                            issues.append("Text falls below the allowed project technology size.")
            for link in page.get_links():
                if link.get("kind") != pymupdf.LINK_URI or not link.get("uri", "").startswith(("https://", "http://", "mailto:")):
                    issues.append("PDF contains an unsupported link action.")
        # Compare ordered text after removing bullet markers; punctuation/qualifiers still matter.
        expected = normalized(re.sub(r"(?m)^- ", "", text))
        actual = normalized(extracted)
        if expected != actual:
            issues.append("PDF text differs from the export text or reading order. Inspect the preview before correcting the saved content.")
        return {"validator_version": "resume-layout-checks-v1", "valid": not issues, "pages": len(document),
                "issues": list(dict.fromkeys(issues)), "human_layout_review_required": True}
