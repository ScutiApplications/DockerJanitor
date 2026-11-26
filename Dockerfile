FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/src PATH=/app/.venv/bin:$PATH
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-cache
COPY src ./src
COPY web ./web
EXPOSE 26510
HEALTHCHECK --interval=15s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:26510/health')"
CMD ["python", "-m", "janitor"]
