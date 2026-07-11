from collections.abc import Callable
from threading import BoundedSemaphore, Lock
from time import sleep

from hardware_sim.errors import ResourceCapacityError
from hardware_sim.snapshots import StorageSnapshot
from hardware_sim.work import WorkInfo


class StorageDevice:
    def __init__(
        self,
        capacity: int,
        read_speed: int,
        write_speed: int,
        latency: float = 0.0,
        queue_depth: int = 1,
        name: str = "Storage",
        sink: Callable[[str], None] = print,
    ):
        if capacity < 1:
            raise ValueError("capacity must be greater than 0")
        if read_speed < 1:
            raise ValueError("read_speed must be greater than 0")
        if write_speed < 1:
            raise ValueError("write_speed must be greater than 0")
        if latency < 0:
            raise ValueError("latency must be 0 or greater")
        if queue_depth < 1:
            raise ValueError("queue_depth must be greater than 0")

        self.name = name
        self._sink = sink
        self.capacity = capacity
        self.read_speed = read_speed
        self.write_speed = write_speed
        self.latency = latency
        self.queue_depth = queue_depth
        self._used = 0
        self._active_transfers = 0
        self._total_read = 0
        self._total_written = 0
        self._queue_slots = BoundedSemaphore(queue_depth)
        self._lock = Lock()

    @property
    def used(self):
        with self._lock:
            return self._used

    @property
    def available(self):
        with self._lock:
            return self.capacity - self._used

    def snapshot(self):
        with self._lock:
            return StorageSnapshot(
                name=self.name,
                active_transfers=self._active_transfers,
                queue_depth=self.queue_depth,
                used=self._used,
                capacity=self.capacity,
                total_read=self._total_read,
                total_written=self._total_written,
            )

    def read(self, work_info: WorkInfo):
        amount = work_info.storage.read
        self._transfer("Read", work_info.id, amount, self.read_speed)
        with self._lock:
            self._total_read += amount

    def write(self, work_info: WorkInfo):
        amount = work_info.storage.write
        with self._lock:
            if self._used + amount > self.capacity:
                raise ResourceCapacityError(
                    f"Work id={work_info.id} writes {amount} storage, "
                    f"but only {self.capacity - self._used} is available"
                )
            self._used += amount

        try:
            self._transfer("Wrote", work_info.id, amount, self.write_speed)
            with self._lock:
                self._total_written += amount
        except Exception:
            with self._lock:
                self._used -= amount
            raise

    def _transfer(self, action: str, work_id: int, amount: int, speed: int):
        self._queue_slots.acquire()
        try:
            with self._lock:
                self._active_transfers += 1

            duration = self.latency + amount / speed
            self._sink(f"[{self.name}] {action}: id={work_id}, amount={amount}")
            sleep(duration)
        finally:
            with self._lock:
                self._active_transfers -= 1
            self._queue_slots.release()
