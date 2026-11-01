from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError

from utils.logging import get_logger
from .config import get_call_budget

LOGGER = get_logger("blinky.learn.llm")

T = TypeVar("T", bound=BaseModel)


class LearnAIError(Exception):
    """Base exception for all Preppy AI errors."""


class LearnNoProviderError(LearnAIError):
    """Raised when no AI provider is configured or reachable."""


class LearnBudgetExceededError(LearnAIError):
    """Raised when the session AI call budget is exhausted."""


class LearnValidationExhaustedError(LearnAIError):
    """Raised when LLM output fails schema validation across all retries."""


class LLMClient:
    """Type-safe, budget-capped, schema-constrained LLM adapter for Preppy."""

    def __init__(self, budget: Optional[int] = None):
        self.total_budget: int = budget if budget is not None else get_call_budget()
        self.used_budget: int = 0
        self.prompts_dir: Path = Path(__file__).parent / "prompts"

    @property
    def remaining_budget(self) -> int:
        return max(0, self.total_budget - self.used_budget)

    def is_cloud_provider(self) -> bool:
        from ai.client import _resolve_provider
        provider = _resolve_provider()
        return provider not in ("ollama", "custom_local")

    def get_provider_status(self) -> Dict[str, Any]:
        try:
            from ai.client import _resolve_provider, get_provider_label
            provider = _resolve_provider()
            label = get_provider_label()
            is_cloud = self.is_cloud_provider()
            return {
                "active_provider": label,
                "provider_code": provider,
                "is_cloud": is_cloud,
                "is_connected": True,
                "call_budget_total": self.total_budget,
                "call_budget_used": self.used_budget,
                "call_budget_remaining": self.remaining_budget,
            }
        except Exception as e:
            return {
                "active_provider": "None",
                "provider_code": "none",
                "is_cloud": False,
                "is_connected": False,
                "call_budget_total": self.total_budget,
                "call_budget_used": self.used_budget,
                "call_budget_remaining": self.remaining_budget,
                "error": str(e),
            }

    def _load_prompt_template(self, prompt_name: str) -> str:
        prompt_path = self.prompts_dir / f"{prompt_name}.md"
        if not prompt_path.exists():
            raise FileNotFoundError(f"Preppy prompt template not found: {prompt_path}")
        return prompt_path.read_text(encoding="utf-8")

    def _strip_markdown_code_fences(self, text: str) -> str:
        text = text.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if fence_match:
            return fence_match.group(1).strip()
        return text

    def _call_raw_provider(self, prompt: str, max_tokens: int = 1500) -> str:
        """Invokes the configured provider via existing Blinky ai.client."""
        if self.remaining_budget <= 0:
            raise LearnBudgetExceededError(
                f"Session AI call budget ({self.total_budget} calls) has been exhausted. "
                "Adjust BLINKY_LEARN_CALL_BUDGET in settings to continue."
            )

        from ai.client import ask_text_model, _resolve_provider

        try:
            provider = _resolve_provider()
        except Exception as exc:
            raise LearnNoProviderError(f"No AI provider available: {exc}") from exc

        # Decrement budget
        self.used_budget += 1

        try:
            raw_res = ask_text_model(prompt, max_tokens=max_tokens)
            if isinstance(raw_res, dict):
                return json.dumps(raw_res)
            return str(raw_res)
        except Exception as exc:
            err_msg = str(exc)
            if "Connection" in err_msg or "timed out" in err_msg or "unreachable" in err_msg.lower():
                raise LearnNoProviderError(
                    f"AI provider '{provider}' is unreachable: {exc}. Ensure Ollama or your cloud provider is running."
                ) from exc
            raise LearnAIError(f"AI call failed: {exc}") from exc

    def generate_structured(
        self,
        prompt_name: str,
        template_args: Dict[str, Any],
        schema: Type[T],
        max_retries: int = 2,
        max_tokens: int = 1500,
    ) -> T:
        """Loads prompt, executes model call, parses JSON, and validates with Pydantic with feedback retries."""
        template = self._load_prompt_template(prompt_name)
        rendered_prompt = template
        for k, v in template_args.items():
            rendered_prompt = rendered_prompt.replace(f"{{{k}}}", str(v))

        # Include JSON schema instruction
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        full_prompt = (
            f"{rendered_prompt}\n\n"
            f"IMPORTANT: You MUST respond ONLY with a valid JSON object strictly matching this schema:\n"
            f"```json\n{schema_json}\n```\n"
        )

        last_error: Optional[str] = None
        current_prompt = full_prompt

        for attempt in range(max_retries + 1):
            if attempt > 0:
                LOGGER.info("Retrying structured generation (attempt %s/%s) for %s", attempt, max_retries, prompt_name)
                current_prompt = (
                    f"{full_prompt}\n\n"
                    f"PREVIOUS ATTEMPT FAILED SCHEMA VALIDATION:\n"
                    f"{last_error}\n"
                    f"Please correct the errors and output ONLY the valid JSON object without commentary."
                )

            raw_text = self._call_raw_provider(current_prompt, max_tokens=max_tokens)
            cleaned_json = self._strip_markdown_code_fences(raw_text)

            try:
                parsed_data = json.loads(cleaned_json)
                validated = schema.model_validate(parsed_data)
                return validated
            except (json.JSONDecodeError, ValidationError) as err:
                last_error = f"{type(err).__name__}: {err}"
                LOGGER.warning("Schema validation error on %s attempt %s: %s", prompt_name, attempt, last_error)

        raise LearnValidationExhaustedError(
            f"Failed to generate valid structured data for {prompt_name} after {max_retries + 1} attempts. Last error: {last_error}"
        )


# Global singleton instance for session
_DEFAULT_CLIENT: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _DEFAULT_CLIENT
    if _DEFAULT_CLIENT is None:
        _DEFAULT_CLIENT = LLMClient()
    return _DEFAULT_CLIENT

