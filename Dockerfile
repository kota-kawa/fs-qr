# Use an official Python runtime as a parent image
FROM python:3.9

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Add wait-for-it script for database readiness
COPY wait-for-it.sh /usr/local/bin/wait-for-it
RUN chmod +x /usr/local/bin/wait-for-it

# Expose port 5000 for Gunicorn app
EXPOSE 5000

# Run Gunicorn app when the container launches
#CMD ["/usr/local/bin/wait-for-it", "db:3306", "--", "gunicorn", "-b", "0.0.0.0:5000", "app:app"]
CMD ["/usr/local/bin/wait-for-it", "db:3306", "--", "gunicorn", "-b", "0.0.0.0:5000", "--access-logfile", "/app/logs/access.log", "--error-logfile", "/app/logs/error.log", "app:app"]