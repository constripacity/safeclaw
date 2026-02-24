"""LLM Planner — generates execution plans validated against policy."""

from __future__ import annotations

import json
import os
import re

from pydantic import BaseModel

from safeclaw.audit import AuditEvent, write_audit
from safeclaw.policy import Policy

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PlannerError(Exception):
    """Base exception for planner errors."""


class PlannerDisabledError(PlannerError):
    """Raised when the planner is not enabled in policy."""


class PlanNetworkError(PlannerError):
    """Raised when network access is required but not allowed."""


class PlanParseError(PlannerError):
    """Raised when the LLM returns unparseable JSON."""

    def __init__(self, message: str, raw_response: str = "") -> None:
        super().__init__(message)
        self.raw_response = raw_response


class PlanConnectionError(PlannerError):
    """Raised when the LLM backend is unreachable."""


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class PlanStep(BaseModel):
    """A single step in an execution plan."""

    plugin: str
    target: str
    reason: str = ""


class ExecutionPlan(BaseModel):
    """An LLM-generated execution plan."""

    steps: list[PlanStep]
    raw_response: str = ""


class PlanResult(BaseModel):
    """Result of validating an execution plan against policy."""

    plan: ExecutionPlan
    validated: bool
    rejected_steps: list[str] = []


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
You are SafeClaw's planning assistant. Your job is to turn a user's task \
description into a JSON execution plan.

Available plugins: {plugins}

Policy constraints:
- Project root: {root}
- Network allowed: {network}
- Shell allowed: {shell}
- Max steps per plan: {max_steps}

You MUST respond with ONLY valid JSON — no markdown fences, no explanation, \
no extra text. Use this exact format:

{{"steps": [{{"plugin": "plugin_name", "target": "./path", "reason": "why"}}]}}

Rules:
- Only use plugins from the available list above.
- Target paths must be relative to the project root.
- Keep plans concise — use the fewest steps necessary.
- If no plugins are relevant, return {{"steps": []}}.
"""


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


def _get_api_key(policy: Policy) -> str:
    """Read the API key from the env var specified in policy."""
    env_var = policy.planner.api_key_env
    if not env_var:
        return ""
    return os.environ.get(env_var, "")


class _OllamaBackend:
    """Send chat completions to a local Ollama instance."""

    def call(self, policy: Policy, system: str, user_msg: str) -> str:
        """Send a request to Ollama's /api/chat endpoint."""
        import httpx

        url = f"{policy.planner.base_url.rstrip('/')}/api/chat"
        payload = {
            "model": policy.planner.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            "stream": False,
            "format": "json",
        }
        try:
            resp = httpx.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except httpx.ConnectError as exc:
            raise PlanConnectionError(f"Cannot reach Ollama at {url}: {exc}") from exc
        except (httpx.HTTPStatusError, KeyError) as exc:
            raise PlanConnectionError(f"Ollama request failed: {exc}") from exc


class _OpenAIBackend:
    """Send chat completions to the OpenAI API."""

    def call(self, policy: Policy, system: str, user_msg: str) -> str:
        """Send a request to OpenAI's chat completions endpoint."""
        import httpx

        api_key = _get_api_key(policy)
        if not api_key:
            raise PlanConnectionError(
                f"No API key found. Set the {policy.planner.api_key_env!r} environment variable."
            )
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "model": policy.planner.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.1,
        }
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except httpx.ConnectError as exc:
            raise PlanConnectionError(f"Cannot reach OpenAI API: {exc}") from exc
        except (httpx.HTTPStatusError, KeyError, IndexError) as exc:
            raise PlanConnectionError(f"OpenAI request failed: {exc}") from exc


class _AnthropicBackend:
    """Send messages to the Anthropic API."""

    def call(self, policy: Policy, system: str, user_msg: str) -> str:
        """Send a request to Anthropic's messages endpoint."""
        import httpx

        api_key = _get_api_key(policy)
        if not api_key:
            raise PlanConnectionError(
                f"No API key found. Set the {policy.planner.api_key_env!r} environment variable."
            )
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": policy.planner.model,
            "max_tokens": 1024,
            "system": system,
            "messages": [{"role": "user", "content": user_msg}],
        }
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            return resp.json()["content"][0]["text"]
        except httpx.ConnectError as exc:
            raise PlanConnectionError(f"Cannot reach Anthropic API: {exc}") from exc
        except (httpx.HTTPStatusError, KeyError, IndexError) as exc:
            raise PlanConnectionError(f"Anthropic request failed: {exc}") from exc


_BACKENDS: dict[str, type] = {
    "ollama": _OllamaBackend,
    "openai": _OpenAIBackend,
    "anthropic": _AnthropicBackend,
}


def get_backend(policy: Policy) -> _OllamaBackend | _OpenAIBackend | _AnthropicBackend:
    """Return the appropriate backend instance for the policy."""
    name = policy.planner.backend
    cls = _BACKENDS.get(name)
    if cls is None:
        raise PlannerError(f"Unknown planner backend: {name!r}")
    return cls()


# ---------------------------------------------------------------------------
# Plan parsing & validation
# ---------------------------------------------------------------------------


def _parse_plan_json(raw: str) -> ExecutionPlan:
    """Parse LLM output into an ExecutionPlan.

    Tolerates markdown fences around the JSON.
    """
    text = raw.strip()
    if not text:
        raise PlanParseError("LLM returned an empty response.", raw_response=raw)

    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PlanParseError(f"Invalid JSON from LLM: {exc}", raw_response=raw) from exc

    if not isinstance(data, dict) or "steps" not in data:
        raise PlanParseError("LLM JSON missing 'steps' key.", raw_response=raw)

    steps = [PlanStep(**s) for s in data["steps"]]
    return ExecutionPlan(steps=steps, raw_response=raw)


def validate_plan(plan: ExecutionPlan, policy: Policy) -> PlanResult:
    """Validate an execution plan against the security policy.

    Args:
        plan: The plan to validate.
        policy: The active security policy.

    Returns:
        A PlanResult with validated status and list of rejected steps.
    """
    if len(plan.steps) > policy.planner.max_steps:
        return PlanResult(
            plan=plan,
            validated=False,
            rejected_steps=[f"Plan has {len(plan.steps)} steps (max {policy.planner.max_steps})"],
        )

    root = policy.root_path()
    rejected: list[str] = []

    for step in plan.steps:
        if step.plugin not in policy.allowed_plugins:
            rejected.append(f"Plugin '{step.plugin}' is not allowed")
            continue

        target = (root / step.target).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            rejected.append(f"Target '{step.target}' is outside project root")

    return PlanResult(
        plan=plan,
        validated=len(rejected) == 0,
        rejected_steps=rejected,
    )


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


def _is_local_ollama(policy: Policy) -> bool:
    """Return True if the backend is Ollama pointed at localhost."""
    if policy.planner.backend != "ollama":
        return False
    url = policy.planner.base_url.lower()
    return "localhost" in url or "127.0.0.1" in url


class Planner:
    """Orchestrates LLM plan generation and policy validation."""

    def __init__(self, policy: Policy) -> None:
        self._policy = policy

    def _check_enabled(self) -> None:
        """Raise if the planner cannot run under the current policy."""
        if not self._policy.planner.enabled:
            raise PlannerDisabledError(
                "Planner is disabled in policy.yaml. Set planner.enabled: true to use this feature."
            )
        if not self._policy.allow_network and not _is_local_ollama(self._policy):
            raise PlanNetworkError(
                "Planner requires network access to reach the LLM API. "
                "Set allow_network: true or use a local Ollama instance."
            )

    def plan(self, task: str) -> ExecutionPlan:
        """Generate an execution plan for a natural-language task.

        Args:
            task: User's task description.

        Returns:
            A parsed ExecutionPlan.

        Raises:
            PlannerDisabledError: If planner is not enabled.
            PlanNetworkError: If network access is needed but denied.
            PlanParseError: If the LLM returns invalid JSON.
            PlanConnectionError: If the backend is unreachable.
        """
        self._check_enabled()

        system = _SYSTEM_PROMPT_TEMPLATE.format(
            plugins=", ".join(self._policy.allowed_plugins),
            root=self._policy.project_root,
            network=self._policy.allow_network,
            shell=self._policy.allow_shell,
            max_steps=self._policy.planner.max_steps,
        )

        backend = get_backend(self._policy)

        write_audit(
            self._policy.root_path(),
            AuditEvent(action="planner", status="request", detail=f"Task: {task}"),
        )

        raw = backend.call(self._policy, system, task)
        plan = _parse_plan_json(raw)

        write_audit(
            self._policy.root_path(),
            AuditEvent(
                action="planner",
                status="ok",
                detail=f"Generated {len(plan.steps)} step(s)",
            ),
        )

        return plan
