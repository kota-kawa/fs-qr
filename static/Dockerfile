# Use an official Python runtime as a parent image
FROM python:3.9

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 5000 for FastAPI app
EXPOSE 5000

# Run FastAPI app when the container launches
CMD ["uvicorn", "app:app", "--host=0.0.0.0", "--port=5000", "--reload"]
