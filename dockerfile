# Stage 1: Base build stage
FROM python:3.13-slim AS builder
 
# Create the app directory
RUN mkdir /app
 
# Set the working directory so `manage.py` in `src/` is used
WORKDIR /app
 
# Set environment variables to optimize Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 

# Install dependencies first for caching benefit
RUN pip install --upgrade pip 
COPY src/requirements.txt /app/ 
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2: Production stage
FROM python:3.13-slim

RUN useradd -m django-user && \
   mkdir /app && \
   chown -R django-user /app

# Copy the Python dependencies from the builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Set the working directory to /app
WORKDIR /app

# Copy only the application source into /app so manage.py is at /app/manage.py
COPY --chown=django-user:django-user src/ /app/
# Ensure the entrypoint from `src/` is placed at `/app/entrypoint.sh`
COPY --chown=django-user:django-user src/entrypoint.sh /app/entrypoint.sh

# Set environment variables to optimize Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1 

# Switch to the non-root user
USER django-user

# Final Prep
EXPOSE 8000 

# Make entry file executable
RUN chmod +x /app/entrypoint.sh

# Use ENTRYPOINT so the script always runs, and CMD for default arguments
ENTRYPOINT ["/app/entrypoint.sh"]