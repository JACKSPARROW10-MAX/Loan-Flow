FROM python:3.11-slim
WORKDIR /app
COPY services/requirements-base.txt /app/requirements-base.txt
RUN pip install --no-cache-dir -r requirements-base.txt
COPY services/shared /app/shared
COPY services/mock_kyc /app/mock_kyc
EXPOSE 8004
CMD ["uvicorn", "mock_kyc.main:app", "--host", "0.0.0.0", "--port", "8004"]
