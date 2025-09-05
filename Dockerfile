FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY uv.lock pyproject.toml ./

RUN uv sync --frozen --no-install-project

COPY . .

RUN uv sync --frozen

RUN uv run python -m grpc_tools.protoc \
-I proto \
--python_out=gen \
--grpc_python_out=gen \
$(find proto -name "*.proto")

FROM python:3.13-slim AS production

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
