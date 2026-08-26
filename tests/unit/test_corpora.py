"""Corpora live at the workspace root; resolution finds them from anywhere."""

from __future__ import annotations

from pathlib import Path

from connections.corpora import DEFAULT_ROOT, default_root, workspace_root


def _workspace(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n', encoding="utf-8"
    )
    (tmp_path / "packages" / "member").mkdir(parents=True)
    return tmp_path


def test_workspace_root_is_found_from_a_nested_member(tmp_path):
    root = _workspace(tmp_path)
    assert workspace_root(root / "packages" / "member") == root


def test_a_plain_project_is_not_a_workspace(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "solo"\n', encoding="utf-8"
    )
    assert workspace_root(tmp_path) is None


def test_default_root_falls_back_to_the_relative_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert default_root() == DEFAULT_ROOT


def test_default_root_anchors_at_the_workspace(tmp_path, monkeypatch):
    root = _workspace(tmp_path)
    monkeypatch.chdir(root / "packages" / "member")
    assert default_root() == root / DEFAULT_ROOT
