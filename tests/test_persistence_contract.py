from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

import pytest

from hardware_sim import AutosaveWorker, ComputeTycoonGame, NodeRole, SaveDataError


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
        game.buy_server(NodeRole.APPLICATION_SERVER, quantity=3)
        game.add_node("app-1", NodeRole.APPLICATION_SERVER)
        game.add_node("app-2", NodeRole.APPLICATION_SERVER)
        game.rename_server("app-1", "Primary application")
        game.buy_cable("cable.cat6.patch", quantity=2)
        game.connect("app-1:lan0", "app-2:lan0")
        game.add_address("app-1:lan0", "192.0.2.10/24")
        game.add_address("app-2:lan0", "192.0.2.20/24")
        game.add_route("app-1", "198.51.100.0/24", interface="lan0")
        version, data = game.save_snapshot()
        source = _SnapshotSource(state_version=version, data=data)
        worker = AutosaveWorker(source, save_path)
        source.state_version += 1
        worker.flush()

        loaded = ComputeTycoonGame(save_path=save_path, load_save=True)

        assert loaded.inventory.to_dict() == game.inventory.to_dict()
        assert set(loaded.nodes) == set(game.nodes) == {"app-1", "app-2"}
        assert loaded.topology.cables == game.topology.cables
        assert loaded.topology.addresses == game.topology.addresses
        assert loaded.topology.routes == game.topology.routes
        assert loaded.to_save_data() == game.to_save_data()
        assert loaded.nodes["app-1"].name == "Primary application"
        assert loaded.state_version == 0
    finally:
        if loaded is not None:
            loaded.stop_all()
        game.stop_all()


def test_game_load_rejects_unsupported_save_version(tmp_path: Path) -> None:
    save_path = tmp_path / "save.json"
    save_path.write_text(json.dumps({"version": 999}), encoding="utf-8")

    with pytest.raises(SaveDataError, match="999"):
        ComputeTycoonGame(save_path=save_path, load_save=True)


@pytest.mark.parametrize(
    "version",
    [
        pytest.param(True, id="boolean"),
        pytest.param(1.0, id="float"),
    ],
)
def test_game_load_rejects_non_integer_save_version(
    tmp_path: Path, version: object
) -> None:
    save_path = tmp_path / "save.json"
    save_path.write_text(json.dumps({"version": version}), encoding="utf-8")

    with pytest.raises(SaveDataError, match=r"(?i)(?:unsupported|invalid).*version"):
        ComputeTycoonGame(save_path=save_path, load_save=True)


def test_game_load_rejects_save_without_version(tmp_path: Path) -> None:
    save_path = tmp_path / "save.json"
    save_path.write_text(json.dumps({}), encoding="utf-8")

    with pytest.raises(SaveDataError, match=r"(?i)version.*missing"):
        ComputeTycoonGame(save_path=save_path, load_save=True)


def test_game_load_rejects_malformed_json(tmp_path: Path) -> None:
    save_path = tmp_path / "save.json"
    save_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(SaveDataError, match=r"(?i)invalid save data"):
        ComputeTycoonGame(save_path=save_path, load_save=True)


def test_game_load_rejects_invalid_utf8(tmp_path: Path) -> None:
    save_path = tmp_path / "save.json"
    save_path.write_bytes(b"\xff\xfe\xfa")

    with pytest.raises(SaveDataError, match="Invalid save data"):
        ComputeTycoonGame(save_path=save_path, load_save=True)


def test_game_load_rejects_invalid_nested_save_field_type(tmp_path: Path) -> None:
    save_path = tmp_path / "save.json"
    save_path.write_text(
        json.dumps(
            {
                "version": 1,
                "inventory": [],
                "nodes": [],
                "network": {"links": [], "addresses": [], "routes": []},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SaveDataError, match="Invalid save data"):
        ComputeTycoonGame(save_path=save_path, load_save=True)


def test_failed_load_stops_workers_started_for_restored_nodes(tmp_path: Path) -> None:
    node_id = "load-cleanup-unique-node"
    source = ComputeTycoonGame(save_path=None, load_save=False)
    try:
        source.buy_server(NodeRole.APPLICATION_SERVER)
        source.add_node(node_id, NodeRole.APPLICATION_SERVER)
        save_data = source.to_save_data()
    finally:
        source.stop_all()

    network = save_data["network"]
    assert isinstance(network, dict)
    links = network["links"]
    assert isinstance(links, list)
    links.append(
        {
            "a": f"{node_id}:lan0",
            "b": f"{node_id}:missing-port",
            "cable": "cable.cat6.patch",
        }
    )
    save_path = tmp_path / "save.json"
    save_path.write_text(json.dumps(save_data), encoding="utf-8")

    with pytest.raises(SaveDataError, match="Invalid save data"):
        ComputeTycoonGame(save_path=save_path, load_save=True)

    assert not any(
        thread.is_alive() and thread.name.startswith(f"{node_id}-worker-")
        for thread in threading.enumerate()
    )


def test_load_stops_started_worker_when_next_thread_fails_to_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    node_id = "load-thread-start-failure-node"
    source = ComputeTycoonGame(save_path=None, load_save=False)
    try:
        source.buy_server(NodeRole.APPLICATION_SERVER)
        source.add_node(node_id, NodeRole.APPLICATION_SERVER)
        save_data = source.to_save_data()
    finally:
        source.stop_all()

    nodes = save_data["nodes"]
    assert isinstance(nodes, list)
    node_data = nodes[0]
    assert isinstance(node_data, dict)
    node_data["workers"] = 2
    save_path = tmp_path / "save.json"
    save_path.write_text(json.dumps(save_data), encoding="utf-8")

    original_start = threading.Thread.start
    target_starts = 0

    def fail_second_target_start(thread: threading.Thread) -> None:
        nonlocal target_starts
        if thread.name.startswith(f"{node_id}-worker-"):
            target_starts += 1
            if target_starts == 2:
                raise RuntimeError("injected thread start failure")
        original_start(thread)

    monkeypatch.setattr(threading.Thread, "start", fail_second_target_start)

    with pytest.raises(RuntimeError, match="injected thread start failure"):
        ComputeTycoonGame(save_path=save_path, load_save=True)

    assert target_starts == 2
    assert not any(
        thread.is_alive() and thread.name.startswith(f"{node_id}-worker-")
        for thread in threading.enumerate()
    )


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


def test_autosave_failed_replace_preserves_destination_and_can_retry(
    tmp_path: Path,
) -> None:
    save_path = tmp_path / "save.json"
    temporary_path = save_path.with_suffix(".json.tmp")
    save_path.mkdir()
    sentinel_path = save_path / "sentinel.txt"
    sentinel_path.write_text("keep", encoding="utf-8")
    source = _SnapshotSource(data={"saved": True})
    worker = AutosaveWorker(source, save_path)
    source.state_version = 1

    with pytest.raises(OSError):
        worker.flush()

    assert save_path.is_dir()
    assert sentinel_path.read_text(encoding="utf-8") == "keep"
    assert not temporary_path.exists()

    sentinel_path.unlink()
    save_path.rmdir()
    worker.flush()

    assert json.loads(save_path.read_text(encoding="utf-8")) == {"saved": True}


def test_autosave_serialization_failure_preserves_existing_save(
    tmp_path: Path,
) -> None:
    save_path = tmp_path / "save.json"
    temporary_path = save_path.with_suffix(".json.tmp")
    save_path.write_text(json.dumps({"old": True}), encoding="utf-8")
    source = _SnapshotSource(data={"invalid": object()})
    worker = AutosaveWorker(source, save_path)
    source.state_version = 1

    with pytest.raises(TypeError):
        worker.flush()

    assert json.loads(save_path.read_text(encoding="utf-8")) == {"old": True}
    assert not temporary_path.exists()
