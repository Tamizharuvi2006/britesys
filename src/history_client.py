"""
Calder County — Caseworker's Morning Agent
HTTP client for the Resident History API.

Uses urllib.request (stdlib). Simple retry + timeout.
"""
import json
import time
import urllib.request
import urllib.error

import config


class HistoryAPIError(Exception):
    """Raised when the History API returns an error or is unreachable."""
    pass


class HistoryClient:
    """Client for the Resident History API."""

    def __init__(
        self,
        base_url: str = None,
        timeout: int = None,
        retries: int = None,
    ):
        self.base_url = (base_url or config.HISTORY_API_BASE).rstrip("/")
        self.timeout = timeout or config.HISTORY_API_TIMEOUT
        self.retries = retries if retries is not None else config.HISTORY_API_RETRIES

    def _get(self, path: str) -> dict:
        """Make a GET request with retry + timeout. Returns parsed JSON."""
        url = f"{self.base_url}{path}"
        last_error = None

        for attempt in range(1 + self.retries):
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = resp.read().decode("utf-8")
                    return json.loads(body)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    body = e.read().decode("utf-8")
                    data = json.loads(body)
                    raise HistoryAPIError(
                        f"Not found: {path} — {data.get('error', 'unknown')}"
                    )
                last_error = e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_error = e

            # Back off before retry
            if attempt < self.retries:
                time.sleep(0.5 * (attempt + 1))

        raise HistoryAPIError(
            f"History API unreachable after {1 + self.retries} attempts: {last_error}"
        )

    def health_check(self) -> dict:
        """GET /health — verify the service is running."""
        return self._get("/health")

    def get_resident(self, ref: str) -> dict:
        """GET /residents/<ref> — full record."""
        return self._get(f"/residents/{ref}")

    def get_household(self, ref: str) -> dict:
        """GET /residents/<ref>/household — household composition only."""
        return self._get(f"/residents/{ref}/household")

    def get_events(self, ref: str) -> dict:
        """GET /residents/<ref>/events — case events only."""
        return self._get(f"/residents/{ref}/events")
