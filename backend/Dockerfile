# Use the official Python image as the base

FROM python:3.11-slim

# Set environment variables

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory

WORKDIR /app

# Copy dependency files and install Python dependencies

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

Copy the rest of the application code

COPY . /app/

# Expose the port the application will run on

EXPOSE 8000

# Command to run the application using Gunicorn

# 0.0.0.0 is necessary to listen on all interfaces inside the container

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "jar_repo.wsgi:application"]