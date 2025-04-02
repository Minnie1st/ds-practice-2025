FROM python:3.11
WORKDIR /app
COPY order_executor/requirements.txt .
COPY utils/pb/ /app/utils/pb/
COPY order_executor/src/ /app/order_executor/src/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install tenacity==8.2.3
CMD ["python", "order_executor/src/app.py"]