FROM python:3.11-slim

# Set working directory
WORKDIR /backend

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Create notebook output directory and set permissions
RUN mkdir -p /notebook_output && chmod -R 755 /notebook_output

# Copy app code
COPY . .

# Expose FastAPI port
EXPOSE 7000

# Run the app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7000"]