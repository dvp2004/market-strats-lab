from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_required_mi0_documents_exist() -> None:
    required = [
        "docs/architecture.md",
        "docs/model_objective.md",
        "docs/reproducibility.md",
        "docs/repository_consolidation.md",
        "docs/research_history.md",
        "docs/intelligence/README.md",
        "configs/intelligence/universe_mi1.yaml",
        "configs/intelligence/mi2_research_registry.yaml",
    ]
    for relative_path in required:
        assert (ROOT / relative_path).is_file(), relative_path


def test_mi1_scope_excludes_macro_and_execution() -> None:
    scope = (ROOT / "docs/intelligence/README.md").read_text(encoding="utf-8").lower()
    assert "macro data begins no earlier than mi-3" in scope
    assert "broker integration" in scope
    assert "portfolio construction or simulation" in scope


def test_public_data_directories_are_gitignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/data/raw/*" in gitignore
    assert "/data/normalized/*" in gitignore
    assert "/data/private/*" in gitignore


def test_no_execution_modules_exist() -> None:
    prohibited_modules = ["alpaca.py", "broker.py", "execution.py", "orders.py"]
    package = ROOT / "src" / "market_strats" / "intelligence"
    for module_name in prohibited_modules:
        assert not (package / module_name).exists(), module_name
