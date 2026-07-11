from collections.abc import Callable
from threading import Event, Thread
from typing import Protocol

from hardware_sim.infrastructure import InfrastructureSnapshot
from hardware_sim.snapshots import HardwareSnapshot, NodeSnapshot

DEFAULT_MONITOR_INTERVAL = 1.0


class SnapshotSource(Protocol):
    def snapshot(self) -> object: ...


class HardwareMonitor:
    def __init__(
        self,
        module: SnapshotSource,
        interval: float = DEFAULT_MONITOR_INTERVAL,
        sink: Callable[[str], None] = print,
    ):
        if interval <= 0:
            raise ValueError("interval must be greater than 0")

        self.module = module
        self.interval = interval
        self.sink = sink
        self._stop_event = Event()
        self._thread = Thread(target=self._run, name="hardware-monitor", daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self._thread.join()

    def _run(self):
        while not self._stop_event.is_set():
            self.sink(self.format_snapshot(self.module.snapshot()))
            self._stop_event.wait(self.interval)

    @staticmethod
    def format_snapshot(
        snapshot: HardwareSnapshot | NodeSnapshot | InfrastructureSnapshot,
    ):
        if isinstance(snapshot, InfrastructureSnapshot):
            return "\n".join(
                HardwareMonitor.format_snapshot(node_snapshot)
                for node_snapshot in snapshot.nodes
            )

        prefix = "[Monitor] "
        if isinstance(snapshot, NodeSnapshot):
            prefix = (
                f"[Monitor] {snapshot.name} ({snapshot.id}, {snapshot.role.value}) | "
            )
            snapshot = snapshot.hardware

        cpu = snapshot.cpu
        memory = snapshot.memory
        storage = snapshot.storage
        gpu_parts = [
            (
                f"{gpu.name} memory={gpu.memory_utilization:.0%} "
                f"({gpu.memory_used}/{gpu.memory_capacity}), "
                f"active_jobs={gpu.active_jobs}, "
                f"processed_compute={gpu.total_processed_compute}"
            )
            for gpu in snapshot.gpus
        ]
        network_parts = [
            (
                f"{network_interface.name} network="
                f"{network_interface.utilization:.0%} "
                f"({network_interface.active_transfers}/"
                f"{network_interface.queue_depth}), "
                f"received={network_interface.total_received}, "
                f"sent={network_interface.total_sent}"
            )
            for network_interface in snapshot.network_interfaces
        ]
        extra_text = "".join(f" | {part}" for part in [*gpu_parts, *network_parts])

        return (
            prefix + f"{cpu.name}={cpu.utilization:.0%} "
            f"({cpu.active_cores}/{cpu.total_cores} cores, "
            f"{cpu.clock_frequency_ghz:.2f}GHz, "
            f"active_clock={cpu.active_clock_hz:,}Hz/"
            f"{cpu.total_clock_hz:,}Hz, "
            f"work_clocks={cpu.active_required_clocks:,}, "
            f"processed={cpu.total_processed_clocks:,}) | "
            f"{memory.name}={memory.utilization:.0%} "
            f"({memory.used}/{memory.capacity}) | "
            f"{storage.name} IO={storage.io_utilization:.0%} "
            f"({storage.active_transfers}/{storage.queue_depth}), "
            f"capacity={storage.capacity_utilization:.0%} "
            f"({storage.used}/{storage.capacity}) | "
            f"read={storage.total_read}, written={storage.total_written}"
            f"{extra_text} | "
            f"jobs queued={snapshot.queued_works}, "
            f"running={snapshot.running_works}, "
            f"done={snapshot.completed_works}, "
            f"failed={snapshot.failed_works}"
        )
