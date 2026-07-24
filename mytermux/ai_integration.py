"""Lightweight adapter for an external AI service.

This module provides a small, testable `AIClient` class used by backend and
agent code to call an external model endpoint using a consistent interface.
"""
from typing import Any, Dict, Optional
import os
import time
import logging

import httpx

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
        """Synchronous request using httpx.Client. Retries transient errors with backoff."""
        url = self.api_url
        headers = self._headers()
        attempt = 0
        while True:
            attempt += 1
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, json=payload, headers=headers)
                if resp.status_code >= 500 and attempt <= max_retries:
                    time.sleep(backoff * (2 ** (attempt - 1)))
                    continue
                if resp.status_code >= 400:
                    raise AIClientError(f"AI request failed: {resp.status_code} {resp.text}")
                return resp.json()
            except (httpx.RequestError, ValueError) as exc:
                if attempt >= max_retries:
                    logger.exception("AI request failed after retries")
                    raise AIClientError("Failed to contact AI service") from exc
                time.sleep(backoff * (2 ** (attempt - 1)))

    async def send_request_async(self, payload: Dict[str, Any], max_retries: int = 3, backoff: float = 0.5) -> Dict[str, Any]:
        """Async request using httpx.AsyncClient."""
        url = self.api_url
        headers = self._headers()
        attempt = 0
        while True:
            attempt += 1
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code >= 500 and attempt <= max_retries:
                    await _async_sleep(backoff * (2 ** (attempt - 1)))
                    continue
                if resp.status_code >= 400:
                    raise AIClientError(f"AI request failed: {resp.status_code} {resp.text}")
                return resp.json()
            except (httpx.RequestError, ValueError) as exc:
                if attempt >= max_retries:
                    logger.exception("AI async request failed after retries")
                    raise AIClientError("Failed to contact AI service") from exc
                await _async_sleep(backoff * (2 ** (attempt - 1)))


async def _async_sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


__all__ = ["AIClient", "AIClientError"]
