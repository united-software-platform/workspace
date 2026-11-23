"""Интеграционные прогоны CLI раскладки: вход, путь, коллизии, реестр, коды."""

import json
from pathlib import Path

from layout.cli.main import main
from tests.fakes import make_run, make_taxonomy


def _run(tmp_path: Path, run_dir: Path) -> tuple[int, Path]:
    """Прогнать CLI на фиковых таксономии и корне; вернуть код и корень."""
    root = tmp_path / "space"
    taxonomy = make_taxonomy(tmp_path / "taxonomy")
    code = main([str(run_dir), "--root", str(root), "--taxonomy", str(taxonomy)])
    return code, root


def _registry(root: Path) -> list[dict]:
    path = root / "projects" / "layout-registry.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def test_accepted_run_creates_tree_and_registry(tmp_path: Path) -> None:
    run = make_run(tmp_path / "runs" / "forge")
    code, root = _run(tmp_path, run)
    assert code == 0
    assert (root / "projects" / "data-engineering" / "data-modeling" / "forge").is_dir()
    entries = _registry(root)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["name"] == "forge"
    assert entry["path"] == "projects/data-engineering/data-modeling/forge"
    assert entry["l1"] == {"id": "DOM-010", "slug": "data-engineering"}
    assert entry["l2"] == {"id": "SUB-018", "slug": "data-modeling"}
    assert entry["source"] == str(run)
    assert entry["date"]


def test_unaccepted_run_refused(tmp_path: Path) -> None:
    run = make_run(tmp_path / "runs" / "forge", accepted=False)
    code, root = _run(tmp_path, run)
    assert code == 1
    assert not (root / "projects").exists()


def test_path_uses_primary_codes(tmp_path: Path) -> None:
    run = make_run(tmp_path / "runs" / "formular", name="formular", l1="DOM-008", l2="SUB-023")
    code, root = _run(tmp_path, run)
    assert code == 0
    assert (
        root / "projects" / "software-engineering" / "ai-agent-engineering" / "formular"
    ).is_dir()


def test_invalid_name_refused_without_transform(tmp_path: Path) -> None:
    run = make_run(tmp_path / "runs" / "bad", name="Forge Lab")
    code, root = _run(tmp_path, run)
    assert code == 1
    assert not (root / "projects").exists()


def test_taxonomy_record_without_code_named(tmp_path: Path) -> None:
    run = make_run(tmp_path / "runs" / "x", l1="DOM-011")
    code, _ = _run(tmp_path, run)
    assert code == 1


def test_collision_prefixes_organization(tmp_path: Path) -> None:
    make_run(tmp_path / "runs" / "first", name="forge", organization="other")
    code, root = _run(tmp_path, tmp_path / "runs" / "first")
    assert code == 0
    make_run(tmp_path / "runs" / "second", name="forge", organization="usp")
    code, root = _run(tmp_path, tmp_path / "runs" / "second")
    assert code == 0
    assert (root / "projects" / "data-engineering" / "data-modeling" / "usp-forge").is_dir()
    assert {entry["path"] for entry in _registry(root)} == {
        "projects/data-engineering/data-modeling/forge",
        "projects/data-engineering/data-modeling/usp-forge",
    }


def test_prefix_occupied_refused(tmp_path: Path) -> None:
    make_run(tmp_path / "runs" / "a", name="forge", organization="other")
    make_run(tmp_path / "runs" / "b", name="usp-forge", organization="another")
    assert _run(tmp_path, tmp_path / "runs" / "a")[0] == 0
    assert _run(tmp_path, tmp_path / "runs" / "b")[0] == 0
    make_run(tmp_path / "runs" / "c", name="forge", organization="usp")
    code, _ = _run(tmp_path, tmp_path / "runs" / "c")
    assert code == 1


def test_rerun_idempotent(tmp_path: Path) -> None:
    run = make_run(tmp_path / "runs" / "forge")
    assert _run(tmp_path, run)[0] == 0
    code, root = _run(tmp_path, run)
    assert code == 0
    assert len(_registry(root)) == 1


def test_reassignment_updates_entry_without_duplicate(tmp_path: Path) -> None:
    make_run(tmp_path / "runs" / "old", name="forge")
    code, root = _run(tmp_path, tmp_path / "runs" / "old")
    assert code == 0
    make_run(tmp_path / "runs" / "new", name="forge", l1="DOM-008", l2="SUB-023")
    code, root = _run(tmp_path, tmp_path / "runs" / "new")
    assert code == 0
    entries = _registry(root)
    assert len(entries) == 1
    assert entries[0]["path"] == "projects/software-engineering/ai-agent-engineering/forge"
    assert (root / "projects" / "software-engineering" / "ai-agent-engineering" / "forge").is_dir()


def test_target_occupied_by_file_refused(tmp_path: Path) -> None:
    run = make_run(tmp_path / "runs" / "forge")
    taxonomy = make_taxonomy(tmp_path / "taxonomy")
    root = tmp_path / "space"
    target = root / "projects" / "data-engineering" / "data-modeling" / "forge"
    target.parent.mkdir(parents=True)
    target.write_text("не каталог", encoding="utf-8")
    code = main([str(run), "--root", str(root), "--taxonomy", str(taxonomy)])
    assert code == 1
    assert target.read_text(encoding="utf-8") == "не каталог"


def test_missing_contract_file_is_environment_error(tmp_path: Path) -> None:
    run = make_run(tmp_path / "runs" / "forge")
    (run / "classification.json").unlink()
    code, _ = _run(tmp_path, run)
    assert code == 2


def test_broken_contract_is_environment_error(tmp_path: Path) -> None:
    run = make_run(tmp_path / "runs" / "forge")
    (run / "card.json").write_text("{ не json", encoding="utf-8")
    code, _ = _run(tmp_path, run)
    assert code == 2
