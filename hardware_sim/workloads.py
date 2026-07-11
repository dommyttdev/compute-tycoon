import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from random import choice, randint
from typing import Protocol

from hardware_sim.config_paths import workloads_config_resource
from hardware_sim.work import (
    CpuRequirement,
    GpuRequirement,
    InfrastructureWorkInfo,
    InfrastructureWorkStep,
    MemoryRequirement,
    NetworkRequirement,
    ResourceRequirements,
    StorageRequirement,
    WorkInfo,
)

IntRange = tuple[int, int]
ProfileConfig = dict[str, object]
RANGE_VALUE_COUNT = 2


class RequirementProfile(Protocol):
    key: str

    def sample(
        self,
        random_int: Callable[[int, int], int] = randint,
    ) -> object: ...


@dataclass(frozen=True)
class CpuRequirementProfile:
    required_clocks: IntRange
    clock_usage_hz: IntRange
    key: str = "cpu"

    def sample(self, random_int: Callable[[int, int], int] = randint):
        return CpuRequirement(
            required_clocks=random_int(*self.required_clocks),
            clock_usage_hz=random_int(*self.clock_usage_hz),
        )


@dataclass(frozen=True)
class MemoryRequirementProfile:
    capacity: IntRange
    key: str = "memory"

    def sample(self, random_int: Callable[[int, int], int] = randint):
        return MemoryRequirement(
            capacity=random_int(*self.capacity),
        )


@dataclass(frozen=True)
class StorageRequirementProfile:
    read: IntRange
    write: IntRange
    key: str = "storage"

    def sample(self, random_int: Callable[[int, int], int] = randint):
        return StorageRequirement(
            read=random_int(*self.read),
            write=random_int(*self.write),
        )


@dataclass(frozen=True)
class GpuRequirementProfile:
    compute: IntRange
    memory: IntRange
    key: str = "gpu"

    def sample(self, random_int: Callable[[int, int], int] = randint):
        return GpuRequirement(
            compute=random_int(*self.compute),
            memory=random_int(*self.memory),
        )


@dataclass(frozen=True)
class NetworkRequirementProfile:
    ingress: IntRange
    egress: IntRange
    connections: IntRange
    key: str = "network"

    def sample(self, random_int: Callable[[int, int], int] = randint):
        return NetworkRequirement(
            ingress=random_int(*self.ingress),
            egress=random_int(*self.egress),
            connections=random_int(*self.connections),
        )


@dataclass(frozen=True)
class WorkloadProfile:
    kind: str
    requirements: tuple[RequirementProfile, ...]

    def create_work(
        self,
        work_id: int,
        random_int: Callable[[int, int], int] = randint,
    ):
        requirements = {
            profile.key: profile.sample(random_int) for profile in self.requirements
        }
        return WorkInfo(
            id=work_id,
            kind=self.kind,
            requirements=ResourceRequirements(**requirements),
        )


@dataclass(frozen=True)
class InfrastructureWorkStepProfile:
    node_id: str
    requirements: tuple[RequirementProfile, ...]

    def create_work(
        self,
        work_id: int,
        kind: str,
        step_index: int,
        random_int: Callable[[int, int], int] = randint,
    ):
        requirements = {
            profile.key: profile.sample(random_int) for profile in self.requirements
        }
        return InfrastructureWorkStep(
            node_id=self.node_id,
            work=WorkInfo(
                id=(work_id * 1000) + step_index,
                kind=f"{kind}:{self.node_id}",
                requirements=ResourceRequirements(**requirements),
            ),
        )


@dataclass(frozen=True)
class InfrastructureWorkloadProfile:
    kind: str
    steps: tuple[InfrastructureWorkStepProfile, ...]

    def create_work(
        self,
        work_id: int,
        random_int: Callable[[int, int], int] = randint,
    ):
        return InfrastructureWorkInfo(
            id=work_id,
            kind=self.kind,
            steps=tuple(
                step.create_work(
                    work_id=work_id,
                    kind=self.kind,
                    step_index=index,
                    random_int=random_int,
                )
                for index, step in enumerate(self.steps, start=1)
            ),
        )


class WorkloadCatalog:
    def __init__(
        self,
        profiles: list[WorkloadProfile | InfrastructureWorkloadProfile],
        choose: Callable[
            [list[WorkloadProfile | InfrastructureWorkloadProfile]],
            WorkloadProfile | InfrastructureWorkloadProfile,
        ] = choice,
    ):
        if not profiles:
            raise ValueError("profiles must not be empty")

        self._profiles = profiles
        self._choose = choose

    def create_work(self, work_id: int, kind: str | None = None):
        if kind is None:
            return self._choose(self._profiles).create_work(work_id)

        for profile in self._profiles:
            if profile.kind == kind:
                return profile.create_work(work_id)

        raise KeyError(f"Unknown workload profile: {kind}")


def load_workload_catalog(path: str | Path | None = None):
    if path is None:
        with workloads_config_resource().open() as file:
            config = json.load(file)
    else:
        with Path(path).open() as file:
            config = json.load(file)

    return WorkloadCatalog(
        profiles=(
            [
                _build_workload_profile(profile_config)
                for profile_config in config.get("profiles", [])
            ]
            + [
                _build_infrastructure_workload_profile(profile_config)
                for profile_config in config.get(
                    "infrastructure_profiles",
                    [],
                )
            ]
        ),
    )


def _build_workload_profile(config: ProfileConfig):
    return WorkloadProfile(
        kind=str(config["kind"]),
        requirements=tuple(
            _build_requirement_profile(key, requirement_config)
            for key, requirement_config in config["requirements"].items()
        ),
    )


def _build_infrastructure_workload_profile(config: ProfileConfig):
    return InfrastructureWorkloadProfile(
        kind=str(config["kind"]),
        steps=tuple(
            _build_infrastructure_work_step_profile(step_config)
            for step_config in config["steps"]
        ),
    )


def _build_infrastructure_work_step_profile(config: ProfileConfig):
    return InfrastructureWorkStepProfile(
        node_id=str(config["node"]),
        requirements=tuple(
            _build_requirement_profile(key, requirement_config)
            for key, requirement_config in config["requirements"].items()
        ),
    )


def _build_requirement_profile(key: str, config: ProfileConfig):
    if key == "cpu":
        return CpuRequirementProfile(
            required_clocks=_to_range(config["required_clocks"]),
            clock_usage_hz=_to_range(config["clock_usage_hz"]),
        )
    if key == "memory":
        return MemoryRequirementProfile(
            capacity=_to_range(config["capacity"]),
        )
    if key == "storage":
        return StorageRequirementProfile(
            read=_to_range(config["read"]),
            write=_to_range(config["write"]),
        )
    if key == "gpu":
        return GpuRequirementProfile(
            compute=_to_range(config["compute"]),
            memory=_to_range(config["memory"]),
        )
    if key == "network":
        return NetworkRequirementProfile(
            ingress=_to_range(config.get("ingress", [0, 0])),
            egress=_to_range(config.get("egress", [0, 0])),
            connections=_to_range(config.get("connections", [1, 1])),
        )

    raise ValueError(f"Unknown requirement profile: {key}")


def _to_range(value: object):
    if not isinstance(value, list) or len(value) != RANGE_VALUE_COUNT:
        raise ValueError(
            f"Expected range list with {RANGE_VALUE_COUNT} values, got {value!r}"
        )

    return (int(value[0]), int(value[1]))


DEFAULT_WORKLOADS = load_workload_catalog()
