# 1. Base Image: Use an official, lightweight Python Linux image
FROM python:3.12-slim

# 2. Environment Variables: Optimize Python behavior for containers
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Work Directory: Set the default directory inside the container
WORKDIR /app

# 4. System Dependencies: Install OS-level packages (Crucial for PostgreSQL)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. Python Dependencies: Copy requirements first to leverage Docker caching
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# 6. Application Code: Copy the rest of your Django project into the container
COPY . /app/

# 7. Port: Expose the port your Django app will run on
EXPOSE 8000

# 8. Execution: The default command to start the server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]