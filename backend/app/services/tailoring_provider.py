"""Bounded structured output at the existing OpenAI boundary; no SDK retries."""
import asyncio
import time
import httpx
from openai import AsyncOpenAI, APITimeoutError
from pydantic import ValidationError
from app.config import get_settings


class ProviderFailure(Exception):
    def __init__(self, message, *, repairable=False):
        self.safe_message = message
        self.repairable = repairable
        super().__init__(message)


async def _request(output_model, system, payload, model, timeout):
    settings = get_settings()
    if not settings.openai_api_key or not model:
        raise ProviderFailure("AI configuration is unavailable. Configure it before an explicit retry.")
    async with httpx.AsyncClient(trust_env=False, timeout=timeout) as http_client:
        client = AsyncOpenAI(api_key=settings.openai_api_key, http_client=http_client, max_retries=0)
        response = await client.responses.parse(model=model, instructions=system, input=payload,
            text_format=output_model, max_output_tokens=6000, store=False, timeout=timeout)
    if any(getattr(part, "type", None) == "refusal" for item in response.output for part in getattr(item, "content", [])):
        raise ProviderFailure("The provider refused this stage. Review the inputs before retrying.")
    if response.status != "completed" or response.output_parsed is None:
        raise ProviderFailure("The provider returned incomplete output. Review the run before retrying.")
    return response.output_parsed, {"response_id": response.id, "model": response.model,
        "usage": response.usage.model_dump(mode="json") if response.usage else None}


def get_tailoring_output(output_model, system, payload, *, model, timeout):
    started = time.monotonic()
    try:
        output, metadata = asyncio.run(asyncio.wait_for(_request(output_model, system, payload, model, timeout), timeout=timeout))
        return output, {**metadata, "latency_ms": round((time.monotonic() - started) * 1000)}
    except ProviderFailure:
        raise
    except (TimeoutError, APITimeoutError):
        raise ProviderFailure("Provider deadline exceeded; completion may be unknown. Retry only explicitly.") from None
    except ValidationError:
        raise ProviderFailure("Provider output did not match the stage schema.", repairable=True) from None
    except Exception:
        # Never log raw provider exceptions, which can contain source text.
        raise ProviderFailure("Provider request failed. Your saved checkpoints are preserved; retry explicitly.") from None
