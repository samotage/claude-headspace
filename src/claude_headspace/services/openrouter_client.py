"""OpenRouter API client for LLM inference."""

import hashlib
import logging
import os
import time
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class InferenceResult:
    """Structured result from an inference call."""

    text: str
    input_tokens: int
    output_tokens: int
    model: str
    latency_ms: int
    cached: bool = False
    error: str | None = None


class OpenRouterClientError(Exception):
    """Base error for OpenRouter client."""

    def __init__(self, message: str, status_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class OpenRouterClient:
    """HTTP client for OpenRouter API."""

    def __init__(self, config: dict):
        or_config = config.get("openrouter", {})
        self.base_url = or_config.get("base_url", "https://openrouter.ai/api/v1")
        self.timeout = or_config.get("timeout", 30)

        # API key: env var takes precedence
        self.api_key = os.environ.get("OPENROUTER_API_KEY") or or_config.get("api_key")

        # Retry config
        retry_config = or_config.get("retry", {})
        self.max_attempts = retry_config.get("max_attempts", 3)
        self.base_delay = retry_config.get("base_delay_seconds", 1.0)
        self.max_delay = retry_config.get("max_delay_seconds", 30.0)

    @property
    def is_configured(self) -> bool:
        """Check if the client has a valid API key."""
        return bool(self.api_key)

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/samotage/claude-headspace",
            "X-Title": "Claude Headspace",
        }

    def chat_completion(self, model: str, messages: list[dict], **kwargs) -> InferenceResult:
        """Send a chat completion request with retries.

        Args:
            model: The model identifier (e.g., "anthropic/claude-3-5-haiku-20241022")
            messages: List of message dicts with "role" and "content"
            **kwargs: Additional parameters passed to the API

        Returns:
            InferenceResult with response data

        Raises:
            OpenRouterClientError: On non-retryable errors or retry exhaustion
        """
        if not self.is_configured:
            raise OpenRouterClientError("OPENROUTER_API_KEY not configured", retryable=False)

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            **kwargs,
        }

        last_error = None
        for attempt in range(self.max_attempts):
            try:
                start_time = time.monotonic()
                response = requests.post(
                    url,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=self.timeout,
                )
                latency_ms = int((time.monotonic() - start_time) * 1000)

                if response.status_code == 200:
                    data = response.json()
                    choice = data.get("choices", [{}])[0]
                    usage = data.get("usage", {})

                    return InferenceResult(
                        text=choice.get("message", {}).get("content", ""),
                        input_tokens=usage.get("prompt_tokens", 0),
                        output_tokens=usage.get("completion_tokens", 0),
                        model=data.get("model", model),
                        latency_ms=latency_ms,
                    )

                # Classify error
                if response.status_code in (401, 400, 403):
                    raise OpenRouterClientError(
                        f"API error {response.status_code}: {response.text[:200]}",
                        status_code=response.status_code,
                        retryable=False,
                    )

                # Retryable errors: 429, 5xx
                last_error = OpenRouterClientError(
                    f"API error {response.status_code}: {response.text[:200]}",
                    status_code=response.status_code,
                    retryable=True,
                )

            except requests.exceptions.Timeout:
                last_error = OpenRouterClientError(
                    "Request timed out", retryable=True
                )
            except requests.exceptions.ConnectionError:
                last_error = OpenRouterClientError(
                    "Connection failed", retryable=True
                )
            except OpenRouterClientError:
                raise
            except Exception as e:
                last_error = OpenRouterClientError(
                    f"Unexpected error: {e}", retryable=False
                )
                raise last_error

            # Wait before retry with exponential backoff
            if attempt < self.max_attempts - 1:
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                logger.warning(
                    f"OpenRouter request failed (attempt {attempt + 1}/{self.max_attempts}): {last_error}. "
                    f"Retrying in {delay:.1f}s"
                )
                time.sleep(delay)

        raise last_error

    def check_connectivity(self) -> bool:
        """Check if OpenRouter API is reachable.

        Returns:
            True if API responds, False otherwise
        """
        if not self.is_configured:
            return False

        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers=self._get_headers(),
                timeout=5,
            )
            return response.status_code == 200
        except Exception:
            return False

    @staticmethod
    def compute_input_hash(content: str) -> str:
        """Compute SHA-256 hash of input content for caching."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
