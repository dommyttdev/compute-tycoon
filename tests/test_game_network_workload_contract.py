from __future__ import annotations

from copy import deepcopy
from threading import Thread
from time import monotonic, sleep

import pytest

from hardware_sim import (
    ApplicationWorkDelegation,
    BuildRequest,
    ComputeTycoonGame,
    CpuRequirement,
    NodeRole,
    ResourceRequirements,
    WorkInfo,
)
from hardware_sim.workloads import (
    ApplicationDelegationProfile,
    ApplicationWorkloadProfile,
    CpuRequirementProfile,
    GpuRequirementProfile,
    InfrastructureWorkloadProfile,
    InfrastructureWorkStepProfile,
    MemoryRequirementProfile,
    StorageRequirementProfile,
    WorkloadCatalog,
)

CABLE_ID = "cable.cat6.patch"


@pytest.fixture
def game() -> ComputeTycoonGame:
    value = ComputeTycoonGame(save_path=None, load_save=False)
    try:
        yield value
    finally:
        value.stop_all()


def _place_server(
    game: ComputeTycoonGame,
    node_id: str,
    role: NodeRole = NodeRole.APPLICATION_SERVER,
) -> None:
    game.buy_server(role)
    game.add_node(node_id, role)


def _build_gpu_worker(game: ComputeTycoonGame, node_id: str) -> None:
    parts = (
        ("motherboard", "mb.server.sp5.ddr5"),
        ("processor", "cpu.database.16core"),
        ("memory", "memory.database"),
        ("storage", "storage.database.nvme"),
        ("gpu", "gpu.training"),
    )
    for kind, part_id in parts:
        game.buy_part(kind, part_id)
    game.build_node(
        BuildRequest(
            node_id=node_id,
            role=NodeRole.GPU_WORKER,
            motherboard="mb.server.sp5.ddr5",
            processors=("cpu.database.16core",),
            memory_modules=("memory.database",),
            storage_devices=("storage.database.nvme",),
            gpus=("gpu.training",),
        )
    )


def _two_node_workloads() -> WorkloadCatalog:
    cpu = (CpuRequirementProfile((1, 1), (1, 1)),)
    return WorkloadCatalog(
        [
            InfrastructureWorkloadProfile(
                kind="two-node",
                steps=(
                    InfrastructureWorkStepProfile("source", cpu),
                    InfrastructureWorkStepProfile("target", cpu),
                ),
            )
        ]
    )


def test_application_workload_without_ingress_returns_structured_failure(
    game: ComputeTycoonGame,
) -> None:
    result = game.run_workload("ai-training")

    assert result.kind == "ai-training"
    assert result.status == "failed"
    assert result.failure.code == "no_ingress"
    assert len(result.jobs) == 1

    job = result.jobs[0]
    assert job.status == "failed"
    assert job.failure.code == "no_ingress"
    assert job.root.node_id is None
    assert job.root.status == "failed"
    assert job.root.failure.code == "no_ingress"


def test_stopped_only_application_server_returns_no_ingress_without_admission(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "app")
    app = game.nodes["app"]
    app.stop()
    before = app.snapshot().hardware
    game.workloads = WorkloadCatalog(
        [
            ApplicationWorkloadProfile(
                kind="stopped-ingress",
                pre=(CpuRequirementProfile((1, 1), (1, 1)),),
                delegations=(),
                post=None,
            )
        ]
    )

    result = game.run_workload("stopped-ingress")

    assert result.status == "failed"
    assert result.failure.code == "no_ingress"
    assert len(result.jobs) == 1
    job = result.jobs[0]
    assert job.status == "failed"
    assert job.failure.code == "no_ingress"
    assert job.root.status == "failed"
    assert job.root.failure.code == "no_ingress"
    assert job.root.node_id is None
    assert job.root.children == ()
    after = app.snapshot().hardware
    assert after.queued_works == before.queued_works == 0
    assert after.running_works == before.running_works == 0
    assert after.completed_works == before.completed_works == 0
    assert after.failed_works == before.failed_works == 0


def test_missing_gpu_candidate_returns_nested_no_eligible_node_failure(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "app")
    game.workloads = WorkloadCatalog(
        [
            ApplicationWorkloadProfile(
                kind="missing-gpu",
                pre=None,
                delegations=(
                    ApplicationDelegationProfile(
                        role="gpu_worker",
                        requirements=(
                            GpuRequirementProfile(
                                compute=(1, 1),
                                memory=(1, 1),
                            ),
                        ),
                    ),
                ),
                post=None,
            )
        ]
    )

    result = game.run_workload("missing-gpu")

    assert result.status == "failed"
    assert result.failure.code == "delegation_failed"
    assert len(result.jobs) == 1
    job = result.jobs[0]
    assert job.status == "failed"
    assert job.failure.code == "delegation_failed"
    assert job.root.status == "failed"
    assert job.root.failure.code == "delegation_failed"
    assert len(job.root.children) == 1
    child = job.root.children[0]
    assert child.status == "failed"
    assert child.failure.code == "no_eligible_node"
    assert child.role == "gpu_worker"
    assert child.node_id is None


def test_application_server_self_delegation_is_rejected_before_enqueue(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "app")

    with pytest.raises(ValueError, match="application_server"):
        ApplicationDelegationProfile(
            role="application_server",
            requirements=(CpuRequirementProfile((1, 1), (1, 1)),),
        )
    with pytest.raises(ValueError, match="application_server"):
        ApplicationWorkDelegation(
            role="application_server",
            requirements=ResourceRequirements(cpu=CpuRequirement(1)),
        )

    app = game.nodes["app"].snapshot().hardware
    assert app.queued_works == 0
    assert app.running_works == 0
    assert app.completed_works == 0
    assert app.failed_works == 0


def test_batch_continues_after_delegation_failure_and_returns_ordered_jobs(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "app")
    game.workloads = WorkloadCatalog(
        [
            ApplicationWorkloadProfile(
                kind="batch-missing-gpu",
                pre=None,
                delegations=(
                    ApplicationDelegationProfile(
                        role="gpu_worker",
                        requirements=(
                            GpuRequirementProfile(
                                compute=(1, 1),
                                memory=(1, 1),
                            ),
                        ),
                    ),
                ),
                post=None,
            )
        ]
    )

    result = game.run_workload("batch-missing-gpu", jobs=2)

    assert result.status == "failed"
    assert result.failure.code == "delegation_failed"
    assert [job.id for job in result.jobs] == [1, 2]
    for job in result.jobs:
        assert job.status == "failed"
        assert job.failure.code == "delegation_failed"
        assert job.root.status == "failed"
        assert job.root.failure.code == "delegation_failed"
        assert len(job.root.children) == 1
        child = job.root.children[0]
        assert child.status == "failed"
        assert child.failure.code == "no_eligible_node"
        assert child.role == "gpu_worker"
        assert child.node_id is None


def test_application_pre_capacity_failure_skips_delegation_and_releases_memory(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "app")
    _build_gpu_worker(game, "gpu")
    game.add_address("app:lan0", "192.0.2.10/24")
    game.add_address("gpu:lan0", "192.0.2.20/24")
    game.buy_cable(CABLE_ID)
    game.connect("app:lan0", "gpu:lan0", CABLE_ID)
    app_memory_capacity = game.nodes["app"].snapshot().hardware.memory.capacity
    game.workloads = WorkloadCatalog(
        [
            ApplicationWorkloadProfile(
                kind="app-pre-capacity-failure",
                pre=(
                    MemoryRequirementProfile(
                        capacity=(app_memory_capacity + 1, app_memory_capacity + 1)
                    ),
                ),
                delegations=(
                    ApplicationDelegationProfile(
                        role="gpu_worker",
                        requirements=(
                            GpuRequirementProfile(
                                compute=(1, 1),
                                memory=(1, 1),
                            ),
                        ),
                    ),
                ),
                post=None,
            )
        ]
    )

    result = game.run_workload("app-pre-capacity-failure")

    assert result.status == "failed"
    assert result.failure.code == "node_execution_failed"
    assert len(result.jobs) == 1
    job = result.jobs[0]
    assert job.status == "failed"
    assert job.failure.code == "node_execution_failed"
    assert job.root.status == "failed"
    assert job.root.failure.code == "node_execution_failed"
    assert job.root.node_id == "app"
    assert job.root.children == ()

    app = game.nodes["app"].snapshot().hardware
    gpu = game.nodes["gpu"].snapshot().hardware
    assert app.memory.used == 0
    assert app.queued_works == 0
    assert app.running_works == 0
    assert app.completed_works == 0
    assert app.failed_works == 1
    assert gpu.queued_works == 0
    assert gpu.running_works == 0
    assert gpu.completed_works == 0
    assert gpu.failed_works == 0


def test_application_parent_remains_running_while_gpu_child_runs(
    game: ComputeTycoonGame,
) -> None:
    game.workloads = WorkloadCatalog(
        [
            ApplicationWorkloadProfile(
                kind="gpu-overlap",
                pre=None,
                delegations=(
                    ApplicationDelegationProfile(
                        role="gpu_worker",
                        requirements=(
                            GpuRequirementProfile(
                                compute=(12_000_000_000_000, 12_000_000_000_000),
                                memory=(8, 8),
                            ),
                        ),
                    ),
                ),
                post=None,
            )
        ]
    )
    _place_server(game, "app")
    _build_gpu_worker(game, "gpu")
    game.add_address("app:lan0", "192.0.2.10/24")
    game.add_address("gpu:lan0", "192.0.2.20/24")
    game.buy_cable(CABLE_ID)
    game.connect("app:lan0", "gpu:lan0", CABLE_ID)

    results = []
    errors: list[BaseException] = []

    def run_workload() -> None:
        try:
            results.append(game.run_workload("gpu-overlap"))
        except BaseException as error:
            errors.append(error)

    thread = Thread(target=run_workload, daemon=True)
    thread.start()
    observed_overlap = False
    deadline = monotonic() + 1
    while monotonic() < deadline:
        app_running = game.nodes["app"].snapshot().hardware.running_works
        gpu_running = game.nodes["gpu"].snapshot().hardware.running_works
        if app_running == 1 and gpu_running == 1:
            observed_overlap = True
            break
        sleep(0.005)

    thread.join(timeout=1)
    assert not thread.is_alive(), "workload execution did not reach a terminal result"
    if errors:
        raise errors[0]
    assert observed_overlap

    result = results[0]
    assert result.status == "completed"
    root = result.jobs[0].root
    assert root.status == "completed"
    assert root.node_id == "app"
    assert len(root.children) == 1
    assert root.children[0].status == "completed"
    assert root.children[0].node_id == "gpu"
    assert root.children[0].role == "gpu_worker"


def test_running_delegated_gpu_rejects_role_change_and_keeps_saved_role(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "app")
    _build_gpu_worker(game, "gpu")
    game.add_address("app:lan0", "192.0.2.10/24")
    game.add_address("gpu:lan0", "192.0.2.20/24")
    game.buy_cable(CABLE_ID)
    game.connect("app:lan0", "gpu:lan0", CABLE_ID)
    game.workloads = WorkloadCatalog(
        [
            ApplicationWorkloadProfile(
                kind="gpu-role-atomicity",
                pre=None,
                delegations=(
                    ApplicationDelegationProfile(
                        role="gpu_worker",
                        requirements=(
                            GpuRequirementProfile(
                                compute=(12_000_000_000_000, 12_000_000_000_000),
                                memory=(1, 1),
                            ),
                        ),
                    ),
                ),
                post=None,
            )
        ]
    )
    saved_gpu_before = deepcopy(
        next(node for node in game.to_save_data()["nodes"] if node["id"] == "gpu")
    )
    version_before = game.state_version
    results = []
    errors: list[BaseException] = []

    def run_workload() -> None:
        try:
            results.append(game.run_workload("gpu-role-atomicity"))
        except BaseException as error:
            errors.append(error)

    thread = Thread(target=run_workload, daemon=True)
    thread.start()
    deadline = monotonic() + 1
    while monotonic() < deadline:
        app_running = game.nodes["app"].snapshot().hardware.running_works
        gpu_running = game.nodes["gpu"].snapshot().hardware.running_works
        if app_running == 1 and gpu_running == 1:
            break
        sleep(0.005)
    else:
        pytest.fail("delegated GPU child did not reach running state")

    with pytest.raises(RuntimeError, match="busy"):
        game.set_node_role("gpu", NodeRole.DATABASE_SERVER)

    thread.join(timeout=2)
    assert not thread.is_alive(), "workload execution did not reach a terminal result"
    if errors:
        raise errors[0]
    result = results[0]
    assert result.status == "completed"
    child = result.jobs[0].root.children[0]
    assert child.status == "completed"
    assert child.role == "gpu_worker"
    assert child.node_id == "gpu"
    assert game.nodes["gpu"].role is NodeRole.GPU_WORKER
    saved_gpu_after = next(
        node for node in game.to_save_data()["nodes"] if node["id"] == "gpu"
    )
    assert saved_gpu_after == saved_gpu_before
    assert saved_gpu_after["role"] == "gpu_worker"
    assert game.state_version == version_before


def test_unpinned_delegation_selects_first_reachable_gpu_by_node_id(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "app")
    _build_gpu_worker(game, "gpu-a")
    _build_gpu_worker(game, "gpu-b")
    game.add_address("app:lan0", "192.0.2.10/24")
    game.add_address("gpu-a:lan0", "192.0.2.20/24")
    game.add_address("gpu-b:lan0", "192.0.2.30/24")
    game.buy_cable(CABLE_ID)
    game.connect("app:lan0", "gpu-b:lan0", CABLE_ID)
    game.workloads = WorkloadCatalog(
        [
            ApplicationWorkloadProfile(
                kind="select-reachable-gpu",
                pre=None,
                delegations=(
                    ApplicationDelegationProfile(
                        role="gpu_worker",
                        requirements=(
                            GpuRequirementProfile(
                                compute=(1, 1),
                                memory=(1, 1),
                            ),
                        ),
                    ),
                ),
                post=None,
            )
        ]
    )

    result = game.run_workload("select-reachable-gpu")

    assert result.status == "completed"
    assert result.failure is None
    root = result.jobs[0].root
    assert root.status == "completed"
    assert len(root.children) == 1
    child = root.children[0]
    assert child.status == "completed"
    assert child.node_id == "gpu-b"
    assert child.role == "gpu_worker"
    assert child.route == ("app", "gpu-b")
    first = game.nodes["gpu-a"].snapshot().hardware
    selected = game.nodes["gpu-b"].snapshot().hardware
    assert first.queued_works == 0
    assert first.running_works == 0
    assert first.completed_works == 0
    assert first.failed_works == 0
    assert selected.queued_works == 0
    assert selected.running_works == 0
    assert selected.completed_works == 1
    assert selected.failed_works == 0


def test_unreachable_gpu_delegation_returns_nested_failure_without_execution(
    game: ComputeTycoonGame,
) -> None:
    game.workloads = WorkloadCatalog(
        [
            ApplicationWorkloadProfile(
                kind="gpu-no-route",
                pre=None,
                delegations=(
                    ApplicationDelegationProfile(
                        role="gpu_worker",
                        requirements=(
                            GpuRequirementProfile(
                                compute=(1, 1),
                                memory=(1, 1),
                            ),
                        ),
                    ),
                ),
                post=None,
            )
        ]
    )
    _place_server(game, "app")
    _build_gpu_worker(game, "gpu")
    game.add_address("app:lan0", "192.0.2.10/24")
    game.add_address("gpu:lan0", "192.0.2.20/24")

    result = game.run_workload("gpu-no-route")

    assert result.status == "failed"
    assert result.failure.code == "delegation_failed"
    assert len(result.jobs) == 1
    job = result.jobs[0]
    assert job.status == "failed"
    assert job.failure.code == "delegation_failed"
    assert job.root.status == "failed"
    assert job.root.failure.code == "delegation_failed"
    assert len(job.root.children) == 1
    child = job.root.children[0]
    assert child.status == "failed"
    assert child.failure.code == "route_unreachable"
    assert child.node_id == "gpu"
    assert child.role == "gpu_worker"

    gpu = game.nodes["gpu"].snapshot().hardware
    assert gpu.queued_works == 0
    assert gpu.running_works == 0
    assert gpu.completed_works == 0
    assert gpu.failed_works == 0


def test_pinned_role_mismatch_does_not_fall_back_to_reachable_gpu(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "app")
    _place_server(game, "wrong", NodeRole.DATABASE_SERVER)
    _place_server(game, "switch", NodeRole.NETWORK_SWITCH)
    _build_gpu_worker(game, "gpu")
    game.add_address("app:lan0", "192.0.2.10/24")
    game.add_address("wrong:lan0", "192.0.2.20/24")
    game.add_address("gpu:lan0", "192.0.2.30/24")
    game.buy_cable(CABLE_ID, quantity=3)
    game.connect("app:lan0", "switch:port1", CABLE_ID)
    game.connect("wrong:lan0", "switch:port2", CABLE_ID)
    game.connect("gpu:lan0", "switch:port3", CABLE_ID)
    game.workloads = WorkloadCatalog(
        [
            ApplicationWorkloadProfile(
                kind="pinned-role-mismatch",
                pre=None,
                delegations=(
                    ApplicationDelegationProfile(
                        role="gpu_worker",
                        node_id="wrong",
                        requirements=(
                            GpuRequirementProfile(
                                compute=(1, 1),
                                memory=(1, 1),
                            ),
                        ),
                    ),
                ),
                post=None,
            )
        ]
    )

    result = game.run_workload("pinned-role-mismatch")

    assert result.status == "failed"
    assert result.failure.code == "delegation_failed"
    job = result.jobs[0]
    assert job.status == "failed"
    assert job.failure.code == "delegation_failed"
    assert job.root.status == "failed"
    assert job.root.failure.code == "delegation_failed"
    assert len(job.root.children) == 1
    child = job.root.children[0]
    assert child.status == "failed"
    assert child.failure.code == "role_mismatch"
    assert child.role == "gpu_worker"
    assert child.node_id == "wrong"

    wrong = game.nodes["wrong"].snapshot().hardware
    gpu = game.nodes["gpu"].snapshot().hardware
    assert wrong.queued_works == 0
    assert wrong.running_works == 0
    assert wrong.completed_works == 0
    assert wrong.failed_works == 0
    assert gpu.queued_works == 0
    assert gpu.running_works == 0
    assert gpu.completed_works == 0
    assert gpu.failed_works == 0


def test_failed_gpu_child_skips_post_and_releases_temporary_resources(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "app")
    _build_gpu_worker(game, "gpu")
    game.add_address("app:lan0", "192.0.2.10/24")
    game.add_address("gpu:lan0", "192.0.2.20/24")
    game.buy_cable(CABLE_ID)
    game.connect("app:lan0", "gpu:lan0", CABLE_ID)
    gpu_memory_capacity = game.nodes["gpu"].snapshot().hardware.gpus[0].memory_capacity
    app_storage_before = game.nodes["app"].snapshot().hardware.storage.used
    game.workloads = WorkloadCatalog(
        [
            ApplicationWorkloadProfile(
                kind="gpu-capacity-failure",
                pre=None,
                delegations=(
                    ApplicationDelegationProfile(
                        role="gpu_worker",
                        requirements=(
                            MemoryRequirementProfile(capacity=(1, 1)),
                            GpuRequirementProfile(
                                compute=(1, 1),
                                memory=(
                                    gpu_memory_capacity + 1,
                                    gpu_memory_capacity + 1,
                                ),
                            ),
                        ),
                    ),
                ),
                post=(StorageRequirementProfile(read=(0, 0), write=(1, 1)),),
            )
        ]
    )

    result = game.run_workload("gpu-capacity-failure")

    assert result.status == "failed"
    assert result.failure.code == "delegation_failed"
    job = result.jobs[0]
    assert job.status == "failed"
    assert job.failure.code == "delegation_failed"
    assert job.root.status == "failed"
    assert job.root.failure.code == "delegation_failed"
    assert len(job.root.children) == 1
    child = job.root.children[0]
    assert child.status == "failed"
    assert child.failure.code == "node_execution_failed"
    assert child.node_id == "gpu"

    app = game.nodes["app"].snapshot().hardware
    gpu = game.nodes["gpu"].snapshot().hardware
    assert app.storage.used == app_storage_before
    assert gpu.memory.used == 0
    assert gpu.gpus[0].memory_used == 0
    assert gpu.gpus[0].active_jobs == 0
    assert gpu.queued_works == 0
    assert gpu.running_works == 0
    assert gpu.completed_works == 0
    assert gpu.failed_works == 1


def test_stopped_reachable_gpu_returns_nested_execution_failure_and_skips_post(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "app")
    _build_gpu_worker(game, "gpu")
    game.add_address("app:lan0", "192.0.2.10/24")
    game.add_address("gpu:lan0", "192.0.2.20/24")
    game.buy_cable(CABLE_ID)
    game.connect("app:lan0", "gpu:lan0", CABLE_ID)
    app_storage_before = game.nodes["app"].snapshot().hardware.storage.used
    game.nodes["gpu"].stop()
    game.workloads = WorkloadCatalog(
        [
            ApplicationWorkloadProfile(
                kind="stopped-gpu",
                pre=None,
                delegations=(
                    ApplicationDelegationProfile(
                        role="gpu_worker",
                        requirements=(
                            GpuRequirementProfile(
                                compute=(1, 1),
                                memory=(1, 1),
                            ),
                        ),
                    ),
                ),
                post=(StorageRequirementProfile(read=(0, 0), write=(1, 1)),),
            )
        ]
    )

    result = game.run_workload("stopped-gpu")

    assert result.status == "failed"
    assert result.failure.code == "delegation_failed"
    job = result.jobs[0]
    assert job.status == "failed"
    assert job.failure.code == "delegation_failed"
    assert job.root.status == "failed"
    assert job.root.failure.code == "delegation_failed"
    assert len(job.root.children) == 1
    child = job.root.children[0]
    assert child.status == "failed"
    assert child.failure.code == "node_execution_failed"
    assert child.role == "gpu_worker"
    assert child.node_id == "gpu"
    assert child.route == ("app", "gpu")

    app = game.nodes["app"].snapshot().hardware
    gpu = game.nodes["gpu"].snapshot().hardware
    assert app.storage.used == app_storage_before
    assert gpu.queued_works == 0
    assert gpu.running_works == 0
    assert gpu.completed_works == 0
    assert gpu.failed_works == 0


def test_application_pre_and_post_consume_configured_resources_around_gpu_child(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "app")
    _build_gpu_worker(game, "gpu")
    game.add_address("app:lan0", "192.0.2.10/24")
    game.add_address("gpu:lan0", "192.0.2.20/24")
    game.buy_cable(CABLE_ID)
    game.connect("app:lan0", "gpu:lan0", CABLE_ID)
    app_storage_before = game.nodes["app"].snapshot().hardware.storage.used
    game.workloads = WorkloadCatalog(
        [
            ApplicationWorkloadProfile(
                kind="app-phases",
                pre=(StorageRequirementProfile(read=(0, 0), write=(2, 2)),),
                delegations=(
                    ApplicationDelegationProfile(
                        role="gpu_worker",
                        requirements=(
                            GpuRequirementProfile(
                                compute=(1, 1),
                                memory=(1, 1),
                            ),
                        ),
                    ),
                ),
                post=(StorageRequirementProfile(read=(0, 0), write=(3, 3)),),
            )
        ]
    )

    result = game.run_workload("app-phases")

    assert result.status == "completed"
    assert result.failure is None
    assert len(result.jobs) == 1
    job = result.jobs[0]
    assert job.status == "completed"
    assert job.failure is None
    assert job.root.status == "completed"
    assert job.root.failure is None
    assert len(job.root.children) == 1
    assert job.root.children[0].status == "completed"
    assert job.root.children[0].node_id == "gpu"
    app_storage_after = game.nodes["app"].snapshot().hardware.storage.used
    assert app_storage_after == app_storage_before + 2 + 3


def test_application_post_failure_preserves_completed_gpu_child_and_releases_resources(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "app")
    _build_gpu_worker(game, "gpu")
    game.add_address("app:lan0", "192.0.2.10/24")
    game.add_address("gpu:lan0", "192.0.2.20/24")
    game.buy_cable(CABLE_ID)
    game.connect("app:lan0", "gpu:lan0", CABLE_ID)
    app_memory_capacity = game.nodes["app"].snapshot().hardware.memory.capacity
    game.workloads = WorkloadCatalog(
        [
            ApplicationWorkloadProfile(
                kind="app-post-capacity-failure",
                pre=None,
                delegations=(
                    ApplicationDelegationProfile(
                        role="gpu_worker",
                        requirements=(
                            MemoryRequirementProfile(capacity=(1, 1)),
                            GpuRequirementProfile(
                                compute=(1, 1),
                                memory=(1, 1),
                            ),
                        ),
                    ),
                ),
                post=(
                    MemoryRequirementProfile(
                        capacity=(app_memory_capacity + 1, app_memory_capacity + 1)
                    ),
                ),
            )
        ]
    )

    result = game.run_workload("app-post-capacity-failure")

    assert result.status == "failed"
    assert result.failure.code == "node_execution_failed"
    job = result.jobs[0]
    assert job.status == "failed"
    assert job.failure.code == "node_execution_failed"
    assert job.root.status == "failed"
    assert job.root.failure.code == "node_execution_failed"
    assert job.root.node_id == "app"
    assert len(job.root.children) == 1
    child = job.root.children[0]
    assert child.status == "completed"
    assert child.failure is None
    assert child.role == "gpu_worker"
    assert child.node_id == "gpu"
    assert child.route == ("app", "gpu")

    app = game.nodes["app"].snapshot().hardware
    gpu = game.nodes["gpu"].snapshot().hardware
    assert app.memory.used == 0
    assert app.queued_works == 0
    assert app.running_works == 0
    assert app.completed_works == 0
    assert app.failed_works == 1
    assert gpu.memory.used == 0
    assert gpu.gpus[0].memory_used == 0
    assert gpu.gpus[0].active_jobs == 0
    assert gpu.queued_works == 0
    assert gpu.running_works == 0
    assert gpu.completed_works == 1
    assert gpu.failed_works == 0


def test_placing_a_purchased_server_consumes_it_only_after_success(
    game: ComputeTycoonGame,
) -> None:
    game.buy_server(NodeRole.APPLICATION_SERVER, quantity=2)
    version_before_placement = game.state_version
    game.add_node("node-1", NodeRole.APPLICATION_SERVER)
    assert game.state_version == version_before_placement + 1
    inventory_before_failure = deepcopy(game.inventory.to_dict())
    version_before_failure = game.state_version

    with pytest.raises(ValueError, match="already exists"):
        game.add_node("node-1", NodeRole.APPLICATION_SERVER)

    assert game.inventory.servers[NodeRole.APPLICATION_SERVER.value] == 1
    assert game.inventory.to_dict() == inventory_before_failure
    assert game.state_version == version_before_failure


def test_connect_consumes_a_cable_and_failed_connect_leaves_state_unchanged(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "left")
    _place_server(game, "right")
    game.buy_cable(CABLE_ID, quantity=2)
    game.connect("left:lan0", "right:lan0", CABLE_ID)
    topology_before_failure = game.topology
    inventory_before_failure = deepcopy(game.inventory.to_dict())
    version_before_failure = game.state_version

    with pytest.raises(ValueError, match="already connected"):
        game.connect("left:lan0", "right:lan0", CABLE_ID)

    assert game.inventory.cables[CABLE_ID] == 1
    assert game.topology is topology_before_failure
    assert game.inventory.to_dict() == inventory_before_failure
    assert game.state_version == version_before_failure


def test_network_mutations_update_topology_inventory_and_version_once(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "left")
    _place_server(game, "right")
    game.buy_cable(CABLE_ID)

    before = game.state_version
    game.connect("left:lan0", "right:lan0")
    assert game.state_version == before + 1
    assert game.inventory.cables[CABLE_ID] == 0

    before = game.state_version
    game.add_address("left:lan0", "192.0.2.10/24")
    assert game.state_version == before + 1

    before = game.state_version
    game.add_route("left", "198.51.100.0/24", interface="lan0")
    assert game.state_version == before + 1

    before = game.state_version
    cable = game.disconnect("left:lan0")
    assert game.state_version == before + 1
    assert cable.cable_id == CABLE_ID
    assert game.inventory.cables[CABLE_ID] == 1


def test_role_and_name_changes_keep_saved_build_request_consistent(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "node-1")

    before = game.state_version
    game.set_node_role("node-1", NodeRole.DATABASE_SERVER)
    assert game.state_version == before + 1

    before = game.state_version
    game.rename_server("node-1", "Primary database")
    assert game.state_version == before + 1

    saved_node = game.to_save_data()["nodes"][0]
    assert saved_node["role"] == NodeRole.DATABASE_SERVER.value
    assert saved_node["name"] == "Primary database"
    assert game.nodes["node-1"].role is NodeRole.DATABASE_SERVER
    assert game.nodes["node-1"].name == "Primary database"


def test_setting_same_game_node_role_is_a_save_state_no_op(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "node-1")
    saved_before = deepcopy(game.to_save_data())
    events_before = game.event_log.entries()
    version_before = game.state_version

    game.set_node_role("node-1", NodeRole.APPLICATION_SERVER)

    assert game.nodes["node-1"].role is NodeRole.APPLICATION_SERVER
    assert game.to_save_data() == saved_before
    assert game.event_log.entries() == events_before
    assert game.state_version == version_before


def test_busy_role_change_failure_leaves_game_state_unchanged(
    game: ComputeTycoonGame,
) -> None:
    _place_server(game, "node-1")
    node = game.nodes["node-1"]
    work = WorkInfo(
        1,
        ResourceRequirements(
            cpu=CpuRequirement(required_clocks=1, clock_usage_hz=1),
        ),
    )

    node.put(work)
    role_before_failure = node.role
    saved_node_before_failure = deepcopy(game.to_save_data()["nodes"][0])
    role_events_before_failure = tuple(
        entry
        for entry in game.event_log.entries("node-1")
        if entry.message.startswith("Node role set")
    )
    version_before_failure = game.state_version
    try:
        with pytest.raises(RuntimeError, match="busy"):
            game.set_node_role("node-1", NodeRole.DATABASE_SERVER)

        assert node.role is role_before_failure
        assert game.to_save_data()["nodes"][0] == saved_node_before_failure
        assert (
            tuple(
                entry
                for entry in game.event_log.entries("node-1")
                if entry.message.startswith("Node role set")
            )
            == role_events_before_failure
        )
        assert game.state_version == version_before_failure
    finally:
        node.wait_all()


def test_game_rejects_legacy_workload_profile_before_enqueuing_node_work(
    game: ComputeTycoonGame,
) -> None:
    game.workloads = _two_node_workloads()
    _place_server(game, "source")
    _place_server(game, "target")
    game.add_address("source:lan0", "192.0.2.10/24")
    game.add_address("target:lan0", "192.0.2.20/24")
    game.buy_cable(CABLE_ID)
    game.connect("source:lan0", "target:lan0")
    counters_before = {
        node_id: (
            node.snapshot().hardware.queued_works,
            node.snapshot().hardware.running_works,
            node.snapshot().hardware.completed_works,
            node.snapshot().hardware.failed_works,
        )
        for node_id, node in game.nodes.items()
    }

    with pytest.raises(KeyError) as error:
        game.run_workload("two-node")

    assert "two-node" in str(error.value)
    counters_after = {
        node_id: (
            node.snapshot().hardware.queued_works,
            node.snapshot().hardware.running_works,
            node.snapshot().hardware.completed_works,
            node.snapshot().hardware.failed_works,
        )
        for node_id, node in game.nodes.items()
    }
    assert counters_after == counters_before
