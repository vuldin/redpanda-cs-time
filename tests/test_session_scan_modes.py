import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.check_coverage import _allowed_dirnames, _claude_project_dirname


def test_dirname_replaces_slashes():
    assert _claude_project_dirname("/home/alice/work") == "-home-alice-work"


def test_dirname_strips_trailing_slash():
    assert _claude_project_dirname("/home/alice/work/") == "-home-alice-work"


def test_mode_all_returns_no_filter():
    assert _allowed_dirnames("all", []) is None


def test_mode_this_repo_scopes_to_cwd():
    expected = {_claude_project_dirname(os.getcwd())}
    assert _allowed_dirnames("this_repo", []) == expected


def test_mode_allowlist_scopes_to_given_paths():
    result = _allowed_dirnames("allowlist", ["/home/alice/work", "/home/alice/other"])
    assert result == {"-home-alice-work", "-home-alice-other"}


def test_mode_allowlist_empty_means_nothing_in_scope():
    assert _allowed_dirnames("allowlist", []) == set()


def test_unknown_mode_raises():
    import pytest
    with pytest.raises(ValueError):
        _allowed_dirnames("bogus", [])


def test_scan_sessions_mode_none_touches_nothing(tmp_path, monkeypatch):
    import scripts.check_coverage as cc

    # If 'none' didn't short-circuit, this would raise/scan a bogus directory.
    monkeypatch.setattr(cc, "CLAUDE_PROJECTS_DIR", str(tmp_path / "does-not-exist"))
    result = cc.scan_sessions("2026-01-01", "2026-01-02", "none", [], [])
    assert result == []


def test_scan_sessions_this_repo_skips_other_projects(tmp_path, monkeypatch):
    import json as jsonmod

    import scripts.check_coverage as cc

    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    monkeypatch.setattr(cc, "CLAUDE_PROJECTS_DIR", str(projects_dir))

    this_dirname = cc._claude_project_dirname(os.getcwd())
    in_scope = projects_dir / this_dirname
    out_of_scope = projects_dir / "-some-other-project"
    in_scope.mkdir()
    out_of_scope.mkdir()

    record = jsonmod.dumps({
        "sessionId": "s1", "cwd": os.getcwd(), "timestamp": "2026-01-01T10:00:00Z",
        "type": "user", "message": {"content": "hello"},
    })
    a_file = in_scope / "a.jsonl"
    b_file = out_of_scope / "b.jsonl"
    a_file.write_text(record + "\n")
    b_file.write_text(record.replace("s1", "s2") + "\n")

    # scan_sessions filters by file mtime against the date range; pin both
    # files' mtimes inside the window being scanned regardless of wall-clock time.
    import time as timemod
    mtime = timemod.mktime(timemod.strptime("2026-01-01", "%Y-%m-%d"))
    os.utime(a_file, (mtime, mtime))
    os.utime(b_file, (mtime, mtime))

    results = cc.scan_sessions("2026-01-01", "2026-01-01", "this_repo", [], [])
    session_ids = {r["session_id"] for r in results}
    assert session_ids == {"s1"}
