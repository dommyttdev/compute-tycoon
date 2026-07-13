from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

ALLOWED_DELEGATION_ROLES = frozenset(
    {"database_server", "gpu_worker", "storage_server"}
)


def validate_delegation_role(role: str):
    if role not in ALLOWED_DELEGATION_ROLES:
        raise ValueError(f"Unsupported delegation role: {role}")


@dataclass(frozen=True)
class CpuRequirement:
    required_clocks: int
    clock_usage_hz: int | None = None

    def __post_init__(self):
        if self.required_clocks < 1:
            raise ValueError("required_clocks must be greater than 0")
        if self.clock_usage_hz is not None and self.clock_usage_hz < 1:
            raise ValueError("clock_usage_hz must be greater than 0")


@dataclass(frozen=True)
class MemoryRequirement:
    capacity: int

    def __post_init__(self):
        if self.capacity < 1:
            raise ValueError("memory capacity must be greater than 0")


@dataclass(frozen=True)
class StorageRequirement:
    read: int
    write: int

    def __post_init__(self):
        if self.read < 0:
            raise ValueError("storage read must be 0 or greater")
        if self.write < 0:
            raise ValueError("storage write must be 0 or greater")


@dataclass(frozen=True)
class GpuRequirement:
    compute: int
    memory: int

    def __post_init__(self):
        if self.compute < 1:
            raise ValueError("gpu compute must be greater than 0")
        if self.memory < 1:
            raise ValueError("gpu memory must be greater than 0")


@dataclass(frozen=True)
class NetworkRequirement:
    ingress: int = 0
    egress: int = 0
    connections: int = 1

    def __post_init__(self):
        if self.ingress < 0:
            raise ValueError("network ingress must be 0 or greater")
        if self.egress < 0:
            raise ValueError("network egress must be 0 or greater")
        if self.connections < 1:
            raise ValueError("network connections must be greater than 0")


@dataclass(frozen=True, init=False)
class ResourceRequirements:
    _requirements: MappingProxyType

    def __init__(self, **requirements: object):
        if not requirements:
            raise ValueError("requirements must not be empty")

        object.__setattr__(
            self,
            "_requirements",
            MappingProxyType(dict(requirements)),
        )

    def require(self, key: str, expected_type: type[Any]):
        try:
            requirement = self._requirements[key]
        except KeyError as error:
            raise KeyError(f"Missing resource requirement: {key}") from error

        if not isinstance(requirement, expected_type):
            raise TypeError(
                f"Resource requirement '{key}' must be "
                f"{expected_type.__name__}, got {type(requirement).__name__}"
            )

        return requirement

    def optional(self, key: str, expected_type: type[Any]):
        requirement = self._requirements.get(key)
        if requirement is None:
            return None

        if not isinstance(requirement, expected_type):
            raise TypeError(
                f"Resource requirement '{key}' must be "
                f"{expected_type.__name__}, got {type(requirement).__name__}"
            )

        return requirement

    def items(self):
        return self._requirements.items()

    @property
    def cpu(self):
        return self.require("cpu", CpuRequirement)

    @property
    def memory(self):
        return self.require("memory", MemoryRequirement)

    @property
    def storage(self):
        return self.require("storage", StorageRequirement)

    @property
    def gpu(self):
        return self.require("gpu", GpuRequirement)

    @property
    def network(self):
        return self.require("network", NetworkRequirement)


@dataclass(frozen=True)
class WorkInfo:
    id: int
    requirements: ResourceRequirements
    kind: str = "generic"

    def __hash__(self):
        return hash(self.id)

    @property
    def cpu(self):
        return self.requirements.cpu

    @property
    def memory(self):
        return self.requirements.memory

    @property
    def storage(self):
        return self.requirements.storage

    @property
    def gpu(self):
        return self.requirements.gpu

    @property
    def network(self):
        return self.requirements.network


@dataclass(frozen=True)
class InfrastructureWorkStep:
    node_id: str
    work: WorkInfo


@dataclass(frozen=True)
class InfrastructureWorkInfo:
    id: int
    kind: str
    steps: tuple[InfrastructureWorkStep, ...]

    def __post_init__(self):
        if not self.steps:
            raise ValueError("steps must not be empty")


@dataclass(frozen=True)
class ApplicationWorkDelegation:
    role: str
    requirements: ResourceRequirements
    node_id: str | None = None

    def __post_init__(self):
        validate_delegation_role(self.role)


@dataclass(frozen=True)
class ApplicationWorkInfo:
    id: int
    kind: str
    pre: ResourceRequirements | None
    delegations: tuple[ApplicationWorkDelegation, ...]
    post: ResourceRequirements | None

    def __hash__(self):
        return hash(self.id)


@dataclass(frozen=True)
class FailureReason:
    code: str
    message: str


@dataclass(frozen=True)
class StepResult:
    work_id: int | None
    role: str
    node_id: str | None
    status: str
    phase: str
    route: tuple[str, ...] = ()
    children: tuple["StepResult", ...] = ()
    failure: FailureReason | None = None


@dataclass(frozen=True)
class NodeWorkResult:
    status: str
    value: object | None = None
    failure: FailureReason | None = None
    children: tuple[StepResult, ...] = ()


@dataclass(frozen=True)
class JobResult:
    id: int
    status: str
    failure: FailureReason | None
    root: StepResult


@dataclass(frozen=True)
class WorkloadResult:
    kind: str
    status: str
    failure: FailureReason | None
    jobs: tuple[JobResult, ...]
