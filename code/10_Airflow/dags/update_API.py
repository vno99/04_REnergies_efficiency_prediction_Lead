from airflow import DAG
# from airflow.operators.python import PythonOperator
# from airflow.operators.bash import BashOperator
from airflow.providers.standard.operators.python import PythonOperator
from airflow.providers.standard.operators.bash import BashOperator
from datetime import datetime, timedelta
import shutil
import os

# ============================================================
# CONFIGURATION — edit only this section
# ============================================================
GIT_FOLDER       = '/opt/airflow/git-repo'
API_FOLDER       = '/code/09_API'
HF_FOLDER        = '/opt/airflow/hf-folder'
GIT_BRANCH       = 'main'
HF_BRANCH        = 'main'
# HF_TOKEN         = 'hf_xxxxxxxxxxxxxxxxxxxx'
HF_REMOTE_URL    = 'https://huggingface.co/your-username/your-repo'
COMMIT_MESSAGE   = 'Sync from API repo [automated]'
AIRFLOW_OWNER    = 'airflow'
RETRIES          = 1
RETRY_DELAY_MIN  = 5
# ============================================================

default_args = {
    'owner': AIRFLOW_OWNER,
    'retries': RETRIES,
    'retry_delay': timedelta(minutes=RETRY_DELAY_MIN),
}

with DAG(
    dag_id='sync_api_to_huggingface',
    default_args=default_args,
    schedule=None, #Only on trigger
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['huggingface', 'deploy'],
) as dag:

    pull_git = BashOperator(
        task_id='pull_git_repo',
        bash_command=f"cd {GIT_FOLDER} && git pull origin {GIT_BRANCH}"
    )

    def copy_files(src=GIT_FOLDER+API_FOLDER, dst=HF_FOLDER):
        for item in os.listdir(dst):
            if item == '.git':
                continue
            s = os.path.join(dst, item)
            shutil.rmtree(s) if os.path.isdir(s) else os.remove(s)

        for item in os.listdir(src):
            if item == '.git':
                continue
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            shutil.copytree(s, d) if os.path.isdir(s) else shutil.copy2(s, d)

        print("Files copied successfully.")

    copy_task = PythonOperator(
        task_id='copy_files_to_hf_folder',
        python_callable=copy_files,
    )

    # push_to_hf = BashOperator(
    #     task_id='push_to_huggingface',
    #     bash_command=f"""
    #         cd {HF_FOLDER} && \
    #         git remote set-url origin https://USER:{HF_TOKEN}@{HF_REMOTE_URL.replace('https://', '')} && \
    #         git add -A && \
    #         git diff --cached --quiet || git commit -m "{COMMIT_MESSAGE}" && \
    #         git push origin {HF_BRANCH}
    #     """
    # )

    pull_git >> copy_task #>> push_to_hf