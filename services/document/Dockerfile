FROM python:3.11-slim
WORKDIR /app
COPY services/requirements-base.txt /app/requirements-base.txt
RUN pip install --no-cache-dir -r requirements-base.txt
COPY services/shared /app/shared
COPY services/document /app/document
EXPOSE 8003
CMD ["uvicorn", "document.main:app", "--host", "0.0.0.0", "--port", "8003"]
