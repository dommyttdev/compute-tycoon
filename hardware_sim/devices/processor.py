from collections.abc import Callable
from threading import Condition
from time import sleep

from hardware_sim.snapshots import ProcessorSnapshot
from hardware_sim.work import WorkInfo


class Processor:
    def __init__(
        self,
        cores: int,
        clock_frequency_hz: int | None = None,
        name: str = "CPU",
        cycles_per_second: int | None = None,
        sink: Callable[[str], None] = print,
    ):
        if cores < 1:
            raise ValueError("cores must be greater than 0")
        if clock_frequency_hz is None:
            clock_frequency_hz = cycles_per_second
        if clock_frequency_hz is None:
            raise ValueError("clock_frequency_hz is required")
        if clock_frequency_hz < 1:
            raise ValueError("clock_frequency_hz must be greater than 0")

        self.name = name
        self._sink = sink
        self.cores = cores
        self.clock_frequency_hz = clock_frequency_hz
        self._condition = Condition()
        self._active_cores = 0
        self._used_clock_hz = 0
        self._active_required_clocks = 0
        self._total_processed_clocks = 0

    @property
    def cycles_per_second(self):
        return self.clock_frequency_hz

    @property
    def total_clock_hz(self):
        return self.cores * self.clock_frequency_hz

    @property
    def parallelism(self):
        return self.cores

    @property
    def active_cores(self):
        with self._condition:
            return self._active_cores

    def snapshot(self):
        with self._condition:
            return ProcessorSnapshot(
                name=self.name,
                active_cores=self._active_cores,
                total_cores=self.cores,
                clock_frequency_hz=self.clock_frequency_hz,
                used_clock_hz=self._used_clock_hz,
                active_required_clocks=self._active_required_clocks,
                total_processed_clocks=self._total_processed_clocks,
            )

    def process(self, work_info: WorkInfo):
        clock_usage_hz = work_info.cpu.clock_usage_hz or self.clock_frequency_hz
        allocated_clock_hz = min(clock_usage_hz, self.total_clock_hz)
        required_cores = self._cores_for_clock_usage(allocated_clock_hz)

        self._acquire_clock_capacity(
            work_info=work_info,
            required_cores=required_cores,
            allocated_clock_hz=allocated_clock_hz,
        )
        completed = False
        try:
            duration = work_info.cpu.required_clocks / allocated_clock_hz
            self._sink(
                f"[{self.name}] Processing: id={work_info.id}, "
                f"required_clocks={work_info.cpu.required_clocks}, "
                f"clock_usage={allocated_clock_hz}Hz, "
                f"cores={self.active_cores}/{self.cores}"
            )
            sleep(duration)
            completed = True
        finally:
            with self._condition:
                self._active_cores -= required_cores
                self._used_clock_hz -= allocated_clock_hz
                self._active_required_clocks -= work_info.cpu.required_clocks
                if completed:
                    self._total_processed_clocks += work_info.cpu.required_clocks
                self._condition.notify_all()

    def _acquire_clock_capacity(
        self,
        work_info: WorkInfo,
        required_cores: int,
        allocated_clock_hz: int,
    ):
        with self._condition:
            while self._active_cores + required_cores > self.cores:
                self._condition.wait()

            self._active_cores += required_cores
            self._used_clock_hz += allocated_clock_hz
            self._active_required_clocks += work_info.cpu.required_clocks

    def _cores_for_clock_usage(self, clock_usage_hz: int):
        return max(
            1,
            (clock_usage_hz + self.clock_frequency_hz - 1) // self.clock_frequency_hz,
        )
