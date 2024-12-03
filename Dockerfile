FROM python:3.10-slim

# Set working directory and non-interactive environment
WORKDIR /usr/local/maas_wol_service/WOL
ENV DEBIAN_FRONTEND=noninteractive

# Copy project files and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
COPY . /usr/local/maas_wol_service

# Install necessary packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends && \
    apt-get install -y openssh-client wakeonlan curl jq uuid && \
    apt-get install -y iputils-ping && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir -r /tmp/requirements.txt && mkdir -p /var/log/maas/wol && rm -f /tmp/requirements.txt

# Expose necessary ports
EXPOSE 8080

# Start SSH service and run the Python application
CMD ["python3", "/usr/local/maas_wol_service/WOL/maas_webhook_2_5_4.py"]
