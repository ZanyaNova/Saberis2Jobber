# Dockerfile

# --- Stage 1: Build Stage ---
# Use an official Python runtime as a parent image
FROM python:3.11-slim AS builder

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# --no-cache-dir ensures we don't store the download cache, keeping the image small
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Final Stage ---
# Use a smaller, non-root user base image for security
FROM python:3.11-slim

# Set the working directory for the final stage
WORKDIR /app

# Create a non-root user and group
RUN addgroup --system app && adduser --system --group app

# Switch to the non-root user
USER app

# Copy the installed packages and binaries from the builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application source code into a 'src' directory inside /app
COPY src/ /app/src/

# Tell Docker that the container will listen on this port
EXPOSE 8080

# Define the command to run your app using Gunicorn
# This tells Gunicorn to look for the 'app' object in the 'main' module inside the 'src' package.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "src.main:app"]