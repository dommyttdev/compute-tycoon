from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessorConfig:
    cores: int
    clock_frequency_hz: int
    name: str = "CPU"
    socket_type: str = "generic-cpu"


@dataclass(frozen=True)
class MemoryConfig:
    capacity: int
    name: str = "RAM"
    memory_type: str = "generic-memory"
    ecc: bool = False


@dataclass(frozen=True)
class StorageConfig:
    capacity: int
    read_speed: int
    write_speed: int
    latency: float
    queue_depth: int
    name: str = "Storage"
    connector_type: str = "generic-storage"


@dataclass(frozen=True)
class GpuConfig:
    compute_units: int
    compute_tflops: float
    memory_capacity: int
    memory_bandwidth: int
    name: str = "GPU"
    pcie_generation_required: int = 1
    pcie_lanes_required: int = 16


@dataclass(frozen=True)
class NetworkInterfaceConfig:
    bandwidth: int
    latency: float
    ports: int
    queue_depth: int
    name: str = "NIC"
    connector: str | None = None
    pcie_generation_required: int | None = None
    pcie_lanes_required: int | None = None


@dataclass(frozen=True)
class CableConfig:
    bandwidth: int
    name: str = "Cable"
    connector: str | None = None


@dataclass(frozen=True)
class CpuSocketConfig:
    socket_type: str
    count: int


@dataclass(frozen=True)
class MemorySlotConfig:
    memory_type: str
    count: int
    max_capacity_per_slot: int | None = None


@dataclass(frozen=True)
class PcieSlotConfig:
    generation: int
    lanes: int
    count: int


@dataclass(frozen=True)
class LanPortConfig:
    connector: str
    bandwidth: int
    count: int
    latency: float = 0.001
    queue_depth: int = 16


@dataclass(frozen=True)
class StorageConnectorConfig:
    connector_type: str
    count: int
    bandwidth: int


@dataclass(frozen=True)
class MotherboardConfig:
    name: str
    cpu_sockets: tuple[CpuSocketConfig, ...]
    memory_slots: tuple[MemorySlotConfig, ...]
    pcie_slots: tuple[PcieSlotConfig, ...]
    onboard_lan_ports: tuple[LanPortConfig, ...]
    storage_connectors: tuple[StorageConnectorConfig, ...] = ()
    form_factor: str | None = None
    chipset: str | None = None
    max_memory_capacity: int | None = None
    supports_ecc: bool = False
