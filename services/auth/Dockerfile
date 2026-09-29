FROM python:3.11-slim

WORKDIR /app

# Install shared deps
COPY services/requirements-base.txt /app/requirements-base.txt
RUN pip install --no-cache-dir -r requirements-base.txt

# Copy shared library
COPY services/shared /app/shared

# Copy service code
COPY services/auth /app/auth

WORKDIR /app/auth
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
