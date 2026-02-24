"""Secret stripping — regex-based redaction of sensitive values."""

from __future__ import annotations

import re

# Each pattern: (name, compiled regex)
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OPENAI_KEY", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("ANTHROPIC_KEY", re.compile(r"sk-ant-[A-Za-z0-9\-]{20,}")),
    ("AWS_KEY", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GITHUB_TOKEN", re.compile(r"ghp_[A-Za-z0-9]{36,}")),
    ("GITHUB_PAT", re.compile(r"github_pat_[A-Za-z0-9]{20,}")),
    ("BEARER_TOKEN", re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)),
    (
        "PRIVATE_KEY",
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----[\s\S]*?"
            r"-----END (?:RSA |EC |DSA )?PRIVATE KEY-----"
        ),
    ),
]


def redact(text: str) -> str:
    """Replace sensitive patterns in *text* with redaction markers.

    Args:
        text: The input string to sanitise.

    Returns:
        A copy of *text* with each secret replaced by
        ``[REDACTED:PATTERN_NAME]``.
    """
    for name, pattern in _PATTERNS:
        text = pattern.sub(f"[REDACTED:{name}]", text)
    return text


def get_pattern_names() -> list[str]:
    """Return the list of redaction pattern names.

    Useful for the secrets_scan plugin, which needs to report which
    pattern type was matched.
    """
    return [name for name, _ in _PATTERNS]


def get_patterns() -> list[tuple[str, re.Pattern[str]]]:
    """Return a copy of the ``(name, regex)`` pairs."""
    return list(_PATTERNS)
