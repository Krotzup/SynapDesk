FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend:/app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
# El perfil ligero no instala torch. Para IA usar una imagen que incluya este extra.
ARG INCLUDE_ML=0
COPY ml/requirements.txt ml/requirements-semantic.txt /app/ml/
RUN if [ "$INCLUDE_ML" = "1" ]; then pip install --no-cache-dir -r ml/requirements.txt -r ml/requirements-semantic.txt; fi
COPY backend/app /app/backend/app
COPY backend/alembic.ini /app/backend/alembic.ini
COPY backend/migraciones /app/backend/migraciones
COPY ml /app/ml
COPY infra/render/start_backend.py /app/start_backend.py
RUN useradd --create-home synapdesk
USER synapdesk
EXPOSE 10000
CMD ["python", "/app/start_backend.py"]
