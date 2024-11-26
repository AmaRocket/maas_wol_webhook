#!/usr/bin/env python3

import argparse
import base64
import http.server
import json
import logging
import os
import re
import uuid
import time
import select
import signal
import socket
import socketserver
import subprocess
import sys


import paramiko


GET_REGEX = re.compile(r"^/(?P<MAC>([\da-f]{2}[:-]){5}[\da-f]{2})[/]?$", re.I)
POST_REGEX = re.compile(
    r"^/(?P<MAC>([\da-f]{2}[:-]){5}[\da-f]{2})/\?op=(?P<OP>(start|stop))$", re.I
)

machine_status = {}
broadcast_ip = None
broadcast_port = None
username = None
password = None
token = None

# Configure logging
logging.basicConfig(
    filename="/var/log/maas/wol/wol_service.log",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("HTTPWoL")


class HTTPWoL(http.server.SimpleHTTPRequestHandler):


    def _authenticate(self):
        global username, password, token
        if not username and not password and not token:
            return True
        try:
            cred = self.headers.get("Authorization").split()[1]
        except (IndexError, AttributeError):
            cred = None

        if token and cred == token:
            logger.info("Token authentication successful")
            return True
        elif username or password:
            if base64.b64decode(cred).decode() == f"{username}:{password}":
                logger.info("Username/password authentication successful")
                return True
        logger.warning("Authentication failed")
        self.send_response(http.client.UNAUTHORIZED)
        self.end_headers()
        self.wfile.write(b"Unauthorized!\n")
        return False

    def _bad_path(self):
        self.send_response(http.client.BAD_REQUEST)
        self.end_headers()
        self.wfile.write(b"Unknown path!\n")
        logger.error(f"Bad path encountered: {self.path}")

    def get_ip_from_api(self):
        system_id = self.headers.get("System_id")
        # print(system_id)
        API_KEY = os.getenv("MAAS_API_KEY").split(":")  # API Key for dbisadmin user e.g
        if not API_KEY:
            raise ValueError("API key is not set. Please set the MAAS_API_KEY environment variable.")
        try:
            # Execute curl to get machine details and parse with jq
            curl_command = f"""
            curl --header "Authorization: OAuth oauth_version=1.0, oauth_signature_method=PLAINTEXT, oauth_consumer_key={API_KEY[0]}, oauth_token={API_KEY[1]}, oauth_signature=&{API_KEY[2]}, oauth_nonce=$(uuid), oauth_timestamp=$(date +%s)" https://maas.dmi.unibas.ch/MAAS/api/2.0/machines/ | \
            jq -r '[.[] | {{osystem_id: .system_id, ip_addresses: .ip_addresses[0], hostname: (.hostname + "." + .domain.name), mac_address: .interface_set[0].mac_address}}] | .[] | select(.osystem_id == "{system_id}") | .ip_addresses'
            """

            result = subprocess.run(curl_command, shell=True, capture_output=True, text=True, check=True)

            # Parse the output and get IP address
            ip_address = result.stdout.strip()
            if not ip_address:
                logger.warning("No IP address found for the system ID provided.")
                return None
            return ip_address
        except subprocess.CalledProcessError as e:
            logger.error(f"Error executing MAAS command: {e.stderr}")
        except (KeyError, IndexError) as e:
            logger.error(f"Error parsing IP address from MAAS output: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")

    def _ping(self, ip):
        try:
            subprocess.check_call(["ping", "-c", "1", ip], stdout=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            return False

    def _check_status(self, mac_address):
        try:
            ip_address = self.get_ip_from_api()
            if ip_address and self._ping(ip_address):
                # Update status if the machine is reachable
                machine_status[mac_address] = "running"
                return True
            else:
                # Update to "stopped" if unreachable
                machine_status[mac_address] = "stopped"
                return False
        except Exception as e:
            logger.error("Exception in _check_status(): ", e)



    def do_GET(self):
        if not self._authenticate():
            return
        m = GET_REGEX.search(self.path)
        if m:
            global machine_status
            mac_address = m.group("MAC")
            status = machine_status.get(m.group("MAC"), "unknown")
            if self._check_status(mac_address):
                status = "running"
                machine_status[mac_address] = "running"
            else:
                status = "stopped"
                machine_status[mac_address] = "stopped"
            self.send_response(http.client.OK)
            self.end_headers()
            self.wfile.write(json.dumps({"status": status}).encode() + b"\n")
            logger.info(f"Status check for MAC {m.group('MAC')}: {status}")
        else:
            self._bad_path()

    def _start(self, mac_address):
        global machine_status, broadcast_ip, broadcast_port
        self._check_status(mac_address)
        packets = bytes.fromhex("F" * 12 + mac_address.replace(mac_address[2], "") * 16)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.connect((broadcast_ip, broadcast_port))
            sock.send(packets)
        self.send_response(http.client.OK)
        self.end_headers()
        self.wfile.write(b"WoL packet sent!\n")
        machine_status[mac_address] = "running"
        logger.info(f"WoL packet sent to MAC {mac_address}")

    def _stop(self, mac_address):
        target_ip = self.get_ip_from_api()
        # print(target_ip)
        ssh_user = "ubuntu"
        ssh_key_path = "/root/.ssh/id_ed25519.pub"
        connection_timeout = 3

        if not target_ip:
            logger.error(f"IP address not found for MAC {mac_address}")
            self.send_response(http.client.INTERNAL_SERVER_ERROR)
            self.end_headers()
            self.wfile.write(b"Failed to find IP address for the system!\n")
            return

        try:
            # Before sending the shutdown signal, verify the machine's status.
            if not self._check_status(mac_address):
                logger.info(f"Machine {mac_address} is already stopped.")
                self.send_response(http.client.OK)
                self.end_headers()
                self.wfile.write(b"Machine is already stopped!\n")
                return

            # Proceed with sending the shutdown signal.
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(target_ip, username=ssh_user, key_filename=ssh_key_path, timeout=connection_timeout)
            ssh.exec_command("sudo shutdown now")
            self.send_response(http.client.OK)
            self.end_headers()
            self.wfile.write(b"System shutdown command sent via SSH!\n")
            logger.info(f"Shutdown command sent via SSH to IP {target_ip}")

            # Verify machine status after sending the command.
            if not self._check_status(mac_address):
                global machine_status
                machine_status[mac_address] = "stopped"
                logger.info(f"Machine {mac_address} status updated to 'stopped'.")

        except paramiko.SSHException as e:
            logger.error(f"SSH error while attempting to shutdown: {e}")
            self.send_response(http.client.INTERNAL_SERVER_ERROR)
            self.end_headers()
            self.wfile.write(b"Failed to shutdown the system via SSH!\n")
        except Exception as e:
            logger.error(f"Unexpected error in _stop: {e}")
            self.send_response(http.client.INTERNAL_SERVER_ERROR)
            self.end_headers()
            self.wfile.write(b"Unexpected error occurred during shutdown process!\n")
        finally:
            if 'ssh' in locals():  # Ensure ssh is defined before trying to close it.
                ssh.close()


    def do_POST(self):
        if not self._authenticate():
            return
        m = POST_REGEX.search(self.path)
        if m:
            op = m.group("OP")
            try:
                if op == "start":
                    self._start(m.group("MAC"))
                elif op == "stop":
                    self._stop(m.group("MAC"))
                logger.info(f"Received {op} operation for MAC {m.group('MAC')}")
            except Exception as e:
                logger.error(f"Error processing {op} operation for MAC {m.group('MAC')}: {e}")
                self.send_response(http.client.INTERNAL_SERVER_ERROR)
                self.end_headers()
                self.wfile.write(b"Error occurred during processing!\n")
        else:
            self._bad_path()


def main():
    parser = argparse.ArgumentParser(description="Web server to issue WoL commands")
    parser.add_argument("--broadcast", "-b", default="255.255.255.255", type=str)
    parser.add_argument("--broadcast-port", "-B", default=9, type=int)
    parser.add_argument("--port", "-p", default=800, type=int)
    parser.add_argument("--username", "-u", type=str)
    parser.add_argument("--password", "-P", type=str)
    parser.add_argument("--token", "-t", type=str)
    args = parser.parse_args()

    global broadcast_ip, broadcast_port, username, password, token
    broadcast_ip = args.broadcast
    broadcast_port = args.broadcast_port
    username = args.username
    password = args.password
    token = args.token

    with socketserver.TCPServer(("", args.port), HTTPWoL) as httpd:
        def shutdown(*args, **kwargs):
            logger.info("Server shutting down")
            httpd.server_close()
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown)
        logger.info("Starting server")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
