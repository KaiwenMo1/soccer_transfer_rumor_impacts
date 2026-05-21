from __future__ import annotations

import time
from typing import Any

import requests


USER_AGENT = "transfer-stock-research/0.1 educational research"


class FetchError(RuntimeError):
    pass


def request_with_retries(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
    retries: int = 2,
) -> requests.Response:
    response: requests.Response | None = None
    last_error: requests.RequestException | None = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(
                url,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=timeout,
            )
        except requests.RequestException as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(2.0 * (attempt + 1))
            continue
        if response.status_code != 429:
            return response
        retry_after = response.headers.get("Retry-After")
        wait = float(retry_after) if retry_after and retry_after.isdigit() else 2.0 * (attempt + 1)
        time.sleep(wait)
    if response is not None:
        return response
    raise FetchError(f"GET {url} failed after {retries + 1} attempts: {last_error}")
    return response


def get_text(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
    retries: int = 2,
) -> str:
    response = request_with_retries(url, params=params, timeout=timeout, retries=retries)
    if response.status_code >= 400:
        raise FetchError(f"GET {response.url} returned {response.status_code}")
    return response.text


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: int = 30,
    retries: int = 2,
) -> Any:
    response = request_with_retries(url, params=params, timeout=timeout, retries=retries)
    if response.status_code >= 400:
        raise FetchError(f"GET {response.url} returned {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        preview = response.text[:120].replace("\n", " ")
        raise FetchError(f"GET {response.url} returned non-JSON response: {preview!r}") from exc


def get_bytes(
    url: str,
    params: dict[str, Any] | None = None,
    timeout: int = 60,
    retries: int = 3,
) -> bytes:
    response = request_with_retries(url, params=params, timeout=timeout, retries=retries)
    if response.status_code >= 400:
        raise FetchError(f"GET {response.url} returned {response.status_code}")
    return response.content


def polite_pause(seconds: float = 1.0) -> None:
    time.sleep(seconds)
