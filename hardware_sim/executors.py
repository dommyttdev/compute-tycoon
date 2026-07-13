from typing import Protocol

from hardware_sim.work import (
    ApplicationWorkInfo,
    CpuRequirement,
    FailureReason,
    GpuRequirement,
    MemoryRequirement,
    NetworkRequirement,
    NodeWorkResult,
    StorageRequirement,
    WorkInfo,
)


class RoleExecutor(Protocol):
    def execute(self, work_info: WorkInfo, node: object) -> None: ...


class UnassignedExecutor:
    def execute(self, work_info: WorkInfo, node: object):
        raise RuntimeError("Node role is unassigned")


class ApplicationServerExecutor:
    def execute(self, work_info: WorkInfo, node: object):
        if isinstance(work_info, ApplicationWorkInfo):
            return self._execute_application_work(work_info, node)

        self._execute_phase(work_info, node)

    def _execute_application_work(self, work_info: ApplicationWorkInfo, node: object):
        _log_execute(work_info, node)
        if work_info.pre is not None:
            self._execute_phase(
                WorkInfo(
                    work_info.id * 1000 + 1, work_info.pre, f"{work_info.kind}:pre"
                ),
                node,
            )
        children = []
        for index, delegation in enumerate(work_info.delegations, start=1):
            child = node.dispatch(work_info, delegation, index)
            children.append(child)
            if child.status != "completed":
                return NodeWorkResult(
                    status="failed",
                    failure=FailureReason(
                        code="delegation_failed",
                        message="Application delegation failed",
                    ),
                    children=tuple(children),
                )
        if work_info.post is not None:
            try:
                self._execute_phase(
                    WorkInfo(
                        work_info.id * 1000 + 999,
                        work_info.post,
                        f"{work_info.kind}:post",
                    ),
                    node,
                )
            except Exception:
                return NodeWorkResult(
                    status="failed",
                    failure=FailureReason(
                        code="node_execution_failed",
                        message="Node execution failed",
                    ),
                    children=tuple(children),
                )
        _log_executed(work_info, node)
        return tuple(children)

    def _execute_phase(self, work_info: WorkInfo, node: object):
        _log_execute(work_info, node)
        _receive_network_if_available(work_info, node)
        _allocate_memory_if_required(work_info, node)
        try:
            _read_storage_if_required(work_info, node)
            _process_cpu_if_required(work_info, node)
            _write_storage_if_required(work_info, node)
            _send_network_if_available(work_info, node)
        finally:
            _release_memory_if_required(work_info, node)
        _log_executed(work_info, node)


class DatabaseServerExecutor:
    def execute(self, work_info: WorkInfo, node: object):
        _log_execute(work_info, node)
        _receive_network_if_available(work_info, node)
        _allocate_memory_if_required(work_info, node)
        try:
            _read_storage_if_required(work_info, node)
            _process_cpu_if_required(work_info, node)
            _write_storage_if_required(work_info, node)
            _send_network_if_available(work_info, node)
        finally:
            _release_memory_if_required(work_info, node)
        _log_executed(work_info, node)


class StorageServerExecutor:
    def execute(self, work_info: WorkInfo, node: object):
        _log_execute(work_info, node)
        _receive_network_if_available(work_info, node)
        _read_storage_if_required(work_info, node)
        _write_storage_if_required(work_info, node)
        _send_network_if_available(work_info, node)
        _log_executed(work_info, node)


class NetworkSwitchExecutor:
    def execute(self, work_info: WorkInfo, node: object):
        _log_execute(work_info, node)
        _receive_network_if_available(work_info, node)
        _send_network_if_available(work_info, node)
        _log_executed(work_info, node)


class RouterExecutor:
    def execute(self, work_info: WorkInfo, node: object):
        _log_execute(work_info, node)
        _receive_network_if_available(work_info, node)
        _process_cpu_if_required(work_info, node)
        _send_network_if_available(work_info, node)
        _log_executed(work_info, node)


class GpuWorkerExecutor:
    def execute(self, work_info: WorkInfo, node: object):
        _log_execute(work_info, node)
        _allocate_memory_if_required(work_info, node)
        try:
            _read_storage_if_required(work_info, node)
            _process_gpu_if_required(work_info, node)
            _process_cpu_if_required(work_info, node)
            _write_storage_if_required(work_info, node)
        finally:
            _release_memory_if_required(work_info, node)
        _log_executed(work_info, node)


def executor_for_role(role):
    from hardware_sim.node import NodeRole

    executors = {
        NodeRole.UNASSIGNED: UnassignedExecutor(),
        NodeRole.APPLICATION_SERVER: ApplicationServerExecutor(),
        NodeRole.DATABASE_SERVER: DatabaseServerExecutor(),
        NodeRole.STORAGE_SERVER: StorageServerExecutor(),
        NodeRole.NETWORK_SWITCH: NetworkSwitchExecutor(),
        NodeRole.ROUTER: RouterExecutor(),
        NodeRole.GPU_WORKER: GpuWorkerExecutor(),
    }
    return executors[role]


def _log_execute(work_info: WorkInfo, node: object):
    _log(
        node,
        f"Executing: node={node.id}, role={node.role.value}, "
        f"id={work_info.id}, kind={work_info.kind}",
    )


def _log_executed(work_info: WorkInfo, node: object):
    _log(
        node,
        f"Executed: node={node.id}, id={work_info.id}, kind={work_info.kind}",
    )


def _log(node: object, message: str):
    if hasattr(node, "log"):
        node.log(message)
        return
    print(message)


def _allocate_memory_if_required(work_info: WorkInfo, node: object):
    if _has_requirement(work_info, "memory", MemoryRequirement):
        node.memory.allocate(work_info)


def _release_memory_if_required(work_info: WorkInfo, node: object):
    if _has_requirement(work_info, "memory", MemoryRequirement):
        node.memory.release(work_info)


def _read_storage_if_required(work_info: WorkInfo, node: object):
    requirement = work_info.requirements.optional("storage", StorageRequirement)
    if requirement is not None and requirement.read > 0:
        node.storage.read(work_info)


def _write_storage_if_required(work_info: WorkInfo, node: object):
    requirement = work_info.requirements.optional("storage", StorageRequirement)
    if requirement is not None and requirement.write > 0:
        node.storage.write(work_info)


def _process_cpu_if_required(work_info: WorkInfo, node: object):
    if _has_requirement(work_info, "cpu", CpuRequirement):
        node.cpu.process(work_info)


def _process_gpu_if_required(work_info: WorkInfo, node: object):
    if _has_requirement(work_info, "gpu", GpuRequirement):
        node.devices.primary_gpu.process(work_info)


def _receive_network_if_available(work_info: WorkInfo, node: object):
    requirement = work_info.requirements.optional("network", NetworkRequirement)
    if requirement is not None and node.network_interfaces:
        node.devices.primary_network_interface.receive(work_info)


def _send_network_if_available(work_info: WorkInfo, node: object):
    requirement = work_info.requirements.optional("network", NetworkRequirement)
    if requirement is not None and node.network_interfaces:
        node.devices.primary_network_interface.send(work_info)


def _has_requirement(work_info: WorkInfo, key: str, expected_type: type):
    return work_info.requirements.optional(key, expected_type) is not None
