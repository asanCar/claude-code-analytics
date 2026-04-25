FROM python:3.12-slim

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

ARG SUPERCRONIC_VERSION=0.2.33
ARG TARGETARCH
RUN ARCH=$(case "${TARGETARCH}" in "arm64") echo "linux-arm64" ;; *) echo "linux-amd64" ;; esac) && \
    curl -fsSL "https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-${ARCH}" \
    -o /usr/local/bin/supercronic && \
    chmod +x /usr/local/bin/supercronic

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
