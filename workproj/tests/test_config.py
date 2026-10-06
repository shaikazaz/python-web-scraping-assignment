import importlib


def test_env_settings(monkeypatch, tmp_path):
    monkeypatch.setenv("SCRAPER_DELAY", "0.25")
    monkeypatch.setenv("SCRAPER_TIMEOUT", "4.5")
    monkeypatch.setenv("SCRAPER_MAX_RETRIES", "2")
    monkeypatch.setenv("SCRAPER_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("SCRAPER_LOG_LEVEL", "DEBUG")
    import config
    importlib.reload(config)
    assert config.REQUEST_DELAY == 0.25
    assert config.TIMEOUT == 4.5
    assert config.MAX_RETRIES == 2
    assert config.OUTPUT_DIR == tmp_path
    assert config.LOG_LEVEL == "DEBUG"


def test_invalid_env_falls_back(monkeypatch, caplog):
    monkeypatch.setenv("SCRAPER_DELAY", "-1")
    monkeypatch.setenv("SCRAPER_TIMEOUT", "bad")
    monkeypatch.setenv("SCRAPER_MAX_RETRIES", "-2")
    import config
    importlib.reload(config)
    assert config.REQUEST_DELAY == 0.5
    assert config.TIMEOUT == 10.0
    assert config.MAX_RETRIES == 3
