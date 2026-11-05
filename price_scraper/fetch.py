"""HTTP layer: one polite, retrying session per thread."""
import threading
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "Mozilla/5.0 (compatible; PriceScraperDemo/1.0)"

_local = threading.local()


def _new_session() -> requests.Session:
    retry = Retry(
        total=4,
        backoff_factor=0.8,  # 0.8s, 1.6s, 3.2s ... between retries
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def get_html(url: str, delay: float = 0.0, timeout: float = 20.0) -> str:
    """Download a page and return its HTML as text.

    `delay` is a pause before each request so we never hammer the site.
    """
    session = getattr(_local, "session", None)
    if session is None:
        session = _local.session = _new_session()
    if delay:
        time.sleep(delay)
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text
