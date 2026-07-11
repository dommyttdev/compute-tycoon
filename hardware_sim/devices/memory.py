from collections.abc import Callable
from threading import Condition

from hardware_sim.errors import ResourceCapacityError
from hardware_sim.snapshots import MemorySnapshot
from hardware_sim.work import WorkInfo


class MemoryModule:
    def __init__(
        self,
        capacity: int,
        name: str = "RAM",
        sink: Callable[[str], None] = print,
    ):
        if capacity < 1:
            raise ValueError("capacity must be greater than 0")

        self.name = name
        self._sink = sink
        self.capacity = capacity
        self._used = 0
        self._condition = Condition()

    @property
    def used(self):
        with self._condition:
            return self._used

    @property
    def available(self):
        with self._condition:
            return self.capacity - self._used

    def snapshot(self):
        with self._condition:
            return MemorySnapshot(
                name=self.name,
                used=self._used,
                capacity=self.capacity,
            )

    def allocate(self, work_info: WorkInfo):
        amount = work_info.memory.capacity
        if amount > self.capacity:
            raise ResourceCapacityError(
                f"Work id={work_info.id} needs {amount} memory, "
                f"but {self.name} capacity is {self.capacity}"
            )

        with self._condition:
            while self._used + amount > self.capacity:
                self._condition.wait()

            self._used += amount
            self._sink(
                f"[{self.name}] Allocated: id={work_info.id}, "
                f"amount={amount}, used={self._used}/{self.capacity}"
            )

    def release(self, work_info: WorkInfo):
        amount = work_info.memory.capacity
        with self._condition:
            self._used -= amount
            self._sink(
                f"[{self.name}] Released: id={work_info.id}, "
                f"amount={amount}, used={self._used}/{self.capacity}"
            )
            self._condition.notify_all()
