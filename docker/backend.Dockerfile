# Compose build.args：.env 里的 DOCKER_PYTHON_IMAGE、DEBIAN_REPO_MIRROR（Debian apt 镜像主机前缀）
ARG PYTHON_IMAGE=python:3.12-slim-bookworm
FROM ${PYTHON_IMAGE}

ARG DEBIAN_REPO_MIRROR=http://deb.debian.org
ENV DEBIAN_FRONTEND=noninteractive

# Debian CDN 偶有 502；国内可将 DEBIAN_REPO_MIRROR 设为 http://mirrors.aliyun.com 等（仅主机名前缀，镜像内会替换 deb.debian.org）
RUN set -eu; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i "s|http://deb.debian.org|${DEBIAN_REPO_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    elif [ -f /etc/apt/sources.list ]; then \
      sed -i "s|http://deb.debian.org|${DEBIAN_REPO_MIRROR}|g" /etc/apt/sources.list; \
    fi; \
    apt_ok=0; \
    for attempt in 1 2 3 4 5; do \
      if apt-get update \
        && apt-get install -y --no-install-recommends \
          -o Acquire::Retries=5 \
          -o Acquire::http::Timeout=120 \
          build-essential \
          curl; then \
        apt_ok=1; break; \
      fi; \
      echo "apt attempt $$attempt failed, retrying..."; \
      sleep 25; \
    done; \
    test "${apt_ok}" -eq 1; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY backend/requirements.txt /workspace/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /workspace/backend/requirements.txt

COPY backend /workspace/backend

WORKDIR /workspace/backend

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
