# Use an official Python runtime as the base image
FROM python:3.11

# Set the working directory in the container
# Both the utils and src folders will be mounted as volumes, please see docker-compose.yaml
WORKDIR /app

# Copy the requirements file to the working directory
COPY ./order_queue/requirements.txt .
COPY utils/pb/ /app/utils/pb/
COPY order_queue/src/ /app/order_queue/src/
# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set the command to run the application
CMD ["python", "order_queue/src/app.py"]