"""OpenAI client shim with a Gemini-compatible call surface.

Wraps the OpenAI SDK so the rest of the codebase can keep using a single
``client.models.generate_content(model, contents, config)`` invocation
regardless of provider.
"""

import os
import sys
from typing import Tuple

from .logging_utils import Logger


def looks_like_openai_model_name(model: str) -> bool:
    value = (model or "").strip().lower()
    if not value:
        return False
    return value.startswith(("gpt-", "o1", "o3", "o4", "o5"))


class _Response:
    def __init__(self, text: str, prompt_tokens: int, completion_tokens: int):
        self.text = text
        self.candidates = [_Candidate(text)]
        self.usage_metadata = _Usage(prompt_tokens, completion_tokens)


class _Candidate:
    def __init__(self, text: str):
        self.content = _Content(text)


class _Content:
    def __init__(self, text: str):
        self.parts = [_Part(text)]


class _Part:
    def __init__(self, text: str):
        self.text = text
        self.executable_code = None


class _Usage:
    def __init__(self, prompt_tokens: int, completion_tokens: int):
        self.prompt_token_count = prompt_tokens
        self.candidates_token_count = completion_tokens


class _GenerateContentConfig:
    """Stand-in for google.genai types.GenerateContentConfig used by the caller."""

    def __init__(self, system_instruction=None, **_kwargs):
        self.system_instruction = system_instruction


class _TypesShim:
    GenerateContentConfig = _GenerateContentConfig


class _Models:
    def __init__(self, sdk_client):
        self._sdk = sdk_client

    def generate_content(self, model, contents, config=None):
        system_instruction = getattr(config, "system_instruction", None) if config else None
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        if isinstance(contents, str):
            messages.append({"role": "user", "content": contents})
        elif isinstance(contents, list):
            messages.append({"role": "user", "content": "\n".join(str(c) for c in contents)})
        else:
            messages.append({"role": "user", "content": str(contents)})

        resp = self._sdk.chat.completions.create(model=model, messages=messages)
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        return _Response(text, prompt_tokens, completion_tokens)


class OpenAIClient:
    def __init__(self, sdk_client):
        self.models = _Models(sdk_client)


def build_openai_client(args, log: Logger) -> Tuple[OpenAIClient, _TypesShim]:
    try:
        from openai import OpenAI
    except Exception as exc:
        log.error(
            "Failed to import the openai package. Run 'pip install openai'.\n" + str(exc)
        )
        sys.exit(2)

    api_key = getattr(args, "api_key", None) or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        log.error("No OpenAI key found. Set OPENAI_API_KEY in .env, environment, or pass --api-key.")
        sys.exit(2)
    log.info("Initializing OpenAI client with provided API key...")
    return OpenAIClient(OpenAI(api_key=api_key)), _TypesShim()
