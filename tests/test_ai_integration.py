import json
from unittest.mock import patch, Mock

from mytermux.ai_integration import AIClient, AIClientError


def test_send_request_success():
    client = AIClient(api_url="https://api.test/ai", api_key="key")
    payload = {"prompt": "hello"}

    resp_mock = Mock()
    resp_mock.ok = True
    resp_mock.status_code = 200
    resp_mock.json.return_value = {"result": "ok"}

    with patch("mytermux.ai_integration.requests.post", return_value=resp_mock) as post:
        out = client.send_request(payload)
        post.assert_called_once()
        assert out["result"] == "ok"


def test_send_request_server_error_retries_and_fails():
    client = AIClient(api_url="https://api.test/ai")
    payload = {"prompt": "hello"}

    resp_mock = Mock()
    resp_mock.ok = False
    resp_mock.status_code = 500
    resp_mock.text = "server error"

    # always return 500 -> should raise after retries
    with patch("mytermux.ai_integration.requests.post", return_value=resp_mock):
        try:
            client.send_request(payload, max_retries=2, backoff=0.01)
            assert False, "Expected AIClientError"
        except AIClientError:
            pass
