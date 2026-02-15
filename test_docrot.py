"""Tests for DocRot documentation rot detection engine."""
import json
import pytest
from pathlib import Path
from docrot import scan_doc, scan_repo, fmt, to_sarif, ScanResult


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "helpers.py").write_text("def greet(): pass\n")
    (tmp_path / "docs").mkdir()
    return tmp_path


def test_broken_link_detected(repo):
    doc = repo / "docs" / "guide.md"
    doc.write_text("See [setup](../missing-file.md) for details.\n")
    issues = scan_doc(doc, repo)
    assert len(issues) == 1
    assert issues[0].kind == "broken_link"
    assert "missing-file.md" in issues[0].message


def test_valid_link_no_issue(repo):
    (repo / "docs" / "other.md").write_text("# Other\n")
    doc = repo / "docs" / "guide.md"
    doc.write_text("See [other](other.md) for more.\n")
    issues = scan_doc(doc, repo)
    assert len(issues) == 0


def test_stale_import_detected(repo):
    doc = repo / "docs" / "guide.md"
    doc.write_text("Use the util module:\n\n    from utils import helper\n")
    issues = scan_doc(doc, repo)
    stale = [i for i in issues if i.kind == "stale_symbol"]
    assert len(stale) == 1
    assert "utils" in stale[0].message


def test_valid_import_no_issue(repo):
    doc = repo / "docs" / "guide.md"
    doc.write_text("Use helpers:\n\n    from src.helpers import greet\n")
    issues = scan_doc(doc, repo)
    stale = [i for i in issues if i.kind == "stale_symbol"]
    assert len(stale) == 0


def test_code_block_drift_detected(repo):
    doc = repo / "docs" / "guide.md"
    doc.write_text("Example:\n```python\nfrom old_module import thing\n```\n")
    issues = scan_doc(doc, repo)
    drift = [i for i in issues if i.kind == "code_drift"]
    assert len(drift) == 1
    assert "old_module" in drift[0].message


def test_code_block_valid_import_no_drift(repo):
    doc = repo / "docs" / "guide.md"
    doc.write_text("Example:\n```python\nfrom src.helpers import greet\n```\n")
    issues = scan_doc(doc, repo)
    assert len(issues) == 0


def test_scan_repo_finds_issues_across_files(repo):
    (repo / "docs" / "a.md").write_text("[broken](nonexistent.md)\n")
    (repo / "docs" / "b.md").write_text("[ok](a.md)\n")
    result = scan_repo(repo)
    assert result.docs_scanned >= 2
    assert any(i.kind == "broken_link" for i in result.issues)


def test_json_output_format(repo):
    (repo / "docs" / "a.md").write_text("[x](nope.md)\n")
    result = scan_repo(repo)
    parsed = json.loads(fmt(result, "json"))
    assert parsed["total_issues"] >= 1
    assert isinstance(parsed["issues"], list)
    assert parsed["issues"][0]["kind"] == "broken_link"


def test_sarif_output_structure(repo):
    (repo / "docs" / "a.md").write_text("[x](nope.md)\n")
    result = scan_repo(repo)
    sarif = to_sarif(result)
    assert sarif["version"] == "2.1.0"
    assert len(sarif["runs"]) == 1
    assert len(sarif["runs"][0]["results"]) >= 1


def test_clean_repo_no_issues(repo):
    (repo / "docs" / "clean.md").write_text("# Clean Doc\nNo links or imports here.\n")
    result = scan_repo(repo)
    assert len(result.issues) == 0
    assert "no rot" in fmt(result, "text").lower()


def test_max_docs_limit(repo):
    for i in range(5):
        (repo / "docs" / f"doc{i}.md").write_text(f"# Doc {i}\n")
    result = scan_repo(repo, max_docs=2)
    assert result.docs_scanned == 2


def test_external_link_skipped_by_default(repo):
    doc = repo / "docs" / "guide.md"
    doc.write_text("See [Google](https://google.com) for info.\n")
    issues = scan_doc(doc, repo, check_urls=False)
    assert len(issues) == 0
