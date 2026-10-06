import argparse

import config
from main import apply_overrides, run_sources


def test_apply_overrides_sets_runtime_settings():
    old = (config.REQUEST_DELAY, config.TIMEOUT, config.MAX_RETRIES, config.MAX_PAGES)
    try:
        args = argparse.Namespace(delay=0.2, timeout=7.0, retries=1, max_pages=4, output_dir=None)
        apply_overrides(args)
        assert (config.REQUEST_DELAY, config.TIMEOUT, config.MAX_RETRIES, config.MAX_PAGES) == (0.2, 7.0, 1, 4)
    finally:
        config.REQUEST_DELAY, config.TIMEOUT, config.MAX_RETRIES, config.MAX_PAGES = old


def test_run_sources_handles_selected_fake_jobs():
    class Fake:
        failed_pages = []
        had_failures = False
        resumed = False
        def scrape(self):
            return [{"x": 1}]

    jobs = [{"name": config.QUOTES_SOURCE, "scraper_factory": Fake, "clean_fn": lambda r: r}]
    result = run_sources(jobs, parallel=False)
    assert result[0]["name"] == config.QUOTES_SOURCE
    assert result[0]["stats"]["collected"] == 1
