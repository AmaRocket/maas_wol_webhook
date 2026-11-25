import base64
import os
import sys
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import maas_webhook_2_5_4 as m
from maas_webhook_2_5_4 import GET_REGEX, POST_REGEX, HTTPWoL


def _make_handler():
    """Build an HTTPWoL instance without running the socketserver machinery."""
    handler = HTTPWoL.__new__(HTTPWoL)
    # BaseHTTPRequestHandler normally exposes these; some code paths log them.
    handler.command = "GET"
    handler.path = "/"
    handler.headers = {}
    handler.wfile = BytesIO()
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()
    return handler


class TestRegexes(unittest.TestCase):
    def test_regex_get(self):
        match = GET_REGEX.match("/2c:44:fd:2a:0e:2a/")
        self.assertIsNotNone(match, "GET regex should match valid MAC path")
        self.assertEqual(match.group("MAC"), "2c:44:fd:2a:0e:2a")

    def test_regex_post_start(self):
        match = POST_REGEX.match("/2c:44:fd:2a:0e:2a/?op=start")
        self.assertIsNotNone(match, "POST regex should match valid MAC and start op")
        self.assertEqual(match.group("MAC"), "2c:44:fd:2a:0e:2a")
        self.assertEqual(match.group("OP"), "start")

    def test_regex_post_stop(self):
        match = POST_REGEX.match("/2c:44:fd:2a:0e:2a/?op=stop")
        self.assertIsNotNone(match, "POST regex should match valid MAC and stop op")
        self.assertEqual(match.group("MAC"), "2c:44:fd:2a:0e:2a")
        self.assertEqual(match.group("OP"), "stop")


class TestAuthentication(unittest.TestCase):
    def setUp(self):
        # Reset module-level auth globals so each test is independent.
        self._orig = (m.username, m.password, m.token)
        m.username = None
        m.password = None
        m.token = None

    def tearDown(self):
        m.username, m.password, m.token = self._orig

    def _basic(self, value):
        encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
        return f"Basic {encoded}"

    def test_no_credentials_configured_allows_all(self):
        handler = _make_handler()
        self.assertTrue(handler._authenticate())

    def test_token_matches_basic_credential(self):
        m.token = "valid_token"
        handler = _make_handler()
        handler.headers = {"Authorization": self._basic("valid_token")}
        self.assertTrue(handler._authenticate())

    def test_bearer_token_is_rejected(self):
        # The handler only accepts HTTP Basic auth; a Bearer header must not pass
        # even when the token value happens to match.
        m.token = "valid_token"
        handler = _make_handler()
        handler.headers = {"Authorization": "Bearer valid_token"}
        self.assertFalse(handler._authenticate())
        handler.send_response.assert_called_once()

    def test_token_mismatch_is_rejected(self):
        m.token = "valid_token"
        handler = _make_handler()
        handler.headers = {"Authorization": self._basic("wrong_token")}
        self.assertFalse(handler._authenticate())
        handler.send_response.assert_called_once()

    def test_username_password_matches(self):
        m.username = "user"
        m.password = "pass"
        handler = _make_handler()
        handler.headers = {"Authorization": self._basic("user:pass")}
        self.assertTrue(handler._authenticate())

    def test_malformed_base64_is_rejected(self):
        m.username = "user"
        m.password = "pass"
        handler = _make_handler()
        handler.headers = {"Authorization": "Basic not-valid-base64!!"}
        self.assertFalse(handler._authenticate())
        handler.send_response.assert_called_once()


class TestOAuthHeader(unittest.TestCase):
    def test_valid_key_builds_plaintext_header(self):
        header = HTTPWoL._oauth_header("consumer:token:secret")
        self.assertIn("oauth_consumer_key=consumer", header)
        self.assertIn("oauth_token=token", header)
        self.assertIn("oauth_signature=&secret", header)

    def test_invalid_key_shape_raises(self):
        with self.assertRaises(ValueError):
            HTTPWoL._oauth_header("consumer:token")


class TestWoLWolPacket(unittest.TestCase):
    def test_start_builds_standard_magic_packet(self):
        handler = _make_handler()
        sent = []

        class FakeSock:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def setsockopt(self, *a):
                pass

            def connect(self, addr):
                self.addr = addr

            def send(self, data):
                sent.append(data)

        m.broadcast_ip = "255.255.255.255"
        m.broadcast_port = 9
        # _start now requires the System_id header before doing any work.
        handler.headers = {"System_id": "abc123"}
        # Avoid depending on a live MAAS API / ping.
        handler._check_status = MagicMock(return_value=False)

        with patch("maas_webhook_2_5_4.socket.socket", return_value=FakeSock()):
            handler._start("2c:44:fd:2a:0e:2a")

        self.assertEqual(len(sent), 1)
        packet = sent[0]
        # 6 bytes of 0xFF, then the MAC repeated 16 times with no separators.
        self.assertEqual(len(packet), 102)
        self.assertEqual(packet[:6], b"\xff" * 6)
        self.assertEqual(packet[6:], bytes.fromhex("2c44fd2a0e2a") * 16)
        self.assertEqual(handler.wfile.getvalue(), b"WoL packet sent!\n")


class TestRequireSystemId(unittest.TestCase):
    def _handler_with_header(self, headers):
        handler = _make_handler()
        handler.command = "GET"
        handler.path = "/2c:44:fd:2a:0e:2a/"
        handler.headers = headers
        return handler

    def test_present_header_allows_through(self):
        handler = self._handler_with_header({"System_id": "abc123"})
        self.assertTrue(handler._require_system_id())

    def test_missing_header_sends_400_and_returns_false(self):
        handler = self._handler_with_header({})
        self.assertFalse(handler._require_system_id())
        # 400 Bad Request is sent via _send_error -> send_response(400).
        handler.send_response.assert_called_once_with(400)
        self.assertIn(b"Missing System_id header", handler.wfile.getvalue())

    def test_empty_header_is_treated_as_missing(self):
        handler = self._handler_with_header({"System_id": ""})
        self.assertFalse(handler._require_system_id())


class TestCheckStatus(unittest.TestCase):
    def test_reachable_is_running(self):
        handler = _make_handler()
        handler.get_ip_from_api = MagicMock(return_value="10.0.0.5")
        handler._ping = MagicMock(return_value=True)
        m.machine_status.clear()
        self.assertTrue(handler._check_status("2c:44:fd:2a:0e:2a"))
        self.assertEqual(m.machine_status["2c:44:fd:2a:0e:2a"], "running")

    def test_known_but_unreachable_is_stopped(self):
        handler = _make_handler()
        handler.get_ip_from_api = MagicMock(return_value="10.0.0.5")
        handler._ping = MagicMock(return_value=False)
        m.machine_status.clear()
        self.assertFalse(handler._check_status("2c:44:fd:2a:0e:2a"))
        self.assertEqual(m.machine_status["2c:44:fd:2a:0e:2a"], "stopped")

    def test_no_ip_is_unknown(self):
        handler = _make_handler()
        handler.get_ip_from_api = MagicMock(return_value=None)
        handler._ping = MagicMock(return_value=False)
        m.machine_status.clear()
        self.assertIsNone(handler._check_status("2c:44:fd:2a:0e:2a"))
        self.assertEqual(m.machine_status["2c:44:fd:2a:0e:2a"], "unknown")


if __name__ == "__main__":
    unittest.main()
