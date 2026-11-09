# Shareable *read-only* demo. No Earth Engine credentials, model weights, or inference in image.
FROM node:22-alpine AS ui
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS viewer
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SARSCOPE_PREVIEW=1 SARSCOPE_WORKSPACE=/tmp/sarscope
WORKDIR /app
COPY requirements-viewer.txt ./
RUN pip install --no-cache-dir -r requirements-viewer.txt
COPY backend/ ./backend/
COPY engine/ ./engine/
COPY evidence/ ./evidence/
COPY sample/ ./sample/
COPY serve.py ./
COPY --from=ui /app/frontend/dist/ ./frontend/dist/
RUN useradd --system --uid 10001 appuser
USER appuser
EXPOSE 8765
CMD ["python","serve.py","--preview","--host","0.0.0.0","--port","8765"]
