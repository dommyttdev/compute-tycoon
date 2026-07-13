from __future__ import annotations

from copy import deepcopy

import pytest

from hardware_sim import (
    ComputeTycoonGame,
    CpuRequirement,
    NodeRole,
    ResourceRequirements,
    WorkInfo,
)
from hardware_sim.workloads import (
    CpuRequirementProfile,
    InfrastructureWorkloadProfile,
    InfrastructureWorkStepProfile,
    WorkloadCatalog,
)

CABLE_ID = "cable.cat6.patch"


@pytest.fixture
def game() -> ComputeTycoonGame:
    value = ComputeTycoonGame(save_path=None, load_save=False)
    try:
        yield value
    finally:
        value.stop_all()


def _place_server(
    game: ComputeTycoonGame,
    node_id: str,
    role: NodeRole = NodeRole.APPLICATION_SERVER,
) -> None:
    game.buy_server(role)
    game.add_node(node_id, role)


def _two_node_workloads() -> WorkloadCatalog:
    cpu = (CpuRequirementProfile((1, 1), (1, 1)),)
    return WorkloadCatalog(
        [
            InfrastructureWorkloadProfile(
                kind="two-node",
                steps=(
                    InfrastructureWorkStepProfile("source", cpu),
                    InfrastructureWorkStepProfile("target", cpu),
                ),
            )
        ]
    )


def test_placing_a_purchased_server_consumes_it_only_after_success(
    game: ComputeTycoonGame,
) -> None:
    game.buy_server(NodeRole.APPLICATION_SERVER, quantity=2)
    version_before_placement = game.state_version
    game.add_node("node-1", NodeRole.APPLICATION_SERVER)
    assert game.state_version == version_before_placement + 1
    inventory_before_failure = deepcopy(game.inventory.to_dict())
    version_before_failure = game.state_version

    with pytest.raises(ValueError, match="already exists"):
        game.add_node("node-1", NodeRole.APPLICATION_SERVER)

    assert game.inventory.servers[NodeRole.APPLICATION_SERVER.value] == 1
    assert game.inventory.to_dict() == inventory_before_failure
    assert game.state_version == version_before_failure


def test_connect_consumes_a_cable_and_failed_connect_leaves_state_unchanged(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "left")
    _place_server(game, "right")
    game.buy_cable(CABLE_ID, quantity=2)
    game.connect("left:lan0", "right:lan0", CABLE_ID)
    topology_before_failure = game.topology
    inventory_before_failure = deepcopy(game.inventory.to_dict())
    version_before_failure = game.state_version

    with pytest.raises(ValueError, match="already connected"):
        game.connect("left:lan0", "right:lan0", CABLE_ID)

    assert game.inventory.cables[CABLE_ID] == 1
    assert game.topology is topology_before_failure
    assert game.inventory.to_dict() == inventory_before_failure
    assert game.state_version == version_before_failure


def test_network_mutations_update_topology_inventory_and_version_once(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "left")
    _place_server(game, "right")
    game.buy_cable(CABLE_ID)

    before = game.state_version
    game.connect("left:lan0", "right:lan0")
    assert game.state_version == before + 1
    assert game.inventory.cables[CABLE_ID] == 0

    before = game.state_version
    game.add_address("left:lan0", "192.0.2.10/24")
    assert game.state_version == before + 1

    before = game.state_version
    game.add_route("left", "198.51.100.0/24", interface="lan0")
    assert game.state_version == before + 1

    before = game.state_version
    cable = game.disconnect("left:lan0")
    assert game.state_version == before + 1
    assert cable.cable_id == CABLE_ID
    assert game.inventory.cables[CABLE_ID] == 1


def test_role_and_name_changes_keep_saved_build_request_consistent(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "node-1")

    before = game.state_version
    game.set_node_role("node-1", NodeRole.DATABASE_SERVER)
    assert game.state_version == before + 1

    before = game.state_version
    game.rename_server("node-1", "Primary database")
    assert game.state_version == before + 1

    saved_node = game.to_save_data()["nodes"][0]
    assert saved_node["role"] == NodeRole.DATABASE_SERVER.value
    assert saved_node["name"] == "Primary database"
    assert game.nodes["node-1"].role is NodeRole.DATABASE_SERVER
    assert game.nodes["node-1"].name == "Primary database"


def test_setting_same_game_node_role_is_a_save_state_no_op(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "node-1")
    saved_before = deepcopy(game.to_save_data())
    events_before = game.event_log.entries()
    version_before = game.state_version

    game.set_node_role("node-1", NodeRole.APPLICATION_SERVER)

    assert game.nodes["node-1"].role is NodeRole.APPLICATION_SERVER
    assert game.to_save_data() == saved_before
    assert game.event_log.entries() == events_before
    assert game.state_version == version_before


def test_busy_role_change_failure_leaves_game_state_unchanged(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "node-1")
    node = game.nodes["node-1"]
    work = WorkInfo(
        1,
        ResourceRequirements(
            cpu=CpuRequirement(required_clocks=1, clock_usage_hz=1),
        ),
    )

    node.put(work)
    role_before_failure = node.role
    saved_node_before_failure = deepcopy(game.to_save_data()["nodes"][0])
    role_events_before_failure = tuple(
        entry
        for entry in game.event_log.entries("node-1")
        if entry.message.startswith("Node role set")
    )
    version_before_failure = game.state_version
    try:
        with pytest.raises(RuntimeError, match="busy"):
            game.set_node_role("node-1", NodeRole.DATABASE_SERVER)

        assert node.role is role_before_failure
        assert game.to_save_data()["nodes"][0] == saved_node_before_failure
        assert (
            tuple(
                entry
                for entry in game.event_log.entries("node-1")
                if entry.message.startswith("Node role set")
            )
            == role_events_before_failure
        )
        assert game.state_version == version_before_failure
    finally:
        node.wait_all()


def test_cross_node_workload_requires_a_route_before_running(
    game: ComputeTycoonGame,
) -> None:
    game.workloads = _two_node_workloads()
    _place_server(game, "source")
    _place_server(game, "target")
    game.add_address("source:lan0", "192.0.2.10/24")
    game.add_address("target:lan0", "192.0.2.20/24")

    with pytest.raises(ValueError, match="No route"):
        game.run_workload("two-node")

    game.buy_cable(CABLE_ID)
    game.connect("source:lan0", "target:lan0")

    assert game.run_workload("two-node") == (
        "two-node completed routes=[source -> target]",
    )
