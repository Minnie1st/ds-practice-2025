FROM python:3.11
WORKDIR /app
COPY payment_service/requirements.txt .
COPY utils/pb/ /app/utils/pb/
COPY payment_service/src/ /app/payment_service/src/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install tenacity==8.2.3
CMD ["python", "payment_service/src/app.py"]