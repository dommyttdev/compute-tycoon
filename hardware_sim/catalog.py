import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping, TypeVar

from hardware_sim.config_paths import parts_catalog_resource
from hardware_sim.parts import (
    CableConfig,
    CpuSocketConfig,
    GpuConfig,
    LanPortConfig,
    MemoryConfig,
    MemorySlotConfig,
    MotherboardConfig,
    NetworkInterfaceConfig,
    PcieSlotConfig,
    ProcessorConfig,
    StorageConfig,
    StorageConnectorConfig,
)

PartConfig = TypeVar("PartConfig")


@dataclass(frozen=True, init=False)
class PartsCatalog:
    motherboards: Mapping[str, MotherboardConfig]
    processors: Mapping[str, ProcessorConfig]
    memory: Mapping[str, MemoryConfig]
    storage: Mapping[str, StorageConfig]
    gpus: Mapping[str, GpuConfig]
    network_interfaces: Mapping[str, NetworkInterfaceConfig]
    cables: Mapping[str, CableConfig]

    def __init__(
        self,
        motherboards: Mapping[str, MotherboardConfig],
        processors: Mapping[str, ProcessorConfig],
        memory: Mapping[str, MemoryConfig],
        storage: Mapping[str, StorageConfig],
        gpus: Mapping[str, GpuConfig] | None = None,
        network_interfaces: Mapping[str, NetworkInterfaceConfig] | None = None,
        cables: Mapping[str, CableConfig] | None = None,
    ):
        _require_not_empty("motherboards", motherboards)
        _require_not_empty("processors", processors)
        _require_not_empty("memory", memory)
        _require_not_empty("storage", storage)

        gpus = gpus or {}
        network_interfaces = network_interfaces or {}
        cables = cables or {}

        object.__setattr__(
            self,
            "motherboards",
            MappingProxyType(dict(motherboards)),
        )
        object.__setattr__(
            self,
            "processors",
            MappingProxyType(dict(processors)),
        )
        object.__setattr__(self, "memory", MappingProxyType(dict(memory)))
        object.__setattr__(self, "storage", MappingProxyType(dict(storage)))
        object.__setattr__(self, "gpus", MappingProxyType(dict(gpus)))
        object.__setattr__(
            self,
            "network_interfaces",
            MappingProxyType(dict(network_interfaces)),
        )
        object.__setattr__(self, "cables", MappingProxyType(dict(cables)))

    def motherboard(self, part_id: str):
        return _require_part("motherboard", part_id, self.motherboards)

    def processor(self, part_id: str):
        return _require_part("processor", part_id, self.processors)

    def memory_module(self, part_id: str):
        return _require_part("memory", part_id, self.memory)

    def storage_device(self, part_id: str):
        return _require_part("storage", part_id, self.storage)

    def gpu(self, part_id: str):
        return _require_part("gpu", part_id, self.gpus)

    def network_interface(self, part_id: str):
        return _require_part("network interface", part_id, self.network_interfaces)

    def cable(self, part_id: str):
        return _require_part("cable", part_id, self.cables)


def load_parts_catalog(path: str | Path | None = None):
    if path is None:
        with parts_catalog_resource().open() as file:
            config = json.load(file)
    else:
        with Path(path).open() as file:
            config = json.load(file)

    return PartsCatalog(
        motherboards={
            part_id: _build_motherboard_config(part_config)
            for part_id, part_config in config["motherboards"].items()
        },
        processors={
            part_id: _build_processor_config(part_config)
            for part_id, part_config in config["processors"].items()
        },
        memory={
            part_id: _build_memory_config(part_config)
            for part_id, part_config in config["memory"].items()
        },
        storage={
            part_id: _build_storage_config(part_config)
            for part_id, part_config in config["storage"].items()
        },
        gpus={
            part_id: _build_gpu_config(part_config)
            for part_id, part_config in config.get("gpus", {}).items()
        },
        network_interfaces={
            part_id: _build_network_interface_config(part_config)
            for part_id, part_config in config.get(
                "network_interfaces",
                {},
            ).items()
        },
        cables={
            part_id: _build_cable_config(part_config)
            for part_id, part_config in config.get("cables", {}).items()
        },
    )


def _require_not_empty(name: str, parts: Mapping[str, object]):
    if not parts:
        raise ValueError(f"{name} must not be empty")


def _require_part(
    kind: str,
    part_id: str,
    parts: Mapping[str, PartConfig],
):
    try:
        return parts[part_id]
    except KeyError as error:
        raise KeyError(f"Unknown {kind} part: {part_id}") from error


def _build_processor_config(config: dict[str, object]):
    return ProcessorConfig(
        cores=int(config["cores"]),
        clock_frequency_hz=int(config["clock_frequency_hz"]),
        name=str(config.get("name", "CPU")),
        socket_type=str(config["socket_type"]),
    )


def _build_memory_config(config: dict[str, object]):
    return MemoryConfig(
        capacity=int(config["capacity"]),
        name=str(config.get("name", "RAM")),
        memory_type=str(config["memory_type"]),
        ecc=bool(config.get("ecc", False)),
    )


def _build_storage_config(config: dict[str, object]):
    return StorageConfig(
        capacity=int(config["capacity"]),
        read_speed=int(config["read_speed"]),
        write_speed=int(config["write_speed"]),
        latency=float(config["latency"]),
        queue_depth=int(config["queue_depth"]),
        name=str(config.get("name", "Storage")),
        connector_type=str(config["connector_type"]),
    )


def _build_gpu_config(config: dict[str, object]):
    return GpuConfig(
        compute_units=int(config["compute_units"]),
        compute_tflops=float(config["compute_tflops"]),
        memory_capacity=int(config["memory_capacity"]),
        memory_bandwidth=int(config["memory_bandwidth"]),
        name=str(config.get("name", "GPU")),
        pcie_generation_required=int(config["pcie_generation_required"]),
        pcie_lanes_required=int(config["pcie_lanes_required"]),
    )


def _build_network_interface_config(config: dict[str, object]):
    return NetworkInterfaceConfig(
        bandwidth=int(config["bandwidth"]),
        latency=float(config["latency"]),
        ports=int(config["ports"]),
        queue_depth=int(config["queue_depth"]),
        name=str(config.get("name", "NIC")),
        connector=(
            str(config["connector"]) if config.get("connector") is not None else None
        ),
        pcie_generation_required=(
            int(config["pcie_generation_required"])
            if config.get("pcie_generation_required") is not None
            else None
        ),
        pcie_lanes_required=(
            int(config["pcie_lanes_required"])
            if config.get("pcie_lanes_required") is not None
            else None
        ),
    )


def _build_cable_config(config: dict[str, object]):
    return CableConfig(
        bandwidth=int(config["bandwidth"]),
        name=str(config.get("name", "Cable")),
        connector=(
            str(config["connector"]) if config.get("connector") is not None else None
        ),
    )


def _build_motherboard_config(config: dict[str, object]):
    return MotherboardConfig(
        name=str(config["name"]),
        form_factor=(
            str(config["form_factor"])
            if config.get("form_factor") is not None
            else None
        ),
        chipset=(str(config["chipset"]) if config.get("chipset") is not None else None),
        max_memory_capacity=(
            int(config["max_memory_capacity"])
            if config.get("max_memory_capacity") is not None
            else None
        ),
        supports_ecc=bool(config.get("supports_ecc", False)),
        cpu_sockets=tuple(
            CpuSocketConfig(
                socket_type=str(socket["socket_type"]),
                count=int(socket["count"]),
            )
            for socket in config["cpu_sockets"]
        ),
        memory_slots=tuple(
            MemorySlotConfig(
                memory_type=str(slot["memory_type"]),
                count=int(slot["count"]),
                max_capacity_per_slot=(
                    int(slot["max_capacity_per_slot"])
                    if slot.get("max_capacity_per_slot") is not None
                    else None
                ),
            )
            for slot in config["memory_slots"]
        ),
        pcie_slots=tuple(
            PcieSlotConfig(
                generation=int(slot["generation"]),
                lanes=int(slot["lanes"]),
                count=int(slot["count"]),
            )
            for slot in config.get("pcie_slots", [])
        ),
        onboard_lan_ports=tuple(
            LanPortConfig(
                connector=str(port["connector"]),
                bandwidth=int(port["bandwidth"]),
                count=int(port["count"]),
                latency=float(port.get("latency", 0.001)),
                queue_depth=int(port.get("queue_depth", 16)),
            )
            for port in config.get("onboard_lan_ports", [])
        ),
        storage_connectors=tuple(
            StorageConnectorConfig(
                connector_type=str(connector["connector_type"]),
                count=int(connector["count"]),
                bandwidth=int(connector["bandwidth"]),
            )
            for connector in config.get("storage_connectors", [])
        ),
    )


DEFAULT_PARTS_CATALOG = load_parts_catalog()
