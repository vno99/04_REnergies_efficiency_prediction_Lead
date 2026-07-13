# 1. Base Image
FROM python:3.12-slim

WORKDIR /home

# 2. System Dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 3. Copy Manifest
COPY requirements.txt .

# 4. INSTALLATION (With Debugging)
# We 'cat' the file to the build logs so you can SEE if pandas is listed.
RUN echo "===== CHECKING REQUIREMENTS =====" && \
    cat requirements.txt && \
    echo "=================================" && \
    pip install --no-cache-dir -r requirements.txt
RUN pip install --extra-index-url https://www.piwheels.org/simple pvlib

# 5. Copy Application Code
# COPY . .
COPY code/09_API/ /home/
# COPY code/09_API/tests/test_api.py /home/tests/test_api.py
# # COPY code/__init__.py /home/tests/__init__.py

# COPY code/09_API/app.py /home/app.py
# # COPY code/__init__.py /home/__init__.py

# 6. Runtime Config
ENV PYTHONPATH=/home
CMD ["python", "app/train.py"]