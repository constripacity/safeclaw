# SafeClaw — multi-stage Docker build
# Usage:
#   docker build -t safeclaw .
#   docker run safeclaw todo /project
#   docker run -p 8321:8321 -v $(pwd):/project safeclaw dashboard

# --- Builder stage ---
FROM python:3.11-slim AS builder

WORKDIR /build
COPY pyproject.toml .
COPY safeclaw/ safeclaw/

RUN pip install --no-cache-dir --prefix=/install .

# --- Runtime stage ---
FROM python:3.11-slim

# Non-root user
RUN useradd --create-home --shell /bin/bash safeclaw
WORKDIR /project

COPY --from=builder /install /usr/local
COPY policy.yaml /project/policy.yaml

USER safeclaw

EXPOSE 8321

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8321/health')" || exit 1

ENTRYPOINT ["safeclaw"]
CMD ["--help"]
