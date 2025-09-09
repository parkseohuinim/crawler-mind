# MCP Server Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 필수 패키지 설치 + playwright + chromium 브라우저 설치
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc g++ libpq-dev curl wget gnupg \
       libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libxcomposite1 \
       libxdamage1 libxrandr2 libgbm1 libxss1 libasound2 \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir playwright \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./mcp-server/ .

# non-root 유저 생성
RUN adduser --disabled-password --gecos '' appuser \
    && mkdir -p /home/appuser/.cache \
    && chown -R appuser:appuser /app /home/appuser

USER appuser

EXPOSE 4200

# 이제는 playwright 설치 필요 없음
CMD ["python", "server.py"]
