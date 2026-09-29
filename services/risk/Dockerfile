FROM python:3.11-slim
WORKDIR /app
COPY services/requirements-base.txt /app/requirements-base.txt
RUN pip install --no-cache-dir -r requirements-base.txt
COPY services/shared /app/shared
COPY services/risk /app/risk
RUN pip install --no-cache-dir numpy scikit-learn
EXPOSE 8005
CMD ["uvicorn", "risk.main:app", "--host", "0.0.0.0", "--port", "8005"]
