import boto3
import time
import requests
import base64
import os
import paramiko
import io
from datetime import datetime, timedelta
import logging
from airflow.sdk import task
from airflow.models.dag import DAG
from airflow.providers.amazon.aws.operators.ec2 import (
    EC2CreateInstanceOperator,
    EC2TerminateInstanceOperator,
)
from airflow.task.trigger_rule import TriggerRule

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------

# GitHub Config
GITHUB_REPO = os.getenv("GITHUB_REPO") 
# User changed env var name to GITHUB_PAT, updating here:
GITHUB_TOKEN = os.getenv("GITHUB_PAT") 
BRANCH_NAME = "main"

# AWS Config
KEY_PAIR_NAME = os.getenv("KEY_PAIR_NAME") 
AMI_ID = os.getenv("AMI_ID", "ami-00ac45f3035ff009e") 
SECURITY_GROUP_ID = os.getenv("SECURITY_GROUP_ID")
INSTANCE_TYPE = os.getenv("INSTANCE_TYPE", "t3.small")

# Connection (Direct Env Vars)
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
REGION_NAME = os.getenv("AWS_DEFAULT_REGION", "eu-west-3")

# MLFlow Config
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI")
MLFLOW_EXPERIMENT_NAME = os.getenv("MLFLOW_EXPERIMENT_NAME", "california_housing")

# User Data (Install Docker + MLflow)
USER_DATA_SCRIPT = """#!/bin/bash
# 1. Redirect all output to a dedicated log file for easy debugging
exec > /var/log/user-data-debug.log 2>&1
set -x # Print every command before executing

echo "--> STARTING SETUP"

# 2. Prevent apt-get from asking questions
export DEBIAN_FRONTEND=noninteractive

# 3. Install System Dependencies
echo "--> Installing Apt Packages..."
apt-get update
apt-get install -y docker.io git python3-pip python3-venv

# 4. Configure Docker
echo "--> Configuring Docker..."
systemctl start docker
systemctl enable docker
usermod -aG docker ubuntu
# Ensure socket is ready before chmod
while [ ! -S /var/run/docker.sock ]; do echo "Waiting for Docker Socket..."; sleep 1; done
chmod 666 /var/run/docker.sock

# 5. Install MLflow (The dangerous part)
echo "--> Installing Python Libs..."
# BYPASS UBUNTU PROTECTIONS
sudo -u ubuntu pip3 install mlflow boto3 --break-system-packages

# This makes 'mlflow' callable from anywhere, even non-interactive shells.
ln -s /home/ubuntu/.local/bin/mlflow /usr/bin/mlflow

# 6. Signal Success
echo "--> SETUP COMPLETE"
touch /tmp/airflow_ready
"""

def load_api_data(url, data_type):
    logging.info(f"LOAD {data_type}")

    max_retries = 3
    wait = 1

    for _ in range(max_retries):

        try:
            response = requests.get(url)
            response.raise_for_status()

            logging.info(response.content)
            break

        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", wait))
                logging.error(f"Error 429. Wait for {retry_after} seconds...")
                time.sleep(retry_after)
                wait *= 2
            else:
                raise

    else:
        logging.error("Failure after {max_retries} retries")

DAG_ID = 'Prediction_data_update'
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

with DAG(
    dag_id=DAG_ID,
    schedule="0 5 * * *",  # everyday at 5 am
    default_args=default_args,
    catchup=False,
    tags=['API', 'data', 'prediction'],
) as dag:

    # ------------------------------------------------------------------
    # TASK 1: Update Prediction weather data
    # ------------------------------------------------------------------
    @task
    def update_weather_data():
        load_api_data("https://renergies99lead-api-renergy-lead.hf.space/load_openweathermap_forecasts", "OPENWEATHERMAP FORECASTS")


        # ------------------------------------------------------------------
    # TASK 2: Update Prediction solar data
    # ------------------------------------------------------------------
    @task
    def update_solar_data():
        load_api_data("https://renergies99lead-api-renergy-lead.hf.space/load_solar_data", "SOLAR FORECAST")


            # ------------------------------------------------------------------
    # TASK 3: Perform a prediction based on the newly loaded data
    # ------------------------------------------------------------------
    @task
    def generate_predict():
        predi_last_download_response = requests.get("https://renergies99lead-api-renergy-lead.hf.space/predi_last_download")
        if predi_last_download_response.json() == datetime.now().strftime("%Y-%m-%d"):
            return "Prediction data is already downloaded today"

        urls = [
            "https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/solar/predi_data.csv",
            "https://renergies99-lead-bucket.s3.eu-west-3.amazonaws.com/public/openweathermap/openweathermap_forecasts.csv"
        ]

        payload = {"urls": urls}

        data = requests.post("https://renergies99lead-api-renergy-lead.hf.space/prep_data", json=payload)
        json_data = data.json()
        print("json_data", json_data)

        response = requests.post("https://renergies99lead-api-renergy-lead.hf.space/predict")
        print("response.content", response.content)

            # ------------------------------------------------------------------
    # FLOW DEFINITION
    # ------------------------------------------------------------------

    # 1. Updating the two data sources: weather and solar
    updating_weather_data = update_weather_data()

    updating_solar_data = update_solar_data()

    # 2. Prediction based on the newly updated data
    nostradamus = generate_predict()

    # 3. Definition of the explicit Execution order
    [updating_weather_data, updating_solar_data] >> nostradamus

    

    