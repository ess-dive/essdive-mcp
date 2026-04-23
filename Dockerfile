FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md /app/
COPY src /app/src
COPY .agents /app/.agents

RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["essdive-mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000", "--path", "/mcp"]
