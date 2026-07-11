from __future__ import annotations

from threading import Event, Lock

import pytest

from hardware_sim import (
    ApplicationServerExecutor,
    CpuRequirement,
    EventLog,
    MemoryModule,
    MemoryRequirement,
    Node,
    NodeDevices,
    NodeRole,
    Processor,
    ResourceRequirements,
    StorageDevice,
    WorkInfo,
)


def _work(work_id: int, **requirements: object) -> WorkInfo:
    return WorkInfo(work_id, ResourceRequirements(**requirements))


def _devices(*, cpu_sink=lambda _message: None) -> NodeDevices:
    return NodeDevices(
        cpu=Processor(cores=1, clock_frequency_hz=1, sink=cpu_sink),
        memory=MemoryModule(capacity=1, sink=lambda _message: None),
        storage=StorageDevice(
            capacity=1,
            read_speed=1,
            write_speed=1,
            sink=lambda _message: None,
        ),
    )


class _ControlledExecutor:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.started = Event()
        self.release = Event()
        self.error = error

    def execute(self, work_info: WorkInfo, node: object) -> None:
        self.started.set()
        assert self.release.wait(timeout=1)
        if self.error is not None:
            raise self.error


def test_worker_records_success_and_wait_all_waits_for_completion() -> None:
    executor = _ControlledExecutor()
    node = Node(
        "node-1",
        "Node 1",
        NodeRole.APPLICATION_SERVER,
        _devices(),
        executor,
        workers=1,
    )
    work = _work(1, cpu=CpuRequirement(1))
    try:
        node.put(work)
        assert executor.started.wait(timeout=1)
        assert node.is_working(work)

        executor.release.set()
        node.wait_all()

        assert node.is_worked(work)
        assert not node.is_failed(work)
        assert not node.is_busy
    finally:
        executor.release.set()
        node.stop()


def test_worker_records_failure_and_logs_it() -> None:
    executor = _ControlledExecutor(error=RuntimeError("controlled failure"))
    event_log = EventLog()
    node = Node(
        "node-1",
        "Node 1",
        NodeRole.APPLICATION_SERVER,
        _devices(),
        executor,
        workers=1,
        event_log=event_log,
    )
    work = _work(1, cpu=CpuRequirement(1))
    try:
        node.put(work)
        assert executor.started.wait(timeout=1)
        executor.release.set()
        node.wait_all()

        assert node.is_failed(work)
        assert not node.is_worked(work)
        assert "controlled failure" in event_log.entries()[0].message
    finally:
        executor.release.set()
        node.stop()


def test_stopped_node_rejects_new_work() -> None:
    executor = _ControlledExecutor()
    executor.release.set()
    node = Node(
        "node-1",
        "Node 1",
        NodeRole.APPLICATION_SERVER,
        _devices(),
        executor,
        workers=1,
    )
    node.stop()

    with pytest.raises(RuntimeError, match="stopped node"):
        node.put(_work(1, cpu=CpuRequirement(1)))


def test_application_executor_releases_memory_when_cpu_fails() -> None:
    def fail_processing(_message: str) -> None:
        raise RuntimeError("processor failed")

    devices = _devices(cpu_sink=fail_processing)
    node = Node(
        "node-1",
        "Node 1",
        NodeRole.APPLICATION_SERVER,
        devices,
        ApplicationServerExecutor(),
        workers=1,
        event_log=EventLog(),
    )
    work = _work(
        1,
        cpu=CpuRequirement(1),
        memory=MemoryRequirement(1),
    )
    try:
        node.put(work)
        node.wait_all()

        assert node.is_failed(work)
        assert devices.memory.used == 0
        assert devices.cpu.snapshot().active_cores == 0
    finally:
        node.stop()


class _MemoryContentionExecutor:
    def __init__(self) -> None:
        self._lock = Lock()
        self.started = 0
        self.first_allocated = Event()
        self.release_first = Event()

    def execute(self, work_info: WorkInfo, node: Node) -> None:
        with self._lock:
            self.started += 1
            order = self.started
        node.memory.allocate(work_info)
        try:
            if order == 1:
                self.first_allocated.set()
                assert self.release_first.wait(timeout=1)
        finally:
            node.memory.release(work_info)


def test_memory_contention_never_exceeds_capacity() -> None:
    executor = _MemoryContentionExecutor()
    devices = _devices()
    node = Node(
        "node-1",
        "Node 1",
        NodeRole.APPLICATION_SERVER,
        devices,
        executor,
        workers=2,
    )
    first = _work(1, memory=MemoryRequirement(1))
    second = _work(2, memory=MemoryRequirement(1))
    try:
        node.put(first)
        assert executor.first_allocated.wait(timeout=1)
        node.put(second)

        assert devices.memory.used == devices.memory.capacity
        executor.release_first.set()
        node.wait_all()

        assert node.is_worked(first)
        assert node.is_worked(second)
        assert devices.memory.used == 0
    finally:
        executor.release_first.set()
        node.stop()
