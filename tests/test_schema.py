"""Test schema serialization."""

from src.t2s.data.schema import get_sqlite_schema_ddl


def test_schema_ddl_rendering(fixture_db_path: str) -> None:
    ddl = get_sqlite_schema_ddl(fixture_db_path, include_sample_rows=False)

    assert "CREATE TABLE albums" in ddl
    assert "CREATE TABLE artists" in ddl
    assert "FOREIGN KEY (artist_id) REFERENCES artists(artist_id)" in ddl
    assert "PRIMARY KEY (artist_id)" in ddl


def test_schema_ddl_sample_rows(fixture_db_path: str) -> None:
    ddl = get_sqlite_schema_ddl(fixture_db_path, include_sample_rows=True)

    assert "-- Example rows:" in ddl
    assert "The Beatles" in ddl
    assert "Abbey Road" in ddl
