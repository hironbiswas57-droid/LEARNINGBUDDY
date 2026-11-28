FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    LEARNMATE_ENV=production \
    DATABASE_PATH=/app/data/learnmate.db

WORKDIR /app
COPY . .
RUN useradd --create-home --uid 10001 learnmate \
    && mkdir -p /app/data \
    && chown -R learnmate:learnmate /app
USER learnmate

EXPOSE 8000
CMD ["python", "-m", "learnmate"]
