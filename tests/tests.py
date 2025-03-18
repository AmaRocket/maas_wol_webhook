import json
import os
import subprocess
import sys
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from io import BytesIO
from unittest.mock import Mock

from maas_webhook_2_5_4 import GET_REGEX, POST_REGEX, HTTPWoL, machine_status


class TestHTTPWoL(unittest.TestCase):
    @patch.dict(os.environ, {"MAAS_API_KEY": os.getenv("MAAS_API_KEY")})
    def setUp(self):
        self.handler = HTTPWoL
        self.handler.username = None
        self.handler.password = None
        self.handler.token = None

    def mock_request(self, path, method="GET", headers=None):
        headers = headers or {}
        request = MagicMock()
        request.path = path
        request.command = method
        request.headers = headers
        request.wfile = BytesIO()
        return request

    @patch("maas_webhook_2_5_4.os.getenv")
    def test_authentication_with_token(self, mock_getenv):
        mock_server = Mock()
        mock_request = Mock()
        mock_request.makefile = Mock(return_value=BytesIO(b"GET /path HTTP/1.1\r\n"))

        handler = self.handler(mock_request, ("127.0.0.1", 12345), mock_server)

        handler.headers = {"Authorization": "Bearer valid_token"}
        handler.wfile = BytesIO()

        handler.token = "valid_token"

        authenticated = handler._authenticate()
        self.assertTrue(authenticated, "Authentication with a valid token should pass")

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


if __name__ == "__main__":
    unittest.main()
