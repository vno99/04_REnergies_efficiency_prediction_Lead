FROM apache/airflow:3.1.0-python3.12

# Install your packages as the airflow user (not root)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt