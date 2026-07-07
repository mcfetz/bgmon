# syntax=docker/dockerfile:1

# =============================================================================
# Stage 1: Build frontend (Svelte 5 + Vite)
# =============================================================================
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend

# Install deps first for better layer caching
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Build static assets
COPY frontend/ ./
RUN npx svelte-kit sync && npm run build


# =============================================================================
# Stage 2: Install Python dependencies into a wheel-equivalent layout
# =============================================================================
FROM python:3.14-slim AS backend-deps
WORKDIR /app/backend

# libpq-dev + gcc are needed to build psycopg2-binary on slim images
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy build metadata first for layer caching
COPY backend/pyproject.toml backend/README.md* ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# Copy the actual source so editable install / package discovery works
COPY backend/ /app/backend/


# =============================================================================
# Stage 3: Production runtime
# =============================================================================
FROM python:3.14-slim AS runtime
WORKDIR /app/backend

# Runtime libs only (libpq5, no gcc)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash bgmon

# Reuse installed Python packages from the deps stage
COPY --from=backend-deps /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=backend-deps /usr/local/bin /usr/local/bin

# Copy backend source
COPY --from=backend-deps /app/backend /app/backend

# Copy built frontend assets and serve them via Flask static
COPY --from=frontend-build /app/frontend/dist /app/backend/bgmon_api/static/dist

# Drop privileges
RUN chown -R bgmon:bgmon /app
USER bgmon

EXPOSE 5000

# Health-check hits the unauthenticated /health endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl --fail --silent http://localhost:5000/health || exit 1

# Production WSGI server (gunicorn is in pyproject deps)
CMD ["gunicorn", "-c", "gunicorn.conf.py", "bgmon_api.app:app"]
