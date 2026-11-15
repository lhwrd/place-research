"""Tests for settings parsing."""

from pathlib import Path

from app.core.config import Settings


def test_blank_data_paths_are_unset(monkeypatch):
    monkeypatch.setenv("RAILLINES_PATH", "  ")
    monkeypatch.setenv("HIGHWAYS_PATH", "data/highways.parquet")

    settings = Settings()

    assert settings.raillines_path is None
    assert settings.highways_path == Path("data/highways.parquet")
