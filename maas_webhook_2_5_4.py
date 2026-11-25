#!/usr/bin/env python3

import argparse
import base64
import binascii
import http.server
import json
import logging
import os
import re
import signal
import socket
import socketserver
import subprocess
import sys
import time
from urllib.parse import urlparse, urlunparse

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

# Configure logging. Create the log directory if needed; fall back to
# stderr if the file cannot be opened (e.g. read-only /var/log in dev).
LOG_FILE = "/var/log/maas/wol/wol_service.log"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
try:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format=LOG_FORMAT,
    )
except (OSError, PermissionError) as e:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    logging.getLogger("HTTPWoL").warning(
        f"Could not write to {LOG_FILE} ({e}); logging to stderr"
    )
logger = logging.getLogger("HTTPWoL")

api_key = os.getenv("MAAS_API_KEY")
if not api_key:
    print("MAAS_API_KEY environment variable is not set")
api_url = os.getenv("MAAS_API_URL")
if not api_url:
    print("MAAS_API_URL environment variable is not set")


class HTTPWoL(http.server.SimpleHTTPRequestHandler):

    def _unauthorized(self):
        self.send_response(http.client.UNAUTHORIZED)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Unauthorized!\n")

    def _authenticate(self):
        global username, password, token
        # No credentials configured: allow all requests (production default).
        if not username and not password and not token:
            return True

        auth = self.headers.get("Authorization") or ""
        if not auth.lower().startswith("basic "):
            self._unauthorized()
            return False
        try:
            cred = (
                base64.b64decode(auth.split(None, 1)[1], validate=True)
                .decode("utf-8", "replace")
            )
        except (IndexError, ValueError, binascii.Error) as e:
            logger.warning(f"Malformed Authorization header: {e}")
            self._unauthorized()
            return False

        if token and cred == token:
            logger.info("Token authentication successful")
            return True
        if username or password:
            if cred == f"{username}:{password}":
                logger.info("Username/password authentication successful")
                return True
        logger.warning("Authentication failed")
        self._unauthorized()
        return False

    def _bad_path(self):
        self.send_response(http.client.BAD_REQUEST)
        self.end_headers()
        self.wfile.write(b"Unknown path!\n")
        logger.error(f"Bad path encountered: {self.path}")

    def _require_system_id(self):
        """Ensure the caller supplied the System_id header used for MAAS lookups.

        The MAC in the request path identifies the node, but IP resolution goes
        through the MAAS API by system_id. Return False (and send 400) when the
        header is missing so the caller does not silently receive a bogus status.
        """
        if self.headers.get("System_id"):
            return True
        logger.error(
            "Missing System_id header for %s %s", self.command, self.path
        )
        self._send_error(
            http.client.BAD_REQUEST,
            "Missing System_id header (required for MAAS lookups)",
        )
        return False

    @staticmethod
    def _oauth_header(api_key):
        """Build the MAAS OAuth Authorization header (PLAINTEXT signature)."""
        parts = api_key.split(":")
        if len(parts) != 3:
            raise ValueError("MAAS_API_KEY must be in consumer:token:secret format")
        consumer_key, token_key, secret = parts
        return (
            "OAuth oauth_version=1.0, "
            "oauth_signature_method=PLAINTEXT, "
            f"oauth_consumer_key={consumer_key}, "
            f"oauth_token={token_key}, "
            f"oauth_signature=&{secret}"
        )

    def get_ip_from_api(self):
        system_id = self.headers.get("System_id")
        API_URL = os.getenv("MAAS_API_URL")
        API_KEY = os.getenv("MAAS_API_KEY")
        if not system_id:
            logger.error("Missing System_id header")
            return None
        if not API_KEY:
            logger.error("MAAS_API_KEY is not set")
            return None
        if not API_URL:
            logger.error("MAAS_API_URL is not set")
            return None
        try:
            oauth_header = self._oauth_header(API_KEY)

            # Execute curl with an argument list (no shell) to avoid injection.
            result = subprocess.run(
                [
                    "curl", "--silent", "--show-error", "--max-time", "10",
                    "--header", f"Authorization: {oauth_header}",
                    API_URL,
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            # MAAS may return a bare JSON object or a single-element list
            # wrapping the API root. Normalize to the API root URL.
            data = json.loads(result.stdout)
            if isinstance(data, list):
                if len(data) == 0:
                    raise ValueError("MAAS returned an empty list")
                root = data[0]
            else:
                root = data
            root = root.get("value") if isinstance(root, dict) else root

            parsed = urlparse(API_URL)
            machines_url = urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    "/api/2.0/machines/?op=list",
                    "",
                    "",
                    "",
                )
            )

            result = subprocess.run(
                [
                    "curl", "--silent", "--show-error", "--max-time", "10",
                    "--header", f"Authorization: {oauth_header}",
                    machines_url,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            machines = json.loads(result.stdout)
            if not isinstance(machines, list):
                raise ValueError("Expected a list of machines from MAAS")

            for machine in machines:
                if machine.get("system_id") == system_id:
                    addresses = machine.get("ip_addresses") or []
                    ip_address = addresses[0] if addresses else None
                    logger.info(f"System ID: {system_id} -- IP: {ip_address}")
                    if not ip_address:
                        logger.warning(
                            "No IP address found for the system ID provided."
                        )
                    return ip_address
            logger.warning(f"System ID {system_id} not found in MAAS machines")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error executing MAAS command: {e.stderr}")
        except (json.JSONDecodeError, KeyError, IndexError, ValueError) as e:
            logger.error(f"Error parsing MAAS API response: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return None
        return None

    def _ping(self, ip):
        try:
            subprocess.check_call(["ping", "-c", "1", ip], stdout=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            return False

    def _check_status(self, mac_address):
        # Returns True (running), False (stopped), or None (could not determine).
        try:
            ip_address = self.get_ip_from_api()
            logger.info("Resolved IP: %s", ip_address)
            if ip_address and self._ping(ip_address):
                machine_status[mac_address] = "running"
                return True
            if ip_address:
                # Host is known but unreachable.
                machine_status[mac_address] = "stopped"
                return False
            # No IP found: status is unknown, not necessarily stopped.
            machine_status[mac_address] = "unknown"
            return None
        except Exception as e:
            logger.error("Exception in _check_status(): %s", e, exc_info=True)
            machine_status[mac_address] = "unknown"
            return None

    def _send_error(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        try:
            self.wfile.write(message.encode("utf-8") + b"\n")
        except (BrokenPipeError, ConnectionResetError):
            logger.warning("Client disconnected while sending error response")

    def do_GET(self):
        try:
            if self.path == "/health":
                self._health_check()
                return

            if not self._authenticate():
                return
            m = GET_REGEX.search(self.path)
            if not m:
                self._bad_path()
                return
            if not self._require_system_id():
                return

            mac_address = m.group("MAC")
            status = machine_status.get(mac_address, "unknown")
            result = self._check_status(mac_address)
            if result is None:
                status = "unknown"
            elif result:
                status = "running"
            else:
                status = "stopped"
            machine_status[mac_address] = status
            self._send_response_json(status)
            logger.info(f"Status check for MAC {mac_address}: {status}")
        except Exception as e:
            logger.error("Error in do_GET: %s", e, exc_info=True)
            try:
                self._send_error(
                    http.client.INTERNAL_SERVER_ERROR, "Internal server error"
                )
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _send_response_json(self, status):
        try:
            self.send_response(http.client.OK)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": status}).encode("utf-8") + b"\n")
        except (BrokenPipeError, ConnectionResetError) as e:
            logger.warning(f"Client disconnected during status response: {e}")

    def _health_check(self):
        """
        Handles health check requests from HAProxy.
        """
        try:
            self.send_response(http.client.OK)
            self.end_headers()
            self.wfile.write(b"OK\n")
            logger.info("Health check successful")
        except (ConnectionResetError, BrokenPipeError):
            logger.warning("Client disconnected prematurely during health check.")
        except Exception as e:
            self.send_response(503)
            self.end_headers()
            self.wfile.write(f"Error: {e}".encode("utf-8"))
            logger.error(f"Error: {e}")

    def _start(self, mac_address):
        global machine_status, broadcast_ip, broadcast_port
        if not self._require_system_id():
            return
        # Record the pre-wake status for logging; the machine is not reported
        # as running until a later status check confirms it actually booted.
        status_before = self._check_status(mac_address)
        logger.info("Pre-wake status for MAC %s: %s", mac_address, status_before)
        # Standard WoL magic packet: 6 x FF + MAC (no separators) x 16 = 102 bytes.
        mac_hex = mac_address.replace(":", "").replace("-", "")
        packets = bytes.fromhex("FF" * 6 + mac_hex * 16)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.connect((broadcast_ip, broadcast_port))
            sock.send(packets)
        self.send_response(http.client.OK)
        self.end_headers()
        self.wfile.write(b"WoL packet sent!\n")
        # Do not assert "running" here: the host has only been signalled, not
        # confirmed online. Leave the recorded status to the next status check.
        machine_status[mac_address] = "stopped" if status_before is False else "unknown"
        logger.info(f"WoL packet sent to MAC {mac_address}")

    def _stop(self, mac_address):
        if not self._require_system_id():
            return
        target_ip = self.get_ip_from_api()
        logger.info(target_ip)
        ssh_user = "ubuntu"
        ssh_key_path = "/root/.ssh/id_ed25519"
        connection_timeout = 3

        if not target_ip:
            logger.error(f"IP address not found for MAC {mac_address}")
            self._send_error(
                http.client.INTERNAL_SERVER_ERROR,
                "Failed to find IP address for the system!",
            )
            return

        try:
            # Before sending the shutdown signal, verify the machine's status.
            # A None status means we could not determine it; proceed cautiously
            # rather than claiming it is already stopped.
            if self._check_status(mac_address) is False:
                logger.info(f"Machine {mac_address} is already stopped.")
                self.send_response(http.client.OK)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Machine is already stopped!\n")
                return

            # Proceed with sending the shutdown signal.
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                target_ip,
                username=ssh_user,
                key_filename=ssh_key_path,
                timeout=connection_timeout,
            )
            _, stdout, stderr = ssh.exec_command("sudo shutdown now")
            # Wait for the command to actually complete on the remote host before
            # reporting success; otherwise the shutdown is dropped when we close.
            exit_status = stdout.channel.recv_exit_status()
            stderr_tail = stderr.read().decode("utf-8", "replace")[:500]
            logger.info(
                f"Shutdown command exit={exit_status} stderr={stderr_tail!r} "
                f"for IP {target_ip}"
            )
            if exit_status == 0:
                self.send_response(http.client.OK)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"System shutdown command sent via SSH!\n")
                # Give the power-off a moment, then verify.
                time.sleep(5)
                if self._check_status(mac_address) is False:
                    machine_status[mac_address] = "stopped"
                    logger.info(
                        f"Machine {mac_address} status updated to 'stopped'."
                    )
            else:
                self._send_error(
                    http.client.INTERNAL_SERVER_ERROR,
                    "Shutdown command failed on remote host",
                )

        except paramiko.SSHException as e:
            logger.error(f"SSH error while attempting to shutdown: {e}")
            self._send_error(
                http.client.INTERNAL_SERVER_ERROR,
                "Failed to shutdown the system via SSH!",
            )
        except Exception as e:
            logger.error(f"Unexpected error in _stop: {e}", exc_info=True)
            self._send_error(
                http.client.INTERNAL_SERVER_ERROR,
                "Unexpected error occurred during shutdown process!",
            )
        finally:
            if "ssh" in locals():  # Ensure ssh is defined before trying to close it.
                ssh.close()

    def do_POST(self):
        if not self._authenticate():
            return
        m = POST_REGEX.search(self.path)
        if not m:
            self._bad_path()
            return
        op = m.group("OP")
        mac_address = m.group("MAC")
        try:
            if op == "start":
                self._start(mac_address)
            else:
                self._stop(mac_address)
            logger.info(f"Received {op} operation for MAC {mac_address}")
        except Exception as e:
            logger.error(
                f"Error processing {op} operation for MAC {mac_address}: {e}",
                exc_info=True,
            )
            self._send_error(
                http.client.INTERNAL_SERVER_ERROR, "Error occurred during processing!"
            )


class ReusableTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser(description="Web server to issue WoL commands")
    parser.add_argument("--broadcast", "-b", default="255.255.255.255", type=str)
    parser.add_argument("--broadcast-port", "-B", default=9, type=int)
    parser.add_argument("--port", "-p", default=8181, type=int)
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

    with ReusableTCPServer(("", args.port), HTTPWoL) as httpd:
        # with socketserver.TCPServer(("", args.port), HTTPWoL) as httpd:
        def shutdown(*args, **kwargs):
            logger.info("Server shutting down")
            httpd.server_close()
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown)
        logger.info("Starting server")
        httpd.serve_forever()


if __name__ == "__main__":
    main()

