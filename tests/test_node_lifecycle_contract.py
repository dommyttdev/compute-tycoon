from __future__ import annotations

from dataclasses import FrozenInstanceError
from threading import Event, Lock

import pytest

from hardware_sim import (
    ApplicationServerExecutor,
    CpuRequirement,
    DatabaseServerExecutor,
    EventLog,
    FailureReason,
    GpuDevice,
    GpuRequirement,
    GpuWorkerExecutor,
    MemoryModule,
    MemoryRequirement,
    NetworkInterface,
    NetworkRequirement,
    NetworkSwitchExecutor,
    Node,
    NodeDevices,
    NodeRole,
    Processor,
    ResourceRequirements,
    RoleExecutor,
    RouterExecutor,
    StorageDevice,
    StorageRequirement,
    StorageServerExecutor,
    WorkInfo,
)
from hardware_sim.node import NodeWorkResult


def _work(work_id: int, **requirements: object) -> WorkInfo:
    return WorkInfo(work_id, ResourceRequirements(**requirements))


def _devices(
    *,
    clock_frequency_hz: int = 1,
    cpu_sink=lambda _message: None,
) -> NodeDevices:
    return NodeDevices(
        cpu=Processor(
            cores=1,
            clock_frequency_hz=clock_frequency_hz,
            sink=cpu_sink,
        ),
        memory=MemoryModule(capacity=1, sink=lambda _message: None),
        storage=StorageDevice(
            capacity=1,
            read_speed=1,
            write_speed=1,
            sink=lambda _message: None,
        ),
    )


def test_real_node_completes_one_work_and_reports_idle_success_snapshot() -> None:
    node = Node(
        "node-1",
        "Node 1",
        NodeRole.APPLICATION_SERVER,
        _devices(clock_frequency_hz=1_000_000_000),
        ApplicationServerExecutor(),
        workers=1,
    )
    try:
        node.put(_work(1, cpu=CpuRequirement(1)))
        node.wait_all()

        snapshot = node.snapshot()
        assert snapshot.hardware.queued_works == 0
        assert snapshot.hardware.running_works == 0
        assert snapshot.hardware.completed_works == 1
        assert snapshot.hardware.failed_works == 0
        with pytest.raises(FrozenInstanceError):
            snapshot.hardware.completed_works = 2
    finally:
        node.stop()


def test_idle_node_role_change_updates_role_and_next_executor_behavior() -> None:
    cpu_messages: list[str] = []
    node = Node(
        "node-1",
        "Node 1",
        NodeRole.APPLICATION_SERVER,
        _devices(cpu_sink=cpu_messages.append),
        ApplicationServerExecutor(),
        workers=1,
    )
    work = _work(1, cpu=CpuRequirement(1))
    try:
        node.set_role(NodeRole.STORAGE_SERVER)
        node.put(work)
        node.wait_all()

        assert node.role is NodeRole.STORAGE_SERVER
        assert node.is_worked(work)
        assert cpu_messages == []
    finally:
        node.stop()


def test_busy_node_rejects_role_change_and_keeps_old_executor_behavior() -> None:
    first_started = Event()
    release_first = Event()
    cpu_messages: list[str] = []

    def hold_first_processing(message: str) -> None:
        cpu_messages.append(message)
        if "id=1," in message:
            first_started.set()
            assert release_first.wait(timeout=2)

    node = Node(
        "node-1",
        "Node 1",
        NodeRole.APPLICATION_SERVER,
        _devices(cpu_sink=hold_first_processing),
        ApplicationServerExecutor(),
        workers=1,
    )
    first = _work(1, cpu=CpuRequirement(1))
    second = _work(2, cpu=CpuRequirement(1))
    try:
        node.put(first)
        assert first_started.wait(timeout=1)
        node.put(second)
        assert node.snapshot().hardware.queued_works == 1

        with pytest.raises(RuntimeError):
            node.set_role(NodeRole.STORAGE_SERVER)

        assert node.role is NodeRole.APPLICATION_SERVER
        release_first.set()
        node.wait_all()
        assert node.is_worked(first)
        assert node.is_worked(second)
        assert len(cpu_messages) == 2
    finally:
        release_first.set()
        node.stop()


def test_setting_same_role_on_stopped_node_is_a_no_op() -> None:
    node = Node(
        "node-1",
        "Node 1",
        NodeRole.APPLICATION_SERVER,
        _devices(),
        ApplicationServerExecutor(),
        workers=1,
    )
    node.stop()
    before_change = node.snapshot()

    node.set_role(NodeRole.APPLICATION_SERVER)

    assert node.role is NodeRole.APPLICATION_SERVER
    assert node.snapshot() == before_change


def test_stopped_node_rejects_role_change_without_changing_state() -> None:
    node = Node(
        "node-1",
        "Node 1",
        NodeRole.APPLICATION_SERVER,
        _devices(),
        ApplicationServerExecutor(),
        workers=1,
    )
    node.stop()
    before_rejection = node.snapshot()

    with pytest.raises(RuntimeError):
        node.set_role(NodeRole.STORAGE_SERVER)

    assert node.role is NodeRole.APPLICATION_SERVER
    assert node.snapshot() == before_rejection


def test_single_worker_starts_accepted_work_in_fifo_order() -> None:
    processing_messages: list[str] = []
    first_started = Event()

    def record_cpu_processing(message: str) -> None:
        processing_messages.append(message)
        first_started.set()

    node = Node(
        "node-1",
        "Node 1",
        NodeRole.APPLICATION_SERVER,
        _devices(clock_frequency_hz=10, cpu_sink=record_cpu_processing),
        ApplicationServerExecutor(),
        workers=1,
    )
    try:
        node.put(_work(101, cpu=CpuRequirement(5)))
        assert first_started.wait(timeout=1)
        node.put(_work(202, cpu=CpuRequirement(1)))

        node.wait_all()

        assert len(processing_messages) == 2
        assert "id=101," in processing_messages[0]
        assert "id=202," in processing_messages[1]
    finally:
        node.stop()


def test_snapshot_distinguishes_running_work_from_queued_work() -> None:
    first_started = Event()
    release_first = Event()

    def hold_first_processing(message: str) -> None:
        if "id=601," in message:
            first_started.set()
            assert release_first.wait(timeout=2)

    node = Node(
        "node-1",
        "Node 1",
        NodeRole.APPLICATION_SERVER,
        _devices(
            clock_frequency_hz=1_000_000_000,
            cpu_sink=hold_first_processing,
        ),
        ApplicationServerExecutor(),
        workers=1,
    )
    first = _work(601, cpu=CpuRequirement(1))
    second = _work(602, cpu=CpuRequirement(1))
    try:
        node.put(first)
        assert first_started.wait(timeout=1)
        node.put(second)

        while_active = node.snapshot().hardware
        assert while_active.running_works == 1
        assert while_active.queued_works == 1

        release_first.set()
        node.wait_all()

        after_completion = node.snapshot().hardware
        assert after_completion.running_works == 0
        assert after_completion.queued_works == 0
        assert after_completion.completed_works == 2
        assert after_completion.failed_works == 0
    finally:
        release_first.set()
        node.stop()


@pytest.mark.parametrize(
    ("role", "executor_factory", "requirements", "expected_operations"),
    [
        pytest.param(
            NodeRole.APPLICATION_SERVER,
            ApplicationServerExecutor,
            {
                "network": NetworkRequirement(ingress=1, egress=1),
                "memory": MemoryRequirement(1),
                "storage": StorageRequirement(read=1, write=1),
                "cpu": CpuRequirement(1),
            },
            (
                "[NIC] Received",
                "[RAM] Allocated",
                "[Storage] Read",
                "[CPU] Processing",
                "[Storage] Wrote",
                "[NIC] Sent",
            ),
            id="application-server",
        ),
        pytest.param(
            NodeRole.DATABASE_SERVER,
            DatabaseServerExecutor,
            {
                "network": NetworkRequirement(ingress=1, egress=1),
                "memory": MemoryRequirement(1),
                "storage": StorageRequirement(read=1, write=1),
                "cpu": CpuRequirement(1),
            },
            (
                "[NIC] Received",
                "[RAM] Allocated",
                "[Storage] Read",
                "[CPU] Processing",
                "[Storage] Wrote",
                "[NIC] Sent",
            ),
            id="database-server",
        ),
        pytest.param(
            NodeRole.STORAGE_SERVER,
            StorageServerExecutor,
            {
                "network": NetworkRequirement(ingress=1, egress=1),
                "storage": StorageRequirement(read=1, write=1),
            },
            (
                "[NIC] Received",
                "[Storage] Read",
                "[Storage] Wrote",
                "[NIC] Sent",
            ),
            id="storage-server",
        ),
        pytest.param(
            NodeRole.NETWORK_SWITCH,
            NetworkSwitchExecutor,
            {"network": NetworkRequirement(ingress=1, egress=1)},
            ("[NIC] Received", "[NIC] Sent"),
            id="network-switch",
        ),
        pytest.param(
            NodeRole.ROUTER,
            RouterExecutor,
            {
                "network": NetworkRequirement(ingress=1, egress=1),
                "cpu": CpuRequirement(1),
            },
            ("[NIC] Received", "[CPU] Processing", "[NIC] Sent"),
            id="router",
        ),
        pytest.param(
            NodeRole.GPU_WORKER,
            GpuWorkerExecutor,
            {
                "memory": MemoryRequirement(1),
                "storage": StorageRequirement(read=1, write=1),
                "gpu": GpuRequirement(compute=1, memory=1),
                "cpu": CpuRequirement(1),
            },
            (
                "[RAM] Allocated",
                "[Storage] Read",
                "[GPU] Processing",
                "[CPU] Processing",
                "[Storage] Wrote",
            ),
            id="gpu-worker",
        ),
    ],
)
def test_role_executor_processes_requirements_in_documented_order(
    role: NodeRole,
    executor_factory: type[RoleExecutor],
    requirements: dict[str, object],
    expected_operations: tuple[str, ...],
) -> None:
    operation_messages: list[str] = []
    node = Node(
        "node-1",
        "Node 1",
        role,
        NodeDevices(
            cpu=Processor(
                cores=1,
                clock_frequency_hz=1_000_000_000,
                sink=operation_messages.append,
            ),
            memory=MemoryModule(capacity=10, sink=operation_messages.append),
            storage=StorageDevice(
                capacity=10,
                read_speed=1_000_000_000,
                write_speed=1_000_000_000,
                sink=operation_messages.append,
            ),
            gpus=(
                GpuDevice(
                    compute_units=1,
                    compute_tflops=1,
                    memory_capacity=10,
                    memory_bandwidth=1_000_000_000,
                    sink=operation_messages.append,
                ),
            ),
            network_interfaces=(
                NetworkInterface(
                    bandwidth=1_000_000_000,
                    latency=0,
                    ports=1,
                    queue_depth=1,
                    sink=operation_messages.append,
                ),
            ),
        ),
        executor_factory(),
        workers=1,
    )
    try:
        node.put(_work(404, **requirements))
        node.wait_all()

        assert (
            tuple(
                message.split(":", 1)[0]
                for message in operation_messages[: len(expected_operations)]
            )
            == expected_operations
        )
    finally:
        node.stop()


def test_stop_synchronously_drains_all_accepted_work() -> None:
    first_started = Event()

    def observe_processing(_message: str) -> None:
        first_started.set()

    node = Node(
        "node-1",
        "Node 1",
        NodeRole.APPLICATION_SERVER,
        _devices(clock_frequency_hz=10, cpu_sink=observe_processing),
        ApplicationServerExecutor(),
        workers=1,
    )
    first = _work(501, cpu=CpuRequirement(5))
    second = _work(502, cpu=CpuRequirement(1))
    try:
        node.put(first)
        assert first_started.wait(timeout=1)
        node.put(second)
        before_stop = node.snapshot().hardware
        assert before_stop.queued_works + before_stop.running_works > 0

        node.stop()

        after_stop = node.snapshot().hardware
        assert node.is_worked(first)
        assert node.is_worked(second)
        assert after_stop.queued_works == 0
        assert after_stop.running_works == 0
    finally:
        node.stop()


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


def test_wait_for_failed_work_returns_immutable_structured_failure() -> None:
    executor = _ControlledExecutor(error=RuntimeError("controlled internal failure"))
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
        executor.release.set()

        result = node.wait_for(work)

        assert isinstance(result, NodeWorkResult)
        assert result.status == "failed"
        assert result.value is None
        assert not isinstance(result.failure, BaseException)
        assert isinstance(result.failure, FailureReason)
        assert result.failure.code == "node_execution_failed"
        assert result.failure.message == "Node execution failed"
        with pytest.raises(FrozenInstanceError):
            result.status = "completed"
    finally:
        executor.release.set()
        node.stop()


def test_stopped_node_rejects_new_work_without_changing_state() -> None:
    node = Node(
        "node-1",
        "Node 1",
        NodeRole.APPLICATION_SERVER,
        _devices(),
        ApplicationServerExecutor(),
        workers=1,
    )
    node.stop()
    before_rejection = node.snapshot()
    rejected_work = _work(1, cpu=CpuRequirement(1))

    with pytest.raises(RuntimeError, match="stopped node"):
        node.put(rejected_work)

    after_rejection = node.snapshot()
    assert after_rejection == before_rejection
    assert after_rejection.hardware.queued_works == 0
    assert after_rejection.hardware.running_works == 0
    assert not node.is_worked(rejected_work)
    assert not node.is_failed(rejected_work)


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
