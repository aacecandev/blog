# syntax=docker/dockerfile:1

# Builder: Alpine + uv

FROM docker.io/python:3.11-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build deps + download uv binary directly (no ghcr.io auth needed)
RUN apk add --no-cache \
      ca-certificates tzdata curl \
      build-base libffi-dev openssl-dev && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv

# Create virtualenv and install dependencies with uv (much faster than pip)
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies with uv
RUN uv pip install \
    fastapi==0.111.0 \
    uvicorn[standard]==0.30.1 \
    boto3==1.34.162 \
    python-frontmatter==1.0.0 \
    PyYAML==6.0.1 \
    cachetools==5.3.3 \
    pydantic-settings==2.4.0 \
    python-dotenv==1.0.1

###############################
# Runtime: Alpine slim image  #
###############################
FROM docker.io/python:3.11-alpine AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime libs (no compilers)
RUN apk add --no-cache ca-certificates tzdata libffi openssl curl

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code and env
COPY . ./app

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
