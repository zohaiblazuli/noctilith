# Container for hosting (Hugging Face Spaces, or any Docker host).
# Runs next to NASA's data in the US, so frames load in seconds instead of minutes.
FROM python:3.12-slim

RUN useradd -m -u 1000 user
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user server server
COPY --chown=user web web
COPY --chown=user scripts scripts

USER user
# The free disk is wiped on restart; the cache just refills from NASA.
ENV SPHEREX_CACHE_DIR=/tmp/spherex-cache \
    PYTHONUNBUFFERED=1

EXPOSE 7860
CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
