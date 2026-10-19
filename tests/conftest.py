"""Pytest configuration and shared fixtures."""

import sqlite3
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from src.t2s.config import AppConfig


@pytest.fixture
def sample_config() -> AppConfig:
    return AppConfig()


@pytest.fixture
def fixture_db_path() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = Path(tmp_dir) / "fixture_test.sqlite"
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE artists (
                artist_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                country TEXT
            );
        """
        )
        cursor.execute(
            """
            CREATE TABLE albums (
                album_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                artist_id INTEGER,
                FOREIGN KEY (artist_id) REFERENCES artists(artist_id)
            );
        """
        )

        cursor.execute(
            "INSERT INTO artists VALUES (1, 'The Beatles', 'UK'), (2, 'Nirvana', 'USA');"
        )
        cursor.execute("INSERT INTO albums VALUES (101, 'Abbey Road', 1), (102, 'Nevermind', 2);")

        conn.commit()
        conn.close()

        yield str(db_file)
