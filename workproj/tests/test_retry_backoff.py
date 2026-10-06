import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import config
from scrapers.base_scraper import BaseScraper


class Handler(BaseHTTPRequestHandler):
    calls = 0
    status_sequence = [503, 200]

    def do_GET(self):
        type(self).calls += 1
        status = type(self).status_sequence[min(type(self).calls - 1, len(type(self).status_sequence) - 1)]
        self.send_response(status)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    Handler.calls = 0
    Handler.status_sequence = [503, 200]
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    thread.join()


def test_retry_503_then_200(monkeypatch, server):
    monkeypatch.setattr(config, "BACKOFF_FACTOR", 0.01)
    monkeypatch.setattr(config, "MAX_RETRIES", 3)
    scraper = BaseScraper(f"http://127.0.0.1:{server.server_port}", delay=0, check_robots=False)
    soup = scraper.fetch(f"http://127.0.0.1:{server.server_port}/")
    assert soup is not None
    assert Handler.calls == 2


def test_always_500_retries_then_fails(monkeypatch):
    monkeypatch.setattr(config, "BACKOFF_FACTOR", 0.01)
    monkeypatch.setattr(config, "MAX_RETRIES", 3)
    Handler.calls = 0
    Handler.status_sequence = [500]
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        scraper = BaseScraper(f"http://127.0.0.1:{srv.server_port}", delay=0, check_robots=False)
        assert scraper.fetch(f"http://127.0.0.1:{srv.server_port}/") is None
        assert Handler.calls == 4
    finally:
        srv.shutdown()
        thread.join()


def test_404_is_not_retried(monkeypatch):
    monkeypatch.setattr(config, "BACKOFF_FACTOR", 0.01)
    monkeypatch.setattr(config, "MAX_RETRIES", 3)
    Handler.calls = 0
    Handler.status_sequence = [404]
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        scraper = BaseScraper(f"http://127.0.0.1:{srv.server_port}", delay=0, check_robots=False)
        assert scraper.fetch(f"http://127.0.0.1:{srv.server_port}/") is None
        assert Handler.calls == 1
    finally:
        srv.shutdown()
        thread.join()


def test_adapter_retry_properties(monkeypatch):
    monkeypatch.setattr(config, "MAX_RETRIES", 3)
    scraper = BaseScraper("http://example.com", delay=0, check_robots=False)
    adapter = scraper.session.get_adapter("http://")
    retry = adapter.max_retries
    assert retry.total == 3
    assert set(retry.status_forcelist) == set(config.RETRY_STATUS)


def test_connection_refused_does_not_raise(monkeypatch):
    monkeypatch.setattr(config, "MAX_RETRIES", 0)
    scraper = BaseScraper("http://127.0.0.1:1", delay=0, check_robots=False)
    assert scraper.fetch("http://127.0.0.1:1/") is None
