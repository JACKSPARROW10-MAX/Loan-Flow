FROM python:3.11-slim
WORKDIR /app
COPY services/requirements-base.txt /app/requirements-base.txt
RUN pip install --no-cache-dir -r requirements-base.txt
COPY services/shared /app/shared
COPY services/loan_app /app/loan_app
EXPOSE 8002
CMD ["uvicorn", "loan_app.main:app", "--host", "0.0.0.0", "--port", "8002"]
