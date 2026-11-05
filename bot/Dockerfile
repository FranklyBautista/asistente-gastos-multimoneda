# Imagen de producción del bot (Railway la construye con bot/ como directorio raíz).
# Sin `RUN --mount=type=cache`: Railway exige ids de caché con el id del servicio.

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Primero solo las dependencias: esta capa se reutiliza mientras no cambie uv.lock.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.12-slim
RUN useradd --create-home --uid 10001 bot
COPY --from=build --chown=bot:bot /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    ENV=prod \
    PORT=8080
USER bot
WORKDIR /app
EXPOSE 8080
# Forma exec: Python es el PID 1 y recibe el SIGTERM de cada redespliegue.
CMD ["python", "-m", "gastos.main"]
