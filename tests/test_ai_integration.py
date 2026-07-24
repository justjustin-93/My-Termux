import json
from unittest.mock import patch, Mock

from mytermux.ai_integration import AIClient, AIClientError


class DummyResp:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json


def test_send_request_success():
    client = AIClient(api_url="https://api.test/ai", api_key="key")
    payload = {"prompt": "hello"}

    dummy = DummyResp(status_code=200, json_data={"result": "ok"})

    with patch("mytermux.ai_integration.httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.post.return_value = dummy
        out = client.send_request(payload)
        inst.post.assert_called_once()
        assert out["result"] == "ok"


def test_send_request_server_error_retries_and_fails():
    client = AIClient(api_url="https://api.test/ai")
    payload = {"prompt": "hello"}

    dummy = DummyResp(status_code=500, json_data={"error": "server"}, text="server error")

    with patch("mytermux.ai_integration.httpx.Client") as MockClient:
        inst = MockClient.return_value.__enter__.return_value
        inst.post.return_value = dummy
        try:
            client.send_request(payload, max_retries=2, backoff=0.001)
            assert False, "Expected AIClientError"
        except AIClientError:
            pass
