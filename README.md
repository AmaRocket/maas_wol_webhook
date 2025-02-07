# Webhook-based Wake-on-LAN (WoL) Service

This service provides a REST API to trigger Wake-on-LAN (WoL) and shutdown commands for machines. It can be used to remotely wake up or shut down machines in a network.

## Overview

The service exposes HTTP endpoints to:
1. **Check the status** of a machine (running or stopped).
2. **Send a Wake-on-LAN packet** to wake up a machine.
3. **Send a shutdown command via SSH** to stop a machine.

### Authentication

The API supports two methods of authentication:
1. **API Token Authentication**: You can authenticate using an API token.
2. **Username/Password Authentication**: Basic HTTP authentication with a username and password.

### Dependencies

This service requires the following dependencies:
- `paramiko`: For SSH communication to send shutdown commands.
- `wakeonlan`: For sending WoL magic packets.
- `curl` and `jq`: For retrieving machine IP addresses from the MAAS API.
- `iputils-ping`: For checking if the machine is reachable.
- `wakeonlan`: should be enabled on the node side in mode 'g'

## Setup

### Docker Setup

The service can be run in a Docker container. Here's how to set up the Docker environment.

1. **Clone this repository**:
    ```bash
    git clone 
    cd repo_directory
    ```

2. **Build the Docker image**:
    ```bash
    docker build -t maas-wol-webhook:latest .
    ```

3. **Run the Docker container**:
    ```bash
    docker run --network=host -e MAAS_API_KEY='Your:API:Key' -v /home/user/.ssh:/root/.ssh --name maas_wol_container --restart unless-stopped maas-wol-webhook:latest
    ```

### Environment Variables

- **`MAAS_API_KEY`**: Your API key for authentication with the MAAS API. It should be set in the `API_KEY` environment variable, separated by colons (e.g., `consumer_key:token:key`).
- **`-v /home/user/.ssh:/root/.ssh`**: Provide SSH Keys of the host machine (ssh keys should be set up on the node side)


3.1. **Alternative way Create .env file with API Key**:
```
sudo mkdir -p /etc/docker
sudo chmod 700 /etc/docker
echo "MAAS_API_KEY=your_api_key_here" | sudo tee /etc/docker/maas_api_key.env
sudo chmod 600 /etc/docker/maas_api_key.env
```
```bash
sudo docker run --network=host --env-file /etc/docker/maas_api_key.env -p 8181:8181 -v /home/user/.ssh:/root/.ssh --name maas_wol_container maas_webhook
```


### Exposed Ports

- **8181**: The port on which the service will be available.

## API Usage

### 1. Check Status (GET)

#### Endpoint:
`GET /{MAC_ADDRESS}`

- **Description**: Checks the status of the machine identified by the given MAC address.
- **Response**:
    ```json
    {
        "status": "running" | "stopped" | "unknown"
    }
    ```

#### Example:
```bash
curl -X GET "http://localhost:8181/00:14:22:01:23:45"
```

`POST /{MAC_ADDRESS}/?op=start`

- **Description**: Sends a Wake-on-LAN packet to wake up the machine identified by the given MAC address.


#### Example:
```bash
curl -X POST "http://localhost:8181/00:14:22:01:23:45/?op=start"
```


`POST /{MAC_ADDRESS}/?op=stop`

- **Description**: Sends a shutdown command via SSH to the machine identified by the given MAC address.


#### Example:
```bash
curl -X POST "http://localhost:8181/00:14:22:01:23:45/?op=stop"
```

## Configuration

You can configure the service by providing the following arguments during container startup:

- **--broadcast**: IP address to use for Wake-on-LAN broadcast (default: 255.255.255.255).
- **--broadcast-port**: Port for the Wake-on-LAN broadcast (default: 9).
- **--port**: Port for the HTTP service to listen on (default: 8080).
- **--username**: Username for basic authentication (optional).
- **--password**: Password for basic authentication (optional).
- **--token**: API token for authentication (optional).

## Logging:

Logs are stored at /var/log/maas/wol/wol_service.log. You can check the log file to monitor the activity of the service, including Wake-on-LAN packets sent and SSH commands executed.

## Troubleshooting

- If the service fails to send the WoL packet, ensure that the MAC address is correct and the machine is on the same network.
- If SSH shutdown commands fail, verify that the machine allows SSH access and that the correct SSH key is used.

## Jenkins CI/CD Pipeline Setup
This project includes a Jenkins pipeline configuration for automating the testing, building, and deployment process. Below are the main stages of the pipeline:
**Setup**
- **Jenkins Credentials:** Store the MAAS API key securely in Jenkins Credentials Manager for safe access during the pipeline execution.<br />
-- Go to Jenkins Dashboard > Manage Jenkins > Manage Credentials > (select a domain or use global) > Add Credentials <br />
-- Choose Secret text and enter the MAAS API key. Label it maas-api-key.
- **GitHub Repository Access:** Jenkins needs access to your GitHub repository (either via a personal access token or SSH keys).


**Steps in the pipeline:**

- **Clone Repository:**    Pulls the latest code from the GitHub repository.
- **Install Dependencies:**  Installs necessary dependencies using pip from requirements.txt.
- **Run Tests:**  Executes unit tests using pytest to ensure that the code works as expected.
- **Build Docker Image:**  Builds a Docker image from the latest code. The image is tagged with maas-wol-webhook:latest.
- **Check and Restart Container:**  
-- Checks if the Docker container is running, stops and removes it if needed, and starts a new container with the updated image.<br />
-- The MAAS API Token is injected into the container using Jenkins credentials securely stored in the Jenkins Credentials Manager. This ensures that sensitive information like tokens is handled securely.

## Handling Sensitive Data (API Keys and Tokens)
 - **Credentials:** We recommend storing sensitive data like the MAAS API key in Jenkins Credentials or environment variables to ensure secure access.
 - In the pipeline, the API key is retrieved using:
```bash
withCredentials([string(credentialsId: 'maas-api-key', variable: 'MAAS_API_KEY')]) {
    sh 'docker run -d --env MAAS_API_KEY=$MAAS_API_KEY -v /home/localadmin/.ssh:/root/.ssh --name maas_wol_container maas-wol-webhook:latest'
}
```
- This method ensures that the API key is kept secure and is injected directly into the container environment at runtime, preventing exposure in logs or source code.

##  Important Considerations
- **Docker Configuration:** Ensure that Docker is installed and accessible on the Jenkins machine. The --network=host flag should be used for the Docker container when running the webhook service, as it allows the container to share the host network(E.g when MAAS is private network).
- **Security Best Practices:** Do not hard-code sensitive information in the repository. Always use Jenkins credentials or environment variables to handle keys and tokens securely.
