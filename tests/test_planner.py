"""Tests for safeclaw.planner."""

from __future__ import annotations

from pathlib import Path

import pytest

from safeclaw.planner import (
    ExecutionPlan,
    PlanConnectionError,
    Planner,
    PlannerDisabledError,
    PlanNetworkError,
    PlanParseError,
    PlanStep,
    _parse_plan_json,
    get_backend,
    validate_plan,
)
from safeclaw.policy import PlannerConfig, Policy

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def planner_policy(tmp_path: Path) -> Policy:
    """Policy with planner enabled and Ollama localhost backend."""
    return Policy(
        project_root=str(tmp_path),
        allow_network=False,
        allowed_plugins=["todo_scan", "secrets_scan", "repo_stats"],
        planner=PlannerConfig(
            enabled=True,
            backend="ollama",
            base_url="http://localhost:11434",
            max_steps=5,
        ),
    )


# ---------------------------------------------------------------------------
# Plan validation
# ---------------------------------------------------------------------------


class TestValidatePlan:
    def test_valid_plan(self, planner_policy: Policy) -> None:
        plan = ExecutionPlan(
            steps=[
                PlanStep(plugin="todo_scan", target="./", reason="scan"),
                PlanStep(plugin="secrets_scan", target="./", reason="check"),
            ]
        )
        result = validate_plan(plan, planner_policy)
        assert result.validated is True
        assert result.rejected_steps == []

    def test_disallowed_plugin_rejected(self, planner_policy: Policy) -> None:
        plan = ExecutionPlan(steps=[PlanStep(plugin="evil_plugin", target="./", reason="hack")])
        result = validate_plan(plan, planner_policy)
        assert result.validated is False
        assert any("evil_plugin" in r for r in result.rejected_steps)

    def test_target_outside_root_rejected(self, planner_policy: Policy) -> None:
        plan = ExecutionPlan(
            steps=[PlanStep(plugin="todo_scan", target="/etc/passwd", reason="read")]
        )
        result = validate_plan(plan, planner_policy)
        assert result.validated is False
        assert any("outside project root" in r for r in result.rejected_steps)

    def test_exceeds_max_steps_rejected(self, planner_policy: Policy) -> None:
        steps = [PlanStep(plugin="todo_scan", target="./", reason=f"step{i}") for i in range(10)]
        plan = ExecutionPlan(steps=steps)
        result = validate_plan(plan, planner_policy)
        assert result.validated is False
        assert any("max" in r.lower() for r in result.rejected_steps)

    def test_empty_plan_valid(self, planner_policy: Policy) -> None:
        plan = ExecutionPlan(steps=[])
        result = validate_plan(plan, planner_policy)
        assert result.validated is True


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------


class TestParsePlanJson:
    def test_valid_json(self) -> None:
        raw = '{"steps": [{"plugin": "todo_scan", "target": "./", "reason": "scan"}]}'
        plan = _parse_plan_json(raw)
        assert len(plan.steps) == 1
        assert plan.steps[0].plugin == "todo_scan"

    def test_json_with_markdown_fences(self) -> None:
        raw = '```json\n{"steps": [{"plugin": "todo_scan", "target": "./"}]}\n```'
        plan = _parse_plan_json(raw)
        assert len(plan.steps) == 1

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(PlanParseError, match="Invalid JSON"):
            _parse_plan_json("not json at all")

    def test_empty_response_raises(self) -> None:
        with pytest.raises(PlanParseError, match="empty"):
            _parse_plan_json("")

    def test_missing_steps_key_raises(self) -> None:
        with pytest.raises(PlanParseError, match="steps"):
            _parse_plan_json('{"actions": []}')

    def test_raw_response_preserved_on_error(self) -> None:
        with pytest.raises(PlanParseError) as exc_info:
            _parse_plan_json("broken json {{{")
        assert exc_info.value.raw_response == "broken json {{{"


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


class TestBackendSelection:
    def test_ollama_backend(self, planner_policy: Policy) -> None:
        backend = get_backend(planner_policy)
        assert type(backend).__name__ == "_OllamaBackend"

    def test_openai_backend(self, tmp_path: Path) -> None:
        pol = Policy(
            project_root=str(tmp_path),
            planner=PlannerConfig(enabled=True, backend="openai"),
        )
        backend = get_backend(pol)
        assert type(backend).__name__ == "_OpenAIBackend"

    def test_anthropic_backend(self, tmp_path: Path) -> None:
        pol = Policy(
            project_root=str(tmp_path),
            planner=PlannerConfig(enabled=True, backend="anthropic"),
        )
        backend = get_backend(pol)
        assert type(backend).__name__ == "_AnthropicBackend"


# ---------------------------------------------------------------------------
# Planner policy checks
# ---------------------------------------------------------------------------


class TestPlannerPolicyChecks:
    def test_disabled_planner_raises(self, tmp_path: Path) -> None:
        pol = Policy(
            project_root=str(tmp_path),
            planner=PlannerConfig(enabled=False),
        )
        planner = Planner(pol)
        with pytest.raises(PlannerDisabledError):
            planner.plan("do something")

    def test_network_denied_non_local_raises(self, tmp_path: Path) -> None:
        pol = Policy(
            project_root=str(tmp_path),
            allow_network=False,
            planner=PlannerConfig(
                enabled=True,
                backend="openai",
            ),
        )
        planner = Planner(pol)
        with pytest.raises(PlanNetworkError):
            planner.plan("do something")

    def test_local_ollama_allowed_without_network(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ollama on localhost should work even when allow_network is False."""
        from safeclaw.planner import _OllamaBackend

        def mock_call(self, policy, system, user_msg):  # noqa: ARG001
            raise PlanConnectionError("mocked: Ollama not reachable")

        monkeypatch.setattr(_OllamaBackend, "call", mock_call)

        pol = Policy(
            project_root=str(tmp_path),
            allow_network=False,
            planner=PlannerConfig(
                enabled=True,
                backend="ollama",
                base_url="http://localhost:11434",
            ),
        )
        planner = Planner(pol)
        # Should not raise PlanNetworkError — it will fail with connection
        # error from the mocked backend, proving the policy check passed.
        with pytest.raises(PlanConnectionError):
            planner.plan("do something")


# ---------------------------------------------------------------------------
# Mock HTTP calls
# ---------------------------------------------------------------------------


class TestPlannerWithMockedBackend:
    def test_plan_success(self, planner_policy: Policy, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_response = '{"steps": [{"plugin": "todo_scan", "target": "./", "reason": "scan"}]}'

        def mock_call(self, policy, system, user_msg):  # noqa: ARG001
            return mock_response

        from safeclaw.planner import _OllamaBackend

        monkeypatch.setattr(_OllamaBackend, "call", mock_call)

        planner = Planner(planner_policy)
        plan = planner.plan("scan for issues")
        assert len(plan.steps) == 1
        assert plan.steps[0].plugin == "todo_scan"

    def test_plan_invalid_json_from_llm(
        self, planner_policy: Policy, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def mock_call(self, policy, system, user_msg):  # noqa: ARG001
            return "I can't do that, Dave."

        from safeclaw.planner import _OllamaBackend

        monkeypatch.setattr(_OllamaBackend, "call", mock_call)

        planner = Planner(planner_policy)
        with pytest.raises(PlanParseError):
            planner.plan("do something")

    def test_plan_empty_steps(
        self, planner_policy: Policy, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LLM returns a valid plan with no steps."""

        def mock_call(self, policy, system, user_msg):  # noqa: ARG001
            return '{"steps": []}'

        from safeclaw.planner import _OllamaBackend

        monkeypatch.setattr(_OllamaBackend, "call", mock_call)

        planner = Planner(planner_policy)
        plan = planner.plan("nothing to do")
        assert plan.steps == []

    def test_audit_written_after_plan(
        self, planner_policy: Policy, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Audit log should be written after a successful plan."""

        def mock_call(self, policy, system, user_msg):  # noqa: ARG001
            return '{"steps": [{"plugin": "todo_scan", "target": "./", "reason": "scan"}]}'

        from safeclaw.planner import _OllamaBackend

        monkeypatch.setattr(_OllamaBackend, "call", mock_call)

        from safeclaw.audit import read_audit

        planner = Planner(planner_policy)
        planner.plan("scan for issues")

        entries = read_audit(planner_policy.root_path(), last_n=10)
        planner_entries = [e for e in entries if e.get("action") == "planner"]
        assert len(planner_entries) >= 2
        statuses = {e["status"] for e in planner_entries}
        assert "request" in statuses
        assert "ok" in statuses

    def test_plan_with_multiple_steps(
        self, planner_policy: Policy, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Plan with multiple valid steps."""
        raw = (
            '{"steps": ['
            '{"plugin": "todo_scan", "target": "./", "reason": "scan todos"},'
            '{"plugin": "secrets_scan", "target": "./", "reason": "check secrets"},'
            '{"plugin": "repo_stats", "target": "./", "reason": "stats"}'
            "]}"
        )

        def mock_call(self, policy, system, user_msg):  # noqa: ARG001
            return raw

        from safeclaw.planner import _OllamaBackend

        monkeypatch.setattr(_OllamaBackend, "call", mock_call)

        planner = Planner(planner_policy)
        plan = planner.plan("full scan")
        assert len(plan.steps) == 3
        assert [s.plugin for s in plan.steps] == ["todo_scan", "secrets_scan", "repo_stats"]


class TestUnknownBackend:
    def test_unknown_backend_raises(self, tmp_path: Path) -> None:
        from safeclaw.planner import PlannerError

        pol = Policy(
            project_root=str(tmp_path),
            planner=PlannerConfig(enabled=True, backend="unknown_backend"),
        )
        with pytest.raises(PlannerError, match="Unknown planner backend"):
            get_backend(pol)
