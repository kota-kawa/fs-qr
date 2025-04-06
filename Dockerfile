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

# Create logs directory and set permissions
RUN mkdir -p /app/logs && chmod -R 777 /app/logs

# Expose port 5000 for Gunicorn app
EXPOSE 5000

# Run Gunicorn app when the container launches
CMD ["/usr/local/bin/wait-for-it", "db:3306", "--", "gunicorn", "-b", "0.0.0.0:5000", "--timeout", "360", "--access-logfile", "/app/logs/access.log", "--error-logfile", "/app/logs/error.log", "app:app"]

########## デバッグ用の実行 ##############
# Flask の環境変数を設定（run.py がエントリーポイントの場合）
#ENV FLASK_APP=app.py
#ENV FLASK_ENV=development
#CMD ["flask", "run", "--host=0.0.0.0", "--port=5000", "--reload"]