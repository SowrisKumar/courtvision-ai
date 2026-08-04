"""Provider-agnostic LLM client.

The provider is chosen by whichever API key is present in the environment
(override with COURTVISION_LLM=anthropic|gemini|openai):

    ANTHROPIC_API_KEY            -> Claude (claude-opus-5)
    GEMINI_API_KEY / GOOGLE_API_KEY -> Gemini (gemini-2.5-flash)
    OPENAI_API_KEY               -> OpenAI (gpt-5-mini)

COURTVISION_LLM_MODEL overrides the default model for any provider. Provider
SDKs are imported lazily so only the one in use needs to be installed.

The unified interface is deliberately tiny: `complete(system, messages) -> str`
where messages are [{"role": "user"|"assistant", "content": str}, ...]. The
agent loop lives above this layer, so adapters stay ~20 lines each.
"""

import os
from typing import Protocol

DEFAULT_MODELS = {
    "anthropic": "claude-opus-5",
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-5-mini",
}

MAX_TOKENS = 16000

# pip extra that installs each provider's SDK (see pyproject [project.optional-dependencies]).
_SDK_PACKAGES = {
    "anthropic": "anthropic",
    "gemini": "google-genai",
    "openai": "openai",
}


class LLMSDKMissingError(RuntimeError):
    """A key is configured but the provider's SDK is not installed."""

    def __init__(self, provider: str):
        self.provider = provider
        self.package = _SDK_PACKAGES[provider]
        super().__init__(
            f"{provider} API key is set but the {self.package} package is not installed; "
            'install it with: pip install -e ".[llm]"'
        )


class LLMClient(Protocol):
    provider: str
    model: str

    def complete(self, system: str, messages: list[dict]) -> str: ...


def detect_provider() -> tuple[str, str] | None:
    """(provider, api_key) from the environment, or None if unconfigured."""
    override = os.environ.get("COURTVISION_LLM")
    candidates = [
        ("anthropic", os.environ.get("ANTHROPIC_API_KEY")),
        ("gemini", os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        ("openai", os.environ.get("OPENAI_API_KEY")),
    ]
    if override:
        for name, key in candidates:
            if name == override:
                return (name, key) if key else None
        return None
    for name, key in candidates:
        if key:
            return name, key
    return None


class AnthropicClient:
    provider = "anthropic"

    def __init__(self, api_key: str, model: str):
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def complete(self, system: str, messages: list[dict]) -> str:
        response = self._client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
        )
        if response.stop_reason == "refusal":
            return '{"answer": "The model declined to answer this request."}'
        return "".join(b.text for b in response.content if b.type == "text")


class GeminiClient:
    provider = "gemini"

    def __init__(self, api_key: str, model: str):
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self.model = model

    def complete(self, system: str, messages: list[dict]) -> str:
        contents = [
            {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
            for m in messages
        ]
        response = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config={"system_instruction": system, "max_output_tokens": MAX_TOKENS},
        )
        return response.text or ""


class OpenAIClient:
    provider = "openai"

    def __init__(self, api_key: str, model: str):
        import openai

        self._client = openai.OpenAI(api_key=api_key)
        self.model = model

    def complete(self, system: str, messages: list[dict]) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, *messages],
        )
        return response.choices[0].message.content or ""


_ADAPTERS = {"anthropic": AnthropicClient, "gemini": GeminiClient, "openai": OpenAIClient}


def create_client() -> LLMClient | None:
    """Client for the configured provider, or None if no key is set.

    Raises LLMSDKMissingError when a key is configured but the provider SDK is
    absent, so the API can answer 503 with an actionable message rather than
    letting the lazy import surface as a 500.
    """
    detected = detect_provider()
    if detected is None:
        return None
    provider, api_key = detected
    model = (os.environ.get("COURTVISION_LLM_MODEL") or "").strip() or DEFAULT_MODELS[provider]
    try:
        return _ADAPTERS[provider](api_key=api_key, model=model)
    except ImportError as exc:
        raise LLMSDKMissingError(provider) from exc
