from collections import deque
from threading import Condition, Thread

from hardware_sim.devices import MemoryModule, Processor, StorageDevice
from hardware_sim.snapshots import HardwareSnapshot
from hardware_sim.work import WorkInfo

DEFAULT_CPU_CORES = 1
DEFAULT_CPU_CLOCK_FREQUENCY_HZ = 200
DEFAULT_MEMORY_CAPACITY = 1024
DEFAULT_STORAGE_CAPACITY = 10_000
DEFAULT_STORAGE_READ_SPEED = 300
DEFAULT_STORAGE_WRITE_SPEED = 150
DEFAULT_STORAGE_LATENCY = 0.01


class HardwareModule:
    def __init__(
        self,
        throughput: int | None = None,
        cpu: Processor | None = None,
        memory: MemoryModule | None = None,
        storage: StorageDevice | None = None,
        workers: int | None = None,
    ):
        self.cpu = cpu or Processor(
            cores=DEFAULT_CPU_CORES,
            clock_frequency_hz=throughput or DEFAULT_CPU_CLOCK_FREQUENCY_HZ,
        )
        self.memory = memory or MemoryModule(capacity=DEFAULT_MEMORY_CAPACITY)
        self.storage = storage or StorageDevice(
            capacity=DEFAULT_STORAGE_CAPACITY,
            read_speed=DEFAULT_STORAGE_READ_SPEED,
            write_speed=DEFAULT_STORAGE_WRITE_SPEED,
            latency=DEFAULT_STORAGE_LATENCY,
        )

        worker_count = workers or self.cpu.parallelism
        if worker_count < 1:
            raise ValueError("workers must be greater than 0")

        self._work_pool = deque()
        self._current_works = set()
        self._worked = set()
        self._failed = {}

        self._condition = Condition()
        self._is_stopped = False

        self._threads = [
            Thread(target=self._run, name=f"hardware-worker-{index}", daemon=True)
            for index in range(1, worker_count + 1)
        ]
        for thread in self._threads:
            thread.start()

    def _run(self):
        while True:
            with self._condition:
                while not self._work_pool and not self._is_stopped:
                    self._condition.wait()

                if self._is_stopped and not self._work_pool:
                    return

                work_info = self._work_pool.popleft()
                self._current_works.add(work_info)

            succeeded = False
            try:
                self._execute(work_info)
                succeeded = True
            except Exception as error:
                print(f"Failed: id={work_info.id}, reason={error}")
                with self._condition:
                    self._failed[work_info] = error
            finally:
                with self._condition:
                    self._current_works.discard(work_info)
                    if succeeded:
                        self._worked.add(work_info)
                    self._condition.notify_all()

    def _execute(self, work_info: WorkInfo):
        print(
            f"Executing: id={work_info.id}, kind={work_info.kind}, "
            f"clocks={work_info.cpu.required_clocks}, "
            f"ram={work_info.memory.capacity}, "
            f"clock_usage={work_info.cpu.clock_usage_hz or self.cpu.clock_frequency_hz}, "
            f"read={work_info.storage.read}, write={work_info.storage.write}"
        )
        self.memory.allocate(work_info)
        try:
            self.storage.read(work_info)
            self.cpu.process(work_info)
            self.storage.write(work_info)
        finally:
            self.memory.release(work_info)
        print(f"Executed: id={work_info.id}, kind={work_info.kind}")

    def put(self, work_info: WorkInfo):
        with self._condition:
            if self._is_stopped:
                raise RuntimeError("Cannot put work into a stopped hardware module")

            self._work_pool.append(work_info)
            self._condition.notify()

    @property
    def is_busy(self):
        with self._condition:
            return bool(self._current_works) or bool(self._work_pool)

    def is_working(self, work_info: WorkInfo):
        with self._condition:
            return work_info in self._current_works or work_info in self._work_pool

    def is_worked(self, work_info: WorkInfo):
        with self._condition:
            return work_info in self._worked

    def is_failed(self, work_info: WorkInfo):
        with self._condition:
            return work_info in self._failed

    def snapshot(self):
        with self._condition:
            queued_works = len(self._work_pool)
            running_works = len(self._current_works)
            completed_works = len(self._worked)
            failed_works = len(self._failed)

        return HardwareSnapshot(
            cpu=self.cpu.snapshot(),
            memory=self.memory.snapshot(),
            storage=self.storage.snapshot(),
            queued_works=queued_works,
            running_works=running_works,
            completed_works=completed_works,
            failed_works=failed_works,
        )

    def wait_all(self):
        with self._condition:
            while self._current_works or self._work_pool:
                self._condition.wait()

    def stop(self):
        with self._condition:
            self._is_stopped = True
            self._condition.notify_all()

        for thread in self._threads:
            thread.join()
