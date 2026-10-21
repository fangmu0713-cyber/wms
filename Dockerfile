FROM python:3.12.14-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 WMS_DB_PATH=/data/wms.sqlite3
WORKDIR /srv/wms
COPY requirements.lock ./
COPY wheelhouse /tmp/wheels
ARG WMS_OFFLINE=0
RUN if [ "$WMS_OFFLINE" = "1" ]; then pip install --no-cache-dir --no-index --find-links=/tmp/wheels -r requirements.lock; else pip install --no-cache-dir -r requirements.lock; fi \
    && rm -rf /tmp/wheels \
    && groupadd --gid 10001 wms && useradd --uid 10001 --gid 10001 --no-create-home wms \
    && mkdir /data && chown 10001:10001 /data
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 scripts/entrypoint.sh /srv/wms/entrypoint.sh
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]
ENTRYPOINT ["sh", "/srv/wms/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--no-proxy-headers"]
