FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    tesseract-ocr-kan \
    tesseract-ocr-urd \
    tesseract-ocr-osd \
    libglib2.0-0 \
    libgl1 \
    fonts-noto-core \
    fonts-noto-extra \
    nginx \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/knowledge_base ./knowledge_base
COPY --from=web /web/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf.template
COPY deploy/start.sh /start.sh
RUN sed -i 's/\r$//' /start.sh && chmod +x /start.sh

ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/data \
    KNOWLEDGE_BASE_DIR=/app/knowledge_base \
    USE_LIGHT_EMBEDDINGS=true \
    EXTERNAL_AI_ENABLED=false \
    APP_ENV=production

EXPOSE 8080
CMD ["/start.sh"]
