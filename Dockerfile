FROM ghcr.io/astral-sh/uv:0.13.1 AS uv
FROM python:3.12.13-slim-bookworm

COPY --from=uv /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_NO_CACHE=1 \
    PATH="/workspace/.venv/bin:${PATH}"

RUN useradd --create-home --uid 10001 appuser \
    && mkdir /workspace \
    && chown appuser:appuser /workspace
WORKDIR /workspace
USER appuser

COPY --chown=appuser:appuser . .
RUN uv sync --locked --no-dev --no-editable

CMD ["python", "scripts/build_master.py"]
