# syntax=docker/dockerfile:1.7
FROM node:24-alpine AS web-build

WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --ignore-scripts
COPY web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="Rivulet LocalOps public demo" \
      org.opencontainers.image.description="Cloud-safe assurance console for predefined synthetic council-service scenarios" \
      org.opencontainers.image.source="https://github.com/Zeeekrom/rivulet-localops"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    RIVULET_DEMO_LEDGER_PATH=/tmp/rivulet/rivulet-demo.sqlite3

WORKDIR /app

RUN groupadd --gid 10001 rivulet \
    && useradd --uid 10001 --gid rivulet --no-create-home --shell /usr/sbin/nologin rivulet \
    && mkdir -p /tmp/rivulet \
    && chown rivulet:rivulet /tmp/rivulet

COPY requirements-runtime.lock ./
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --requirement requirements-runtime.lock

COPY data/hobart_litter_bins.geojson ./data/hobart_litter_bins.geojson
COPY data/agents/case_agent_v0.1.0.json ./data/agents/case_agent_v0.1.0.json
COPY data/policies/waste_litter_demo_v0.1.0.json ./data/policies/waste_litter_demo_v0.1.0.json
COPY data/mart/v1/build_report.json ./data/mart/v1/build_report.json
COPY --from=web-build /build/web/dist ./web/dist

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]

CMD ["python", "-m", "uvicorn", "rivulet_localops.public_demo:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
