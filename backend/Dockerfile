FROM python:3.11-slim

# Set environment for Python
ENV PYTHONPATH=/backend
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /backend

COPY requirements.txt .

RUN pip install -r requirements.txt

# Create notebook output directory and set permissions
RUN mkdir -p /notebook_output && chmod -R 755 /notebook_output

# Copy app code
COPY . .

# Expose FastAPI port
EXPOSE 5000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
