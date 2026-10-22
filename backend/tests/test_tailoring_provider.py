import asyncio
from types import SimpleNamespace
import pytest
from app.config import get_settings
from app.generation_schemas import CritiqueReport
from app.services import tailoring_provider as provider


def test_provider_uses_structured_schema_without_tools_storage_or_retries(monkeypatch):
    monkeypatch.setattr(get_settings(), "openai_api_key", "synthetic-key")
    calls = []
    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["max_retries"] == 0
            self.responses = self
        async def parse(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output=[], status="completed", output_parsed=CritiqueReport(issues=[]), id="synthetic-response", model="synthetic-model", usage=None)
    monkeypatch.setattr(provider, "AsyncOpenAI", FakeClient)
    output, metadata = provider.get_tailoring_output(CritiqueReport, "system", "fictional data", model="synthetic-model", timeout=1)
    assert isinstance(output, CritiqueReport) and metadata["usage"] is None
    assert len(calls) == 1 and calls[0]["store"] is False and "tools" not in calls[0]
    assert calls[0]["text_format"] is CritiqueReport and calls[0]["max_output_tokens"] == 6000


@pytest.mark.parametrize("kind", ["refusal", "incomplete", "exception", "timeout"])
def test_provider_errors_are_bounded_and_sanitized(monkeypatch, caplog, kind):
    monkeypatch.setattr(get_settings(), "openai_api_key", "synthetic-key")
    class FakeClient:
        def __init__(self, **kwargs): self.responses = self
        async def parse(self, **kwargs):
            if kind == "exception": raise RuntimeError("PRIVATE_PROVIDER_DETAILS")
            if kind == "timeout": await asyncio.sleep(0.1)
            return SimpleNamespace(output=[SimpleNamespace(content=[SimpleNamespace(type="refusal", refusal="PRIVATE_PROVIDER_DETAILS")])] if kind == "refusal" else [], status="incomplete", output_parsed=None)
    monkeypatch.setattr(provider, "AsyncOpenAI", FakeClient)
    with pytest.raises(provider.ProviderFailure) as error:
        provider.get_tailoring_output(CritiqueReport, "system", "fictional data", model="synthetic-model", timeout=0.01 if kind == "timeout" else 1)
    assert not error.value.repairable
    assert "PRIVATE_PROVIDER_DETAILS" not in str(error.value) + caplog.text
