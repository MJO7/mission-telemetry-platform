# syntax=docker/dockerfile:1
#
# Multi-stage: build the venv with uv (see macos-pip-venv-bug memory --
# same tool, different reason here: reproducible, fast, no compiler
# toolchain needed for this project's deps), then copy only the
# runtime artifacts into a fresh slim image so the final image doesn't
# carry uv itself, pip's cache, or any build-only layer weight.
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN uv venv .venv && uv pip install --python .venv/bin/python .

FROM python:3.12-slim
# Non-root: a k8s SecurityContext can enforce runAsNonRoot against this
# UID; a container that can only ever run as some non-zero UID doesn't
# depend on the cluster operator remembering to set one.
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/app ./app
COPY --from=builder /app/alembic ./alembic
COPY --from=builder /app/alembic.ini ./
ENV PATH="/app/.venv/bin:${PATH}"
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
