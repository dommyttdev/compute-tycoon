import json
from dataclasses import dataclass
from pathlib import Path

from hardware_sim.assembly import NodeAssemblyConfig, NodeRole
from hardware_sim.config_paths import runtime_config_resource
from hardware_sim.infrastructure import InfrastructureConfig, NetworkLink
from hardware_sim.parts import MemoryConfig, ProcessorConfig, StorageConfig


@dataclass(frozen=True)
class HardwareConfig:
    cpu: ProcessorConfig
    memory: MemoryConfig
    storage: StorageConfig
    workers: int | None = None


@dataclass(frozen=True)
class SimulationConfig:
    monitor_interval: float
    work_id_start: int
    spawn_interval_min: float
    spawn_interval_max: float


@dataclass(frozen=True)
class RuntimeConfig:
    hardware: HardwareConfig | None
    simulation: SimulationConfig
    infrastructure: InfrastructureConfig | None = None


def load_runtime_config(path: str | Path | None = None):
    if path is None:
        with runtime_config_resource().open() as file:
            config = json.load(file)
    else:
        with Path(path).open() as file:
            config = json.load(file)

    hardware = config.get("hardware")
    infrastructure = config.get("infrastructure")
    return RuntimeConfig(
        simulation=_build_simulation_config(config["simulation"]),
        hardware=(
            _build_hardware_config(hardware) if isinstance(hardware, dict) else None
        ),
        infrastructure=(
            _build_infrastructure_config(infrastructure)
            if isinstance(infrastructure, dict)
            else None
        ),
    )


def _build_hardware_config(config: dict[str, object]):
    workers = config.get("workers")
    return HardwareConfig(
        cpu=_build_processor_config(config["cpu"]),
        memory=_build_memory_config(config["memory"]),
        storage=_build_storage_config(config["storage"]),
        workers=int(workers) if workers is not None else None,
    )


def _build_processor_config(config: dict[str, object]):
    return ProcessorConfig(
        cores=int(config["cores"]),
        clock_frequency_hz=int(config["clock_frequency_hz"]),
        name=str(config.get("name", "CPU")),
    )


def _build_memory_config(config: dict[str, object]):
    return MemoryConfig(
        capacity=int(config["capacity"]),
        name=str(config.get("name", "RAM")),
    )


def _build_storage_config(config: dict[str, object]):
    return StorageConfig(
        capacity=int(config["capacity"]),
        read_speed=int(config["read_speed"]),
        write_speed=int(config["write_speed"]),
        latency=float(config["latency"]),
        queue_depth=int(config["queue_depth"]),
        name=str(config.get("name", "Storage")),
    )


def _build_simulation_config(config: dict[str, object]):
    return SimulationConfig(
        monitor_interval=float(config["monitor_interval"]),
        work_id_start=int(config["work_id_start"]),
        spawn_interval_min=float(config["spawn_interval_min"]),
        spawn_interval_max=float(config["spawn_interval_max"]),
    )


def _build_infrastructure_config(config: dict[str, object]):
    return InfrastructureConfig(
        nodes=tuple(
            _build_node_assembly_config(node_config)
            for node_config in config.get("nodes", [])
        ),
        links=tuple(
            _build_network_link(link_config) for link_config in config.get("links", [])
        ),
    )


def _build_node_assembly_config(config: dict[str, object]):
    parts = config.get("parts", {})
    if not isinstance(parts, dict):
        raise ValueError("node parts must be a mapping")

    return NodeAssemblyConfig(
        id=str(config["id"]),
        name=str(config.get("name", config["id"])),
        role=NodeRole(str(config["role"])),
        motherboard=str(config["motherboard"]),
        processors=_part_ids(parts, "processors", "cpu"),
        memory_modules=_part_ids(parts, "memory_modules", "memory"),
        storage_devices=_part_ids(parts, "storage_devices", "storage"),
        gpus=_part_ids(parts, "gpus", "gpu"),
        expansion_network_interfaces=_part_ids(
            parts,
            "expansion_network_interfaces",
            "nic",
        ),
        workers=(int(config["workers"]) if config.get("workers") is not None else None),
    )


def _build_network_link(config: dict[str, object]):
    return NetworkLink(
        source_node=str(config["source_node"]),
        target_node=str(config["target_node"]),
        network_interface=(
            str(config["network_interface"])
            if config.get("network_interface") is not None
            else None
        ),
    )


def _part_ids(
    parts: dict[str, object],
    plural_key: str,
    legacy_key: str,
):
    value = parts.get(plural_key, parts.get(legacy_key))
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list):
        raise ValueError(f"parts.{plural_key} must be a list or string")
    return tuple(str(part_id) for part_id in value)


DEFAULT_RUNTIME_CONFIG = load_runtime_config()
