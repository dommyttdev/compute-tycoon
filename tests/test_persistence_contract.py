from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from hardware_sim import AutosaveWorker, ComputeTycoonGame, NodeRole


@dataclass
class _SnapshotSource:
    state_version: int = 0
    data: dict[str, object] | None = None

    def save_snapshot(self) -> tuple[int, dict[str, object]]:
        return self.state_version, self.data or {}


def test_game_save_load_roundtrip_preserves_inventory_and_nodes(tmp_path: Path) -> None:
    save_path = tmp_path / "save.json"
    game = ComputeTycoonGame(save_path=None, load_save=False)
    loaded: ComputeTycoonGame | None = None
    try:
        game.buy_server(NodeRole.APPLICATION_SERVER, quantity=2)
        game.add_node("app-1", NodeRole.APPLICATION_SERVER)
        game.rename_server("app-1", "Primary application")
        version, data = game.save_snapshot()
        source = _SnapshotSource(state_version=version, data=data)
        worker = AutosaveWorker(source, save_path)
        source.state_version += 1
        worker.flush()

        loaded = ComputeTycoonGame(save_path=save_path, load_save=True)

        assert loaded.inventory.to_dict() == game.inventory.to_dict()
        assert loaded.to_save_data() == game.to_save_data()
        assert loaded.nodes["app-1"].name == "Primary application"
        assert loaded.state_version == 0
    finally:
        if loaded is not None:
            loaded.stop_all()
        game.stop_all()


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda game: game.buy_server(NodeRole.APPLICATION_SERVER),
            id="buy-server",
        ),
        pytest.param(
            lambda game: game.buy_cable("cable.cat6.patch"),
            id="buy-cable",
        ),
        pytest.param(
            lambda game: game.buy_part("processors", "cpu.starter.4core"),
            id="buy-part",
        ),
    ],
)
def test_save_relevant_mutation_increments_state_version(mutate: object) -> None:
    game = ComputeTycoonGame(save_path=None, load_save=False)
    version_before = game.state_version

    mutate(game)  # type: ignore[operator]

    assert game.state_version == version_before + 1


def test_autosave_flush_writes_only_when_version_changes(tmp_path: Path) -> None:
    save_path = tmp_path / "save.json"
    source = _SnapshotSource(data={"value": "first"})
    worker = AutosaveWorker(source, save_path)

    worker.flush()
    assert not save_path.exists()

    source.state_version = 1
    worker.flush()
    assert json.loads(save_path.read_text(encoding="utf-8")) == {"value": "first"}

    source.data = {"value": "not written"}
    worker.flush()
    assert json.loads(save_path.read_text(encoding="utf-8")) == {"value": "first"}


def test_autosave_stop_flushes_changed_snapshot_without_waiting(tmp_path: Path) -> None:
    save_path = tmp_path / "save.json"
    source = _SnapshotSource(data={"stopped": True})
    worker = AutosaveWorker(source, save_path, interval=60)
    worker.start()
    source.state_version = 1

    worker.stop()

    assert json.loads(save_path.read_text(encoding="utf-8")) == {"stopped": True}
    assert not worker._thread.is_alive()


def test_autosave_replaces_destination_after_temporary_file_is_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_path = tmp_path / "nested" / "save.json"
    temporary_path = save_path.with_suffix(".json.tmp")
    save_path.parent.mkdir(parents=True)
    save_path.write_text('{"old": true}', encoding="utf-8")
    source = _SnapshotSource(data={"new": True})
    worker = AutosaveWorker(source, save_path)
    observed: dict[str, object] = {}
    original_replace = Path.replace

    def observe_replace(path: Path, target: Path) -> Path:
        observed["source"] = path
        observed["temporary_data"] = json.loads(path.read_text(encoding="utf-8"))
        observed["destination_before_replace"] = json.loads(
            target.read_text(encoding="utf-8")
        )
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", observe_replace)

    source.state_version = 1
    worker.flush()

    assert observed == {
        "source": temporary_path,
        "temporary_data": {"new": True},
        "destination_before_replace": {"old": True},
    }
    assert json.loads(save_path.read_text(encoding="utf-8")) == {"new": True}
    assert not temporary_path.exists()
