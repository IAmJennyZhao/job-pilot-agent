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
    assert layout.safe_link("https://example.test/a_%20?x=y&b=2") == "https://example.test/a_%2520?x=y%26b=2"
    with pytest.raises(ValueError): layout.escape("hidden\x00text")


def test_real_pdf_compiles_with_matching_text_and_one_page(tmp_path):
    content, snapshot = sample()
    tex, text = layout.exports(layout.document(content, snapshot))
    executable, _ = compiler.compiler()
    pdf, warnings = compiler.compile_pdf(tex, executable)
    report = compiler.inspect_pdf(pdf, text, warnings)
    assert report["valid"], report
    assert report["pages"] == 1


def test_real_pdf_overflow_is_blocked_without_rewriting():
    content, snapshot = sample()
    content["draft"]["bullets"] *= 70
    tex, text = layout.exports(layout.document(content, snapshot))
    pdf, warnings = compiler.compile_pdf(tex, compiler.compiler()[0])
    report = compiler.inspect_pdf(pdf, text, warnings)
    assert not report["valid"] and report["pages"] > 1
    assert tex.count(r"\item ") == 70
