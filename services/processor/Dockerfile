# syntax=docker/dockerfile:1
#
# Build context is the REPO ROOT, not services/processor -- this
# package is an install-time consumer of api-service's app.* package
# (models, Settings; see services/processor/README.md), the same way
# local dev does `uv pip install -e ../api-service`. A container image
# needs both source trees in the build context for that to resolve.
#
#   docker build -f services/processor/Dockerfile -t ... .
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
WORKDIR /build

COPY services/api-service ./api-service
COPY services/processor ./processor

# Plain (non-editable) installs on purpose here, unlike local dev's -e:
# a container image wants a fixed, portable installed copy in
# site-packages, not a symlink back to a source tree that may not even
# exist at the same path at runtime.
RUN uv venv /venv \
    && uv pip install --python /venv/bin/python ./api-service \
    && uv pip install --python /venv/bin/python ./processor

FROM python:3.12-slim
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder /venv /venv
ENV PATH="/venv/bin:${PATH}"
USER appuser
CMD ["python", "-m", "processor.main"]
