"""Pinned hanshof historical-membership seed adapter."""

from __future__ import annotations

import csv
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from market_strats.universe.contracts import UniverseContractError, require_safe_relative_path
from market_strats.universe.hashing import sha256_file


@dataclass(frozen=True)
class HistoricalMembershipSeed:
    snapshots: tuple[tuple[date, frozenset[str]], ...]
    current_rows: tuple[dict[str, str], ...]
    first_observed_by_ticker: dict[str, date]
    file_hashes: dict[str, str]
    source_commit: str


def _run_git(args: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def prepare_pinned_repository(
    *,
    repository_url: str,
    destination: Path,
    expected_commit: str,
    git_runner: Callable[[list[str], Path | None], str] = _run_git,
) -> None:
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    git_runner(["clone", "--no-checkout", repository_url, str(destination)], None)
    git_runner(["checkout", "--detach", expected_commit], destination)


def _parse_historical(
    path: Path,
) -> tuple[
    tuple[tuple[date, frozenset[str]], ...],
    dict[str, date],
]:
    snapshots: list[tuple[date, frozenset[str]]] = []
    first_observed: dict[str, date] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["date", "tickers"]:
            raise UniverseContractError("Historical membership seed schema changed unexpectedly")
        for row in reader:
            observed = date.fromisoformat(row["date"])
            tickers = frozenset(item.strip().upper() for item in row["tickers"].split(",") if item)
            if not tickers:
                raise UniverseContractError("Historical membership row contains no tickers")
            snapshots.append((observed, tickers))
            for ticker in tickers:
                first_observed.setdefault(ticker, observed)
    if not snapshots:
        raise UniverseContractError("Historical membership seed is empty")
    return tuple(snapshots), first_observed


def _parse_current(path: Path) -> tuple[dict[str, str], ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"symbol", "security", "cik", "date"}
        if reader.fieldnames is None or not required <= set(reader.fieldnames):
            raise UniverseContractError("Current constituent seed schema changed unexpectedly")
        return tuple(dict(row) for row in reader)


def load_pinned_membership_seed(
    *,
    repository_root: Path,
    expected_commit: str,
    expected_hashes: dict[str, str],
) -> HistoricalMembershipSeed:
    if not repository_root.is_dir():
        raise UniverseContractError("Pinned membership repository is missing")
    actual_commit = _run_git(["rev-parse", "HEAD"], repository_root)
    if actual_commit != expected_commit:
        raise UniverseContractError("Pinned membership repository commit mismatch")
    relative_files = {
        "historical": require_safe_relative_path(
            "sp_500_historical_components.csv", "historical membership file"
        ),
        "current": require_safe_relative_path("sp500_constituents.csv", "current membership file"),
        "licence": require_safe_relative_path("LICENSE", "membership licence file"),
    }
    file_hashes: dict[str, str] = {}
    for key, relative in relative_files.items():
        path = repository_root / relative
        if not path.is_file():
            raise UniverseContractError(f"Pinned membership source missing required {key} file")
        digest = sha256_file(path)
        expected = expected_hashes.get(relative.as_posix())
        if expected is not None and digest.lower() != expected.lower():
            raise UniverseContractError(f"Pinned membership {key} file hash mismatch")
        file_hashes[relative.as_posix()] = digest
    snapshots, first_observed = _parse_historical(repository_root / relative_files["historical"])
    current = _parse_current(repository_root / relative_files["current"])
    return HistoricalMembershipSeed(
        snapshots=snapshots,
        current_rows=current,
        first_observed_by_ticker=first_observed,
        file_hashes=file_hashes,
        source_commit=actual_commit,
    )
