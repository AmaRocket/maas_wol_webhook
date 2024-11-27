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
    docker build -t maas-wol-service .
    ```

3. **Run the Docker container**:
    ```bash
    docker run --network=host -e MAAS_API_KEY='Your:API:Key' -p 8080:8080 -v /home/user/.ssh:/root/.ssh --name maas_wol_container maas_webhook 
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
sudo docker run --network=host --env-file /etc/docker/maas_api_key.env -p 8080:8080 -v /home/user/.ssh:/root/.ssh --name maas_wol_container maas_webhook
```


### Exposed Ports

- **8080**: The port on which the service will be available.

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
curl -X GET "http://localhost:8080/00:14:22:01:23:45"
```

`POST /{MAC_ADDRESS}/?op=start`

- **Description**: Sends a Wake-on-LAN packet to wake up the machine identified by the given MAC address.


#### Example:
```bash
curl -X POST "http://localhost:8080/00:14:22:01:23:45/?op=start"
```


`POST /{MAC_ADDRESS}/?op=stop`

- **Description**: Sends a shutdown command via SSH to the machine identified by the given MAC address.


#### Example:
```bash
curl -X POST "http://localhost:8080/00:14:22:01:23:45/?op=stop"
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
