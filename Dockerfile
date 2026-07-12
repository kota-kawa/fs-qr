FROM python:3.14-slim-trixie AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt gunicorn


FROM python:3.14-slim-trixie

WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Keep the runtime image small and avoid carrying build-only packages such as
# linux-libc-dev into production, where Trivy scans the final image.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        libmagic1 \
        libmariadb3 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade system packaging tools shipped in the base image because Trivy scans
# their metadata even though the app itself runs from /opt/venv.
RUN /usr/local/bin/python -m pip install \
        --no-cache-dir \
        --root-user-action=ignore \
        --upgrade \
        pip \
        setuptools \
        wheel

COPY --from=builder /opt/venv /opt/venv

# Run as a non-root user. uid/gid 1000 must match the host user that owns the
# bind-mounted directories in docker-compose (./logs, ./geoip, source tree).
RUN groupadd --gid 1000 kota \
    && useradd --uid 1000 --gid 1000 --create-home --shell /usr/sbin/nologin kota

# Copy the current directory contents into the container at /app
COPY --chown=kota:kota . /app

# Add wait-for-it script for database readiness
COPY wait-for-it.sh /usr/local/bin/wait-for-it
RUN chmod +x /usr/local/bin/wait-for-it

# Writable runtime directories (logs, uploads, GeoIP DB updates)
RUN mkdir -p /app/logs /app/storage /app/geoip \
    && chown -R kota:kota /app/logs /app/storage /app/geoip /app/static

USER kota

# Expose port 5000 for Gunicorn app
EXPOSE 5000

# Run Gunicorn app when the container launches.
# Tunable settings live in gunicorn_conf.py (env-driven: WEB_CONCURRENCY,
# GUNICORN_MAX_REQUESTS, GUNICORN_TIMEOUT, ...).
CMD ["/usr/local/bin/wait-for-it", "db:3306", "--strict", "--timeout=120", "--", "gunicorn", "-c", "/app/gunicorn_conf.py", "app:app"]

########## デバッグ用の実行 ##############
# FastAPI のローカル実行例
#CMD ["uvicorn", "app:app", "--host=0.0.0.0", "--port=5000", "--reload"]
