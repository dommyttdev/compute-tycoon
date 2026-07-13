from collections import deque
from dataclasses import dataclass
from enum import Enum
from threading import Condition, Thread

from hardware_sim.devices import (
    GpuDevice,
    MemoryModule,
    NetworkInterface,
    Processor,
    StorageDevice,
)
from hardware_sim.snapshots import HardwareSnapshot, NodeSnapshot
from hardware_sim.work import WorkInfo


class NodeRole(str, Enum):
    UNASSIGNED = "unassigned"
    APPLICATION_SERVER = "application_server"
    DATABASE_SERVER = "database_server"
    STORAGE_SERVER = "storage_server"
    NETWORK_SWITCH = "network_switch"
    ROUTER = "router"
    GPU_WORKER = "gpu_worker"


@dataclass(frozen=True)
class NodeDevices:
    cpu: Processor
    memory: MemoryModule
    storage: StorageDevice
    gpus: tuple[GpuDevice, ...] = ()
    network_interfaces: tuple[NetworkInterface, ...] = ()

    @property
    def primary_gpu(self):
        if not self.gpus:
            raise RuntimeError("Node has no GPU")
        return self.gpus[0]

    @property
    def primary_network_interface(self):
        if not self.network_interfaces:
            raise RuntimeError("Node has no network interface")
        return self.network_interfaces[0]


class Node:
    def __init__(
        self,
        id: str,
        name: str,
        role: NodeRole,
        devices: NodeDevices,
        executor: object,
        workers: int | None = None,
        event_log: object | None = None,
    ):
        if not id:
            raise ValueError("id must not be empty")
        if not name:
            raise ValueError("name must not be empty")

        worker_count = workers or devices.cpu.parallelism
        if worker_count < 1:
            raise ValueError("workers must be greater than 0")

        self.id = id
        self.name = name
        self.role = role
        self.devices = devices
        self.executor = executor
        self.event_log = event_log

        self._work_pool = deque()
        self._current_works = set()
        self._worked = set()
        self._failed = {}

        self._condition = Condition()
        self._is_stopped = False

        self._threads = [
            Thread(target=self._run, name=f"{id}-worker-{index}", daemon=True)
            for index in range(1, worker_count + 1)
        ]
        started_threads: list[Thread] = []
        try:
            for thread in self._threads:
                thread.start()
                started_threads.append(thread)
        except BaseException:
            with self._condition:
                self._is_stopped = True
                self._condition.notify_all()
            for thread in started_threads:
                try:
                    thread.join()
                except BaseException:
                    pass
            raise

    @property
    def cpu(self):
        return self.devices.cpu

    @property
    def memory(self):
        return self.devices.memory

    @property
    def storage(self):
        return self.devices.storage

    @property
    def gpus(self):
        return self.devices.gpus

    @property
    def network_interfaces(self):
        return self.devices.network_interfaces

    def put(self, work_info: WorkInfo):
        with self._condition:
            if self._is_stopped:
                raise RuntimeError("Cannot put work into a stopped node")

            self._work_pool.append(work_info)
            self._condition.notify()

    def log(self, message: str):
        if self.event_log is None:
            print(message)
            return
        self.event_log.record(self.id, message)

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

        return NodeSnapshot(
            id=self.id,
            name=self.name,
            role=self.role,
            hardware=HardwareSnapshot(
                cpu=self.cpu.snapshot(),
                memory=self.memory.snapshot(),
                storage=self.storage.snapshot(),
                queued_works=queued_works,
                running_works=running_works,
                completed_works=completed_works,
                failed_works=failed_works,
                gpus=tuple(gpu.snapshot() for gpu in self.gpus),
                network_interfaces=tuple(
                    network_interface.snapshot()
                    for network_interface in self.network_interfaces
                ),
            ),
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
                self.executor.execute(work_info, self)
                succeeded = True
            except Exception as error:
                self.log(f"Failed: node={self.id}, id={work_info.id}, reason={error}")
                with self._condition:
                    self._failed[work_info] = error
            finally:
                with self._condition:
                    self._current_works.discard(work_info)
                    if succeeded:
                        self._worked.add(work_info)
                    self._condition.notify_all()
