FROM python:3.11
WORKDIR /app
COPY database/requirements.txt .
COPY utils/pb/ /app/utils/pb/
COPY database/src/ /app/database/src/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install tenacity==8.2.3
CMD ["python", "database/src/app.py"]