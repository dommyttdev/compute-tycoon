from collections.abc import Callable
from threading import Condition
from time import sleep

from hardware_sim.errors import ResourceCapacityError
from hardware_sim.snapshots import GpuSnapshot
from hardware_sim.work import WorkInfo

FLOPS_PER_TFLOP = 1_000_000_000_000


class GpuDevice:
    def __init__(
        self,
        compute_units: int,
        compute_tflops: float,
        memory_capacity: int,
        memory_bandwidth: int,
        name: str = "GPU",
        sink: Callable[[str], None] = print,
    ):
        if compute_units < 1:
            raise ValueError("compute_units must be greater than 0")
        if compute_tflops <= 0:
            raise ValueError("compute_tflops must be greater than 0")
        if memory_capacity < 1:
            raise ValueError("memory_capacity must be greater than 0")
        if memory_bandwidth < 1:
            raise ValueError("memory_bandwidth must be greater than 0")

        self.name = name
        self._sink = sink
        self.compute_units = compute_units
        self.compute_tflops = compute_tflops
        self.memory_capacity = memory_capacity
        self.memory_bandwidth = memory_bandwidth
        self._condition = Condition()
        self._active_jobs = 0
        self._memory_used = 0
        self._active_compute = 0
        self._total_processed_compute = 0

    @property
    def compute_flops_per_second(self):
        return int(self.compute_tflops * FLOPS_PER_TFLOP)

    def snapshot(self):
        with self._condition:
            return GpuSnapshot(
                name=self.name,
                active_jobs=self._active_jobs,
                memory_used=self._memory_used,
                memory_capacity=self.memory_capacity,
                active_compute=self._active_compute,
                total_processed_compute=self._total_processed_compute,
            )

    def process(self, work_info: WorkInfo):
        amount = work_info.gpu.compute
        memory = work_info.gpu.memory
        if memory > self.memory_capacity:
            raise ResourceCapacityError(
                f"Work id={work_info.id} needs {memory} GPU memory, "
                f"but {self.name} capacity is {self.memory_capacity}"
            )

        with self._condition:
            while self._memory_used + memory > self.memory_capacity:
                self._condition.wait()

            self._active_jobs += 1
            self._memory_used += memory
            self._active_compute += amount

        completed = False
        try:
            duration = amount / self.compute_flops_per_second
            self._sink(
                f"[{self.name}] Processing: id={work_info.id}, "
                f"compute={amount}, gpu_memory={memory}"
            )
            sleep(duration)
            completed = True
        finally:
            with self._condition:
                self._active_jobs -= 1
                self._memory_used -= memory
                self._active_compute -= amount
                if completed:
                    self._total_processed_compute += amount
                self._condition.notify_all()
