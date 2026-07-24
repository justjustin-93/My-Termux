"""Lightweight adapter for an external AI service.

This module provides a small, testable `AIClient` class used by backend and
agent code to call an external model endpoint using a consistent interface.
"""
from typing import Any, Dict, Optional
import os
import time
import logging

import requests

logger = logging.getLogger(__name__)


class AIClientError(Exception):
    pass


class AIClient:
    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None, timeout: int = 15):
        self.api_url = api_url or os.environ.get("AI_API_URL")
        self.api_key = api_key or os.environ.get("AI_API_KEY")
        self.timeout = int(os.environ.get("AI_TIMEOUT", timeout))
        if not self.api_url:
            raise AIClientError("AI_API_URL not configured")

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def send_request(self, payload: Dict[str, Any], max_retries: int = 3, backoff: float = 0.5) -> Dict[str, Any]:
        """Send a request to the AI endpoint and return parsed JSON response.

        Retries transient network errors with exponential backoff.
        """
        url = self.api_url
        headers = self._headers()
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                if resp.status_code >= 500 and attempt <= max_retries:
                    # transient server error — retry
                    time.sleep(backoff * (2 ** (attempt - 1)))
                    continue
                if not resp.ok:
                    raise AIClientError(f"AI request failed: {resp.status_code} {resp.text}")
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                if attempt >= max_retries:
                    logger.exception("AI request failed after retries")
                    raise AIClientError("Failed to contact AI service") from exc
                time.sleep(backoff * (2 ** (attempt - 1)))


__all__ = ["AIClient", "AIClientError"]
