FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
ENV DATABASE_URL=sqlite:////app/data/myziel.db
VOLUME /app/data
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["sh", "-c", "alembic upgrade head && uvicorn myziel.main:app --factory --host 0.0.0.0 --port 8000 --proxy-headers"]
