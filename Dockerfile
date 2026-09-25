# Stage 1: build the web interface.
FROM node:22-slim AS web
WORKDIR /app/web
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

# Stage 2: the server, with the built interface inside.
FROM python:3.12-slim
RUN pip install --no-cache-dir uv && useradd --create-home --uid 1000 katib
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev --extra postgres
COPY --from=web /app/src/katib/static ./src/katib/static

ENV PATH="/app/.venv/bin:$PATH" \
    KATIB_SERVER__HOST=0.0.0.0 \
    KATIB_AUTH__MODE=local \
    KATIB_STORAGE__DATA_DIR=/data
RUN mkdir /data && chown katib /data
USER katib
VOLUME /data
EXPOSE 8420
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8420/api/v1/health')"
CMD ["katib", "serve"]
