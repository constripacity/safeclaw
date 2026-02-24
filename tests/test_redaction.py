"""Tests for safeclaw.redaction."""

from safeclaw.redaction import redact


class TestRedaction:
    def test_openai_key(self) -> None:
        text = "key=sk-1234567890abcdefghijklmnopqrstuvwxyz"
        assert "[REDACTED:OPENAI_KEY]" in redact(text)

    def test_anthropic_key(self) -> None:
        text = "key=sk-ant-abcdefghijklmnopqrstuvwxyz"
        assert "[REDACTED:ANTHROPIC_KEY]" in redact(text)

    def test_aws_key(self) -> None:
        text = "access=AKIAIOSFODNN7EXAMPLE"
        assert "[REDACTED:AWS_KEY]" in redact(text)

    def test_github_token(self) -> None:
        text = "token=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklm"
        assert "[REDACTED:GITHUB_TOKEN]" in redact(text)

    def test_github_pat(self) -> None:
        text = "pat=github_pat_ABCDEFGHIJKLMNOPQRSTUVWXYZab"
        assert "[REDACTED:GITHUB_PAT]" in redact(text)

    def test_bearer_token(self) -> None:
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        assert "[REDACTED:BEARER_TOKEN]" in redact(text)

    def test_private_key(self) -> None:
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIBog==\n-----END RSA PRIVATE KEY-----"
        assert "[REDACTED:PRIVATE_KEY]" in redact(text)

    def test_clean_text_unchanged(self) -> None:
        text = "This is a normal log message with no secrets."
        assert redact(text) == text

    def test_multiple_patterns(self) -> None:
        text = "sk-abcdefghijklmnopqrstuvwxyz and AKIAIOSFODNN7EXAMPLE"
        result = redact(text)
        assert "[REDACTED:OPENAI_KEY]" in result
        assert "[REDACTED:AWS_KEY]" in result
