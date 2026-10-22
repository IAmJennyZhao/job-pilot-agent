import copy
import pytest
from app.services import resume_layout as layout, resume_compiler as compiler
from tailoring_fixtures import bank_data


def sample():
    bank = bank_data()
    content = {"identity": bank["identity"], "education": bank["education"], "records": bank["records"],
               "draft": {"skills": [{"name": "Python"}], "bullets": [{"record_id": "R-1", "text": bank["claims"][0]["text"]}]}}
    return content, {"projection": bank}


def test_public_document_omits_provenance_and_includes_project_metadata():
    content, snapshot = sample()
    content["identity"].update(location="Boston", relocation_preference={"display": "Open to relocation to NYC", "note": "PRIVATE_NOTE"})
    content["records"].append({"id": "P-1", "kind": "project", "name": "Demo", "subtitle": "Internal prototype", "technologies": ["C++", "C#"], "public_url": "https://example.test/demo"})
    content["draft"]["bullets"].append({"record_id": "P-1", "text": "Built an internal prototype."})
    doc = layout.document(content, snapshot)
    tex, text = layout.exports(doc)
    for value in ("Internal prototype", "C++", "https://example.test/demo", "Open to relocation to NYC"):
        assert value in text and value in tex
    for value in ("PRIVATE_NOTE", "ARCHIVE_ONLY_SECRET", "C-ALLOWED", "S-1", "EXCLUDED_CLAIM_SECRET"):
        assert value not in text and value not in tex


def test_escaping_and_links_are_data_only():
    assert layout.escape(r"\input{secret} & 90% $ # _ ~ ^") == r"\textbackslash{}input\{secret\} \& 90\% \$ \# \_ \textasciitilde{} \textasciicircum{}"
    assert layout.safe_link("file:///secret") is None
    assert layout.safe_link("https://user:password@example.test") is None
    assert layout.safe_link("https://example.test/a_%20?x=y&b=2") == "https://example.test/a_%20?x=y&b=2"
    with pytest.raises(ValueError): layout.escape("hidden\x00text")


def test_real_pdf_compiles_with_matching_text_and_one_page(tmp_path):
    content, snapshot = sample()
    tex, text = layout.exports(layout.document(content, snapshot))
    executable, _ = compiler.compiler()
    pdf, warnings = compiler.compile_pdf(tex, executable)
    report = compiler.inspect_pdf(pdf, text, warnings)
    assert report["valid"], report
    assert report["pages"] == 1
    import pymupdf
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        assert doc.metadata["author"] == "Synthetic Tester"
        assert "Resume" in doc.metadata["title"]


def test_real_pdf_overflow_is_blocked_without_rewriting():
    content, snapshot = sample()
    content["draft"]["bullets"] *= 70
    tex, text = layout.exports(layout.document(content, snapshot))
    pdf, warnings = compiler.compile_pdf(tex, compiler.compiler()[0])
    report = compiler.inspect_pdf(pdf, text, warnings)
    assert not report["valid"] and report["pages"] > 1
    assert tex.count(r"\item ") == 70


def test_project_metadata_filters_excluded_technologies_and_editorial_labels():
    content, snapshot = sample()
    bank = snapshot["projection"]
    bank["records"][0].update(kind="project", name="Demo", subtitle="Supported subtitle", public_url="https://example.test", technologies=["Python", "Secret planned tool"])
    content["draft"]["bullets"][0]["evidence_ids"] = ["C-ALLOWED"]
    bank["skill_groups"][0]["label"] = "Additional technologies (select by relevance)"
    metadata = layout.presentation_metadata(content, snapshot, bank)
    assert metadata["R-1"]["technologies"] == ["Python"]
    tex, text = layout.exports(layout.document(content, snapshot, metadata))
    assert "Supported subtitle" in text
    assert "select by relevance" not in tex and "Secret planned tool" not in text


def test_real_special_characters_links_and_tex_injection_are_inert():
    import pymupdf
    content, snapshot = sample()
    content["identity"]["name"] = "Émilie Example"
    content["identity"]["website"] = "https://example.test/a_b?x=1&y=2#demo"
    content["draft"]["bullets"][0]["text"] = r"Used C++, C#, A&B, 90%, $5 and snake_case. Literal \input{secret} stays text."
    tex, text = layout.exports(layout.document(content, snapshot))
    pdf, warnings = compiler.compile_pdf(tex, compiler.compiler()[0])
    report = compiler.inspect_pdf(pdf, text, warnings)
    assert report["valid"], report
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        assert content["identity"]["website"] in [link.get("uri") for link in doc[0].get_links()]


def test_timeout_and_crash_scratch_cleanup(monkeypatch, tmp_path):
    import os
    import time
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "asset_storage_dir", str(tmp_path))
    scratch = tmp_path / "render-tmp"; scratch.mkdir()
    stale = scratch / "job-pilot-render-old"; stale.mkdir(); (stale / "private.tex").write_text("private")
    unrelated = scratch / "unrelated"; unrelated.mkdir()
    recent = scratch / "job-pilot-render-live"; recent.mkdir()
    os.utime(stale, (time.time()-7200, time.time()-7200))
    monkeypatch.setattr(compiler, "TIMEOUT_SECONDS", 0)
    content, snapshot = sample()
    tex, _ = layout.exports(layout.document(content, snapshot))
    with pytest.raises(ValueError, match="timed out"):
        compiler.compile_pdf(tex, compiler.compiler()[0])
    assert not stale.exists() and unrelated.exists() and recent.exists()
    assert sorted(p.name for p in scratch.iterdir()) == ["job-pilot-render-live", "unrelated"]


def test_pdf_active_content_is_rejected():
    import io
    from pypdf import PdfReader, PdfWriter
    content, snapshot = sample()
    tex, text = layout.exports(layout.document(content, snapshot))
    pdf, _ = compiler.compile_pdf(tex, compiler.compiler()[0])
    writer = PdfWriter(); writer.append(PdfReader(io.BytesIO(pdf))); writer.add_js("app.alert('unsafe')")
    output = io.BytesIO(); writer.write(output)
    with pytest.raises(ValueError, match="active content|external actions|opening actions"):
        compiler.inspect_pdf(output.getvalue(), text)
