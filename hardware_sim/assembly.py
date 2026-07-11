from collections.abc import Callable
from dataclasses import dataclass
from typing import NamedTuple

from hardware_sim.catalog import PartsCatalog
from hardware_sim.devices import (
    GpuDevice,
    MemoryModule,
    NetworkInterface,
    Processor,
    StorageDevice,
)
from hardware_sim.executors import executor_for_role
from hardware_sim.module import HardwareModule
from hardware_sim.node import Node, NodeDevices, NodeRole
from hardware_sim.parts import (
    MotherboardConfig,
    PcieSlotConfig,
)


@dataclass(frozen=True)
class NodeAssemblyConfig:
    id: str
    name: str
    role: NodeRole
    motherboard: str
    processors: tuple[str, ...] = ()
    memory_modules: tuple[str, ...] = ()
    storage_devices: tuple[str, ...] = ()
    gpus: tuple[str, ...] = ()
    expansion_network_interfaces: tuple[str, ...] = ()
    workers: int | None = None


class NodeBuilder:
    def __init__(
        self,
        catalog: PartsCatalog,
        event_log: object | None = None,
    ):
        self.catalog = catalog
        self.event_log = event_log

    def build(self, assembly: NodeAssemblyConfig):
        sink = self._sink_for(assembly.id)
        devices = self._build_devices(assembly, sink=sink)
        return Node(
            id=assembly.id,
            name=assembly.name,
            role=assembly.role,
            devices=devices,
            executor=executor_for_role(assembly.role),
            workers=assembly.workers,
            event_log=self.event_log,
        )

    def build_module(self, assembly: NodeAssemblyConfig):
        devices = self._build_devices(assembly)

        return HardwareModule(
            cpu=devices.cpu,
            memory=devices.memory,
            storage=devices.storage,
            workers=assembly.workers,
        )

    def validate(self, assembly: NodeAssemblyConfig):
        self._build_devices(assembly)

    def _sink_for(self, node_id: str) -> Callable[[str], None]:
        if self.event_log is None:
            return print
        return self.event_log.sink(node_id)

    def _build_devices(
        self,
        assembly: NodeAssemblyConfig,
        sink: Callable[[str], None] = print,
    ):
        _require_one("processors", assembly.processors)
        _require_one("memory_modules", assembly.memory_modules)
        _require_one("storage_devices", assembly.storage_devices)

        motherboard = self.catalog.motherboard(assembly.motherboard)
        processors = tuple(
            self.catalog.processor(processor) for processor in assembly.processors
        )
        memory_modules = tuple(
            self.catalog.memory_module(memory) for memory in assembly.memory_modules
        )
        storage_devices = tuple(
            self.catalog.storage_device(storage) for storage in assembly.storage_devices
        )
        gpus = tuple(self.catalog.gpu(gpu) for gpu in assembly.gpus)
        expansion_network_interfaces = tuple(
            self.catalog.network_interface(network_interface)
            for network_interface in assembly.expansion_network_interfaces
        )

        _validate_motherboard_assembly(
            motherboard=motherboard,
            processors=processors,
            memory_modules=memory_modules,
            storage_devices=storage_devices,
            gpus=gpus,
            expansion_network_interfaces=expansion_network_interfaces,
        )

        return NodeDevices(
            cpu=_build_processor(processors, sink=sink),
            memory=_build_memory(memory_modules, sink=sink),
            storage=_build_storage(storage_devices, sink=sink),
            gpus=tuple(_build_gpu(gpu, sink=sink) for gpu in gpus),
            network_interfaces=tuple(
                [
                    *_build_onboard_network_interfaces(motherboard, sink=sink),
                    *(
                        _build_network_interface(
                            network_interface,
                            sink=sink,
                        )
                        for network_interface in expansion_network_interfaces
                    ),
                ]
            ),
        )


def _require_one(name: str, values: tuple[str, ...]):
    if not values:
        raise ValueError(f"{name} must not be empty")


class PcieRequirement(NamedTuple):
    label: str
    generation: int
    lanes: int


def _build_processor(
    processors,
    sink: Callable[[str], None] = print,
):
    return Processor(
        cores=sum(processor.cores for processor in processors),
        clock_frequency_hz=min(
            processor.clock_frequency_hz for processor in processors
        ),
        name=" + ".join(processor.name for processor in processors),
        sink=sink,
    )


def _build_memory(
    memory_modules,
    sink: Callable[[str], None] = print,
):
    return MemoryModule(
        capacity=sum(memory.capacity for memory in memory_modules),
        name=" + ".join(memory.name for memory in memory_modules),
        sink=sink,
    )


def _build_storage(
    storage_devices,
    sink: Callable[[str], None] = print,
):
    return StorageDevice(
        capacity=sum(storage.capacity for storage in storage_devices),
        read_speed=sum(storage.read_speed for storage in storage_devices),
        write_speed=sum(storage.write_speed for storage in storage_devices),
        latency=min(storage.latency for storage in storage_devices),
        queue_depth=sum(storage.queue_depth for storage in storage_devices),
        name=" + ".join(storage.name for storage in storage_devices),
        sink=sink,
    )


def _build_gpu(gpu, sink: Callable[[str], None] = print):
    return GpuDevice(
        compute_units=gpu.compute_units,
        compute_tflops=gpu.compute_tflops,
        memory_capacity=gpu.memory_capacity,
        memory_bandwidth=gpu.memory_bandwidth,
        name=gpu.name,
        sink=sink,
    )


def _build_network_interface(
    network_interface,
    sink: Callable[[str], None] = print,
):
    return NetworkInterface(
        bandwidth=network_interface.bandwidth,
        latency=network_interface.latency,
        ports=network_interface.ports,
        queue_depth=network_interface.queue_depth,
        name=network_interface.name,
        sink=sink,
    )


def _build_onboard_network_interfaces(
    motherboard: MotherboardConfig,
    sink: Callable[[str], None] = print,
):
    network_interfaces = []
    for port in motherboard.onboard_lan_ports:
        for index in range(1, port.count + 1):
            network_interfaces.append(
                NetworkInterface(
                    bandwidth=port.bandwidth,
                    latency=port.latency,
                    ports=1,
                    queue_depth=port.queue_depth,
                    name=(
                        f"{motherboard.name} {port.connector} "
                        f"{port.bandwidth}Mb LAN {index}"
                    ),
                    sink=sink,
                )
            )
    return tuple(network_interfaces)


def _validate_motherboard_assembly(
    motherboard: MotherboardConfig,
    processors,
    memory_modules,
    storage_devices,
    gpus,
    expansion_network_interfaces,
):
    _validate_processors(motherboard, processors)
    _validate_memory(motherboard, memory_modules)
    _validate_storage(motherboard, storage_devices)
    _validate_pcie(
        motherboard,
        tuple(
            [
                *(
                    PcieRequirement(
                        label=gpu.name,
                        generation=gpu.pcie_generation_required,
                        lanes=gpu.pcie_lanes_required,
                    )
                    for gpu in gpus
                ),
                *(
                    PcieRequirement(
                        label=network_interface.name,
                        generation=network_interface.pcie_generation_required,
                        lanes=network_interface.pcie_lanes_required,
                    )
                    for network_interface in expansion_network_interfaces
                    if network_interface.pcie_generation_required is not None
                    and network_interface.pcie_lanes_required is not None
                ),
            ]
        ),
    )


def _validate_processors(motherboard: MotherboardConfig, processors):
    available = _count_by_key(
        motherboard.cpu_sockets,
        key=lambda socket: socket.socket_type,
        count=lambda socket: socket.count,
    )
    requested = _count_by_key(
        processors,
        key=lambda processor: processor.socket_type,
        count=lambda processor: 1,
    )
    _ensure_counts_fit("CPU socket", requested, available)


def _validate_memory(motherboard: MotherboardConfig, memory_modules):
    available = _count_by_key(
        motherboard.memory_slots,
        key=lambda slot: slot.memory_type,
        count=lambda slot: slot.count,
    )
    requested = _count_by_key(
        memory_modules,
        key=lambda memory: memory.memory_type,
        count=lambda memory: 1,
    )
    _ensure_counts_fit("memory slot", requested, available)

    total_capacity = sum(memory.capacity for memory in memory_modules)
    if (
        motherboard.max_memory_capacity is not None
        and total_capacity > motherboard.max_memory_capacity
    ):
        raise ValueError(
            f"Memory capacity {total_capacity} exceeds "
            f"{motherboard.name} limit {motherboard.max_memory_capacity}"
        )

    for memory in memory_modules:
        if memory.ecc and not motherboard.supports_ecc:
            raise ValueError(
                f"{motherboard.name} does not support ECC memory: {memory.name}"
            )

        matching_slots = [
            slot
            for slot in motherboard.memory_slots
            if slot.memory_type == memory.memory_type
        ]
        if not matching_slots:
            continue
        max_capacity = max(
            (
                slot.max_capacity_per_slot
                for slot in matching_slots
                if slot.max_capacity_per_slot is not None
            ),
            default=None,
        )
        if max_capacity is not None and memory.capacity > max_capacity:
            raise ValueError(
                f"{memory.name} capacity {memory.capacity} exceeds "
                f"{motherboard.name} per-slot limit {max_capacity}"
            )


def _validate_storage(motherboard: MotherboardConfig, storage_devices):
    available = _count_by_key(
        motherboard.storage_connectors,
        key=lambda connector: connector.connector_type,
        count=lambda connector: connector.count,
    )
    requested = _count_by_key(
        storage_devices,
        key=lambda storage: storage.connector_type,
        count=lambda storage: 1,
    )
    _ensure_counts_fit("storage connector", requested, available)


def _validate_pcie(
    motherboard: MotherboardConfig,
    requirements: tuple[PcieRequirement, ...],
):
    slots = [
        PcieSlotConfig(
            generation=slot.generation,
            lanes=slot.lanes,
            count=1,
        )
        for slot in motherboard.pcie_slots
        for _ in range(slot.count)
    ]
    slots.sort(key=lambda slot: (slot.generation, slot.lanes))

    for requirement in sorted(requirements, key=lambda item: item.lanes):
        for index, slot in enumerate(slots):
            if (
                slot.generation >= requirement.generation
                and slot.lanes >= requirement.lanes
            ):
                slots.pop(index)
                break
        else:
            raise ValueError(
                f"No PCIe slot on {motherboard.name} can accept "
                f"{requirement.label} "
                f"(PCIe {requirement.generation} x{requirement.lanes})"
            )


def _count_by_key(values, key, count):
    counts = {}
    for value in values:
        item_key = key(value)
        counts[item_key] = counts.get(item_key, 0) + count(value)
    return counts


def _ensure_counts_fit(kind: str, requested: dict, available: dict):
    for key, requested_count in requested.items():
        available_count = available.get(key, 0)
        if requested_count > available_count:
            raise ValueError(
                f"Not enough {kind}s for {key}: "
                f"requested={requested_count}, available={available_count}"
            )
