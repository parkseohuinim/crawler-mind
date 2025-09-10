# MCP Server Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# 필수 패키지 설치 + playwright + chromium 설치 (root 권한)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       gcc g++ libpq-dev curl wget gnupg \
       libnss3 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libxcomposite1 \
       libxdamage1 libxrandr2 libgbm1 libxss1 libasound2 \
    && pip install --no-cache-dir --upgrade pip playwright \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./mcp-server/ .

# non-root 유저 생성 및 권한 부여
RUN adduser --disabled-password --gecos '' appuser \
    && mkdir -p /home/appuser/.cache ${PLAYWRIGHT_BROWSERS_PATH} \
    && chown -R appuser:appuser /app /home/appuser ${PLAYWRIGHT_BROWSERS_PATH}

# 이제부터는 appuser로 실행
USER appuser

EXPOSE 4200
CMD ["python", "server.py"]