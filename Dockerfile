FROM python:3.12-slim

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the application into the container.
WORKDIR /app

# deps first, for layer caching
COPY pyproject.toml uv.lock ./
COPY app ./app

# Install the application dependencies.
RUN uv sync --no-dev

ENV PATH="/.venv/bin:$PATH"

CMD ["uv", "run", "python", "-m", "app.api.local_api_run"]