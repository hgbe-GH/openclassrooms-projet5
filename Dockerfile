FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

WORKDIR /app

RUN apt-get update \
    && apt-get install --yes --no-install-recommends openssl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md alembic.ini ./
COPY alembic ./alembic
COPY openclassrooms_projet5 ./openclassrooms_projet5
COPY models ./models
COPY scripts ./scripts

RUN uv sync --frozen

EXPOSE 7860

CMD ["./scripts/start_api.sh"]
