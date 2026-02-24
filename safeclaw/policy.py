"""Policy engine — loads and validates policy.yaml with Pydantic."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator


class Limits(BaseModel):
    """Resource limits for plugin execution."""

    max_file_mb: int = 5
    max_files: int = 2000
    timeout_seconds: int = 30


class Policy(BaseModel):
    """Security policy governing SafeClaw behaviour.

    All permissions are DENIED by default. Only explicitly allowed
    actions are permitted.
    """

    project_root: str = "."
    sandbox_subdir: str = "AI_SANDBOX"
    allow_network: bool = False
    allow_shell: bool = False
    allowed_plugins: list[str] = []
    limits: Limits = Limits()

    @field_validator("allowed_plugins", mode="before")
    @classmethod
    def _deduplicate_plugins(cls, v: list[str]) -> list[str]:
        """Remove duplicate plugin names while preserving order."""
        seen: set[str] = set()
        result: list[str] = []
        for name in v:
            if name not in seen:
                seen.add(name)
                result.append(name)
        return result

    def root_path(self) -> Path:
        """Return the resolved project root path."""
        return Path(self.project_root).resolve()

    def sandbox_path(self) -> Path:
        """Return the resolved sandbox directory path."""
        return self.root_path() / self.sandbox_subdir


def load_policy(path: Path | str = "policy.yaml") -> Policy:
    """Load and validate a policy file.

    Args:
        path: Path to the YAML policy file.

    Returns:
        A validated Policy instance.

    Raises:
        FileNotFoundError: If the policy file does not exist.
        ValueError: If the policy file contains invalid configuration.
    """
    policy_path = Path(path)
    if not policy_path.exists():
        raise FileNotFoundError(f"Policy file not found: {policy_path}")

    text = policy_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)

    if data is None:
        raise ValueError(f"Policy file is empty: {policy_path}")
    if not isinstance(data, dict):
        raise ValueError(f"Policy file must contain a YAML mapping: {policy_path}")

    return Policy(**data)
