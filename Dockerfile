# A imagem é Linux mesmo quando construída pelo Docker Desktop no Windows.
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY src/netsentinel/api/templates/ /app/src/netsentinel/api/templates/
COPY src/netsentinel/api/static/ /app/src/netsentinel/api/static/
# evidence-corpus.test.mjs lê o mesmo JSON que o teste Python (ADR 0006).
COPY tests/fixtures/evidence_cases.json /app/tests/fixtures/evidence_cases.json
RUN npm test && npm run build

FROM python:3.12-slim-bookworm AS python-build
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY --from=frontend-build /app/src/netsentinel/api/static/ ./src/netsentinel/api/static/
# Instalação editable preserva o caminho /app das migrações existentes.
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -e .

FROM python:3.12-slim-bookworm AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080
WORKDIR /app
# ip é usado pelo preflight do Sensor; o modo sintético não o executa.
# nftables pertence ao agente na Vítima, não ao backend desta imagem.
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 netsentinel \
    && useradd --uid 10001 --gid netsentinel --no-create-home netsentinel
COPY --from=python-build /opt/venv /opt/venv
COPY --from=python-build /app /app
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY deploy/start-container.sh ./deploy/start-container.sh
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
  CMD ["python", "-c", "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/health', timeout=3).read()"]
CMD ["sh", "/app/deploy/start-container.sh"]
