from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hardware_sim.node import NodeRole


HZ_PER_GHZ = 1_000_000_000


@dataclass(frozen=True)
class ProcessorSnapshot:
    name: str
    active_cores: int
    total_cores: int
    clock_frequency_hz: int
    used_clock_hz: int
    active_required_clocks: int
    total_processed_clocks: int

    @property
    def utilization(self):
        return self.used_clock_hz / self.total_clock_hz

    @property
    def active_clock_hz(self):
        return self.used_clock_hz

    @property
    def total_clock_hz(self):
        return self.total_cores * self.clock_frequency_hz

    @property
    def clock_frequency_ghz(self):
        return self.clock_frequency_hz / HZ_PER_GHZ


@dataclass(frozen=True)
class MemorySnapshot:
    name: str
    used: int
    capacity: int

    @property
    def utilization(self):
        return self.used / self.capacity

    @property
    def available(self):
        return self.capacity - self.used


@dataclass(frozen=True)
class StorageSnapshot:
    name: str
    active_transfers: int
    queue_depth: int
    used: int
    capacity: int
    total_read: int
    total_written: int

    @property
    def io_utilization(self):
        return self.active_transfers / self.queue_depth

    @property
    def capacity_utilization(self):
        return self.used / self.capacity

    @property
    def available(self):
        return self.capacity - self.used


@dataclass(frozen=True)
class GpuSnapshot:
    name: str
    active_jobs: int
    memory_used: int
    memory_capacity: int
    active_compute: int
    total_processed_compute: int

    @property
    def memory_utilization(self):
        return self.memory_used / self.memory_capacity

    @property
    def memory_available(self):
        return self.memory_capacity - self.memory_used


@dataclass(frozen=True)
class NetworkInterfaceSnapshot:
    name: str
    active_transfers: int
    queue_depth: int
    total_received: int
    total_sent: int

    @property
    def utilization(self):
        return self.active_transfers / self.queue_depth


@dataclass(frozen=True)
class HardwareSnapshot:
    cpu: ProcessorSnapshot
    memory: MemorySnapshot
    storage: StorageSnapshot
    queued_works: int
    running_works: int
    completed_works: int
    failed_works: int
    gpus: tuple[GpuSnapshot, ...] = ()
    network_interfaces: tuple[NetworkInterfaceSnapshot, ...] = ()


@dataclass(frozen=True)
class NodeSnapshot:
    id: str
    name: str
    role: "NodeRole"
    hardware: HardwareSnapshot
