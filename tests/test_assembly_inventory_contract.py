from __future__ import annotations

from copy import deepcopy

import pytest

from hardware_sim import (
    BuildRequest,
    ComputeTycoonGame,
    CpuSocketConfig,
    GpuConfig,
    MemoryConfig,
    MemorySlotConfig,
    MotherboardConfig,
    NodeRole,
    PartsCatalog,
    PcieSlotConfig,
    ProcessorConfig,
    StorageConfig,
    StorageConnectorConfig,
)


def _catalog() -> PartsCatalog:
    return PartsCatalog(
        motherboards={
            "mb.compatible": MotherboardConfig(
                name="Compatible board",
                cpu_sockets=(CpuSocketConfig("socket-a", 1),),
                memory_slots=(MemorySlotConfig("ddr5", 2, 64),),
                pcie_slots=(PcieSlotConfig(4, 16, 1),),
                onboard_lan_ports=(),
                storage_connectors=(StorageConnectorConfig("nvme", 1, 4_000),),
                max_memory_capacity=128,
                supports_ecc=True,
            ),
            "mb.limited": MotherboardConfig(
                name="Limited board",
                cpu_sockets=(CpuSocketConfig("socket-b", 1),),
                memory_slots=(MemorySlotConfig("ddr4", 1, 16),),
                pcie_slots=(PcieSlotConfig(3, 8, 1),),
                onboard_lan_ports=(),
                storage_connectors=(StorageConnectorConfig("sata", 1, 600),),
                max_memory_capacity=16,
                supports_ecc=False,
            ),
        },
        processors={
            "cpu.a": ProcessorConfig(4, 3_000_000_000, socket_type="socket-a"),
            "cpu.b": ProcessorConfig(4, 3_000_000_000, socket_type="socket-b"),
        },
        memory={
            "memory.ddr5.ecc": MemoryConfig(32, memory_type="ddr5", ecc=True),
            "memory.ddr4": MemoryConfig(16, memory_type="ddr4"),
            "memory.ddr4.ecc": MemoryConfig(16, memory_type="ddr4", ecc=True),
        },
        storage={
            "storage.nvme": StorageConfig(
                1_000, 1_000, 800, 0.1, 32, connector_type="nvme"
            ),
            "storage.sata": StorageConfig(
                1_000, 500, 400, 1.0, 16, connector_type="sata"
            ),
        },
        gpus={
            "gpu.pcie4x16": GpuConfig(
                16, 10.0, 16, 500, pcie_generation_required=4, pcie_lanes_required=16
            ),
        },
    )


def _request(**changes: object) -> BuildRequest:
    values: dict[str, object] = {
        "node_id": "node-1",
        "role": NodeRole.APPLICATION_SERVER,
        "motherboard": "mb.compatible",
        "processors": ("cpu.a",),
        "memory_modules": ("memory.ddr5.ecc",),
        "storage_devices": ("storage.nvme",),
        "gpus": ("gpu.pcie4x16",),
    }
    values.update(changes)
    return BuildRequest(**values)  # type: ignore[arg-type]


def _buy_request_parts(game: ComputeTycoonGame, request: BuildRequest) -> None:
    game.buy_part("motherboards", request.motherboard)
    for part_id in request.processors:
        game.buy_part("processors", part_id)
    for part_id in request.memory_modules:
        game.buy_part("memory", part_id)
    for part_id in request.storage_devices:
        game.buy_part("storage", part_id)
    for part_id in request.gpus:
        game.buy_part("gpus", part_id)


@pytest.fixture
def game() -> ComputeTycoonGame:
    return ComputeTycoonGame(catalog=_catalog(), save_path=None, load_save=False)


def test_valid_assembly_registers_node_and_consumes_parts(
    game: ComputeTycoonGame,
) -> None:
    request = _request()
    _buy_request_parts(game, request)
    version_before = game.state_version

    node = game.build_node(request)

    assert game.nodes == {request.node_id: node}
    assert game.state_version == version_before + 1
    assert game.inventory.part_quantity("motherboards", request.motherboard) == 0
    assert game.inventory.part_quantity("processors", request.processors[0]) == 0
    assert game.inventory.part_quantity("memory", request.memory_modules[0]) == 0
    assert game.inventory.part_quantity("storage", request.storage_devices[0]) == 0
    assert game.inventory.part_quantity("gpus", request.gpus[0]) == 0


def test_build_node_duplicate_id_does_not_consume_new_parts(
    game: ComputeTycoonGame,
) -> None:
    request = _request()
    _buy_request_parts(game, request)
    original_node = game.build_node(request)
    _buy_request_parts(game, request)
    inventory_before_rejection = deepcopy(game.inventory.to_dict())
    topology_before_rejection = (
        tuple(game.topology.nodes),
        game.topology.cables,
        game.topology.addresses,
        game.topology.routes,
    )
    version_before_rejection = game.state_version

    try:
        with pytest.raises(ValueError, match="already exists"):
            game.build_node(request)

        assert game.nodes == {request.node_id: original_node}
        assert (
            tuple(game.topology.nodes),
            game.topology.cables,
            game.topology.addresses,
            game.topology.routes,
        ) == topology_before_rejection
        assert game.inventory.to_dict() == inventory_before_rejection
        assert game.state_version == version_before_rejection
    finally:
        game.stop_all()


def test_missing_inventory_does_not_change_game(game: ComputeTycoonGame) -> None:
    request = _request()
    game.buy_part("motherboards", request.motherboard)
    inventory_before = deepcopy(game.inventory.to_dict())
    version_before = game.state_version

    with pytest.raises(ValueError, match="Missing purchased part"):
        game.build_node(request)

    assert game.nodes == {}
    assert game.inventory.to_dict() == inventory_before
    assert game.state_version == version_before


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {
                "motherboard": "mb.limited",
                "processors": ("cpu.a",),
                "memory_modules": ("memory.ddr4",),
                "storage_devices": ("storage.sata",),
                "gpus": (),
            },
            "CPU sockets",
        ),
        (
            {
                "motherboard": "mb.limited",
                "processors": ("cpu.b",),
                "memory_modules": ("memory.ddr4.ecc",),
                "storage_devices": ("storage.sata",),
                "gpus": (),
            },
            "does not support ECC",
        ),
        (
            {
                "motherboard": "mb.limited",
                "processors": ("cpu.b",),
                "memory_modules": ("memory.ddr5.ecc",),
                "storage_devices": ("storage.sata",),
                "gpus": (),
            },
            "memory slots",
        ),
        (
            {
                "motherboard": "mb.limited",
                "processors": ("cpu.b",),
                "memory_modules": ("memory.ddr4",),
                "storage_devices": ("storage.nvme",),
                "gpus": (),
            },
            "storage connectors",
        ),
        (
            {
                "motherboard": "mb.limited",
                "processors": ("cpu.b",),
                "memory_modules": ("memory.ddr4",),
                "storage_devices": ("storage.sata",),
            },
            "No PCIe slot",
        ),
    ],
    ids=["socket", "ecc", "slot", "storage-connector", "pcie"],
)
def test_invalid_assembly_does_not_change_game(
    game: ComputeTycoonGame, changes: dict[str, object], message: str
) -> None:
    request = _request(**changes)
    _buy_request_parts(game, request)
    inventory_before = deepcopy(game.inventory.to_dict())
    version_before = game.state_version

    with pytest.raises(ValueError, match=message):
        game.build_node(request)

    assert game.nodes == {}
    assert game.inventory.to_dict() == inventory_before
    assert game.state_version == version_before
