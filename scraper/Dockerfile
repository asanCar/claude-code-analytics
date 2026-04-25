# FROM python:3.12-slim
FROM public.ecr.aws/docker/library/python:3.12-slim

RUN apt-get update && apt-get install -y curl tini && rm -rf /var/lib/apt/lists/*

ARG SUPERCRONIC_VERSION=0.2.33
RUN ARCH=$(uname -m | sed 's/aarch64/linux-arm64/' | sed 's/x86_64/linux-amd64/') && \
    curl -fsSL "https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-${ARCH}" \
    -o /usr/local/bin/supercronic && \
    chmod +x /usr/local/bin/supercronic

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["tini", "--"]
CMD ["/app/entrypoint.sh"]
