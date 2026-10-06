from storage.postgres import PostgresStore, StoreError, mask_dsn


def test_mask_dsn():
    assert "secret" not in mask_dsn("postgresql://user:secret@localhost/db")
    assert "***" in mask_dsn("postgresql://user:secret@localhost/db")


def test_lazy_import_error(monkeypatch):
    store = PostgresStore("postgresql://user:secret@localhost/db")
    assert store.connection is None
    # The test environment intentionally has no psycopg2 dependency.
    try:
        store.connect()
    except StoreError as exc:
        assert "secret" not in str(exc)
        assert "psycopg2" in str(exc)
    else:
        raise AssertionError("Expected optional dependency error")


def test_fake_upsert_uses_parameterized_sql_and_counts():
    class Cursor:
        def __init__(self): self.calls = []
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def execute(self, sql, values):
            self.calls.append((sql, values))
        def fetchone(self): return (True,)

    class Conn:
        def __init__(self): self.cur = Cursor()
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def cursor(self): return self.cur

    store = PostgresStore.__new__(PostgresStore)
    store.connection = Conn()
    store.masked_dsn = "postgresql://user:***@localhost/db"
    store.ensure_schema = lambda: None
    record = {
        "source": "Books to Scrape", "name_or_title": "Book", "category": "Travel",
        "price": 1.0, "rating": 5, "author": None, "tags": None,
        "source_url": "https://example.com", "scraped_at": "2026-01-01T00:00:00+00:00",
        "description": None, "availability": "In stock", "author_url": None,
    }
    result = store.upsert_records([record], ["fp1"])
    sql, values = store.connection.cur.calls[0]
    assert "%s" in sql
    assert values[1] == "Books to Scrape"
    assert "Book" not in sql
    assert result == {"inserted": 1, "updated": 0}
