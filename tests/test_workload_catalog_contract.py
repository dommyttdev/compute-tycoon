from __future__ import annotations

import json

import pytest

from hardware_sim import (
    CpuRequirement,
    GpuRequirement,
    ResourceRequirements,
    WorkInfo,
)
from hardware_sim.workloads import ApplicationWorkInfo, load_workload_catalog


def test_application_profile_creates_an_immutable_explicit_phase_plan(
    tmp_path,
) -> None:
    path = tmp_path / "workloads.json"
    path.write_text(
        json.dumps(
            {
                "profiles": [],
                "application_profiles": [
                    {
                        "kind": "ai-training",
                        "application": {
                            "pre": {
                                "cpu": {
                                    "required_clocks": [10, 10],
                                    "clock_usage_hz": [5, 5],
                                }
                            },
                            "delegations": [
                                {
                                    "role": "gpu_worker",
                                    "requirements": {
                                        "gpu": {
                                            "compute": [20, 20],
                                            "memory": [8, 8],
                                        }
                                    },
                                }
                            ],
                            "post": {
                                "network": {
                                    "ingress": [0, 0],
                                    "egress": [4, 4],
                                    "connections": [1, 1],
                                }
                            },
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    plan = load_workload_catalog(path).create_application_work(7, "ai-training")

    assert plan.kind == "ai-training"
    assert isinstance(plan.pre, ResourceRequirements)
    assert plan.pre.cpu.required_clocks == 10
    assert plan.pre.optional("gpu", GpuRequirement) is None
    assert len(plan.delegations) == 1

    delegation = plan.delegations[0]
    assert delegation.role == "gpu_worker"
    assert delegation.node_id is None
    assert isinstance(delegation.requirements, ResourceRequirements)
    assert delegation.requirements.gpu.compute == 20
    assert delegation.requirements.optional("cpu", CpuRequirement) is None

    assert isinstance(plan.post, ResourceRequirements)
    assert plan.post.network.egress == 4
    assert plan.post.optional("gpu", GpuRequirement) is None
    with pytest.raises(AttributeError):
        plan.kind = "changed"


def test_present_empty_application_phases_are_rejected_at_load_time(
    tmp_path,
) -> None:
    for phase in ("pre", "post"):
        application = {
            "delegations": [
                {
                    "role": "gpu_worker",
                    "requirements": {
                        "gpu": {
                            "compute": [1, 1],
                            "memory": [1, 1],
                        }
                    },
                }
            ],
            phase: {},
        }
        path = tmp_path / f"empty-{phase}.json"
        path.write_text(
            json.dumps(
                {
                    "profiles": [],
                    "application_profiles": [
                        {
                            "kind": f"empty-{phase}",
                            "application": application,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(ValueError) as error:
            load_workload_catalog(path)

        message = str(error.value).lower()
        assert phase in message
        assert "non-empty" in message


def test_packaged_catalog_keeps_legacy_and_playable_creation_models_separate() -> None:
    expected_roles = {
        "ai-training": "gpu_worker",
        "video-encoding": "gpu_worker",
        "database-query": "database_server",
        "backup": "storage_server",
        "web-request-with-db": "database_server",
    }
    catalog = load_workload_catalog()

    legacy = catalog.create_work(1, "ai-training")
    assert isinstance(legacy, WorkInfo)
    assert legacy.kind == "ai-training"
    assert not isinstance(legacy, ApplicationWorkInfo)

    for work_id, (kind, expected_role) in enumerate(
        expected_roles.items(),
        start=2,
    ):
        plan = catalog.create_application_work(work_id, kind)

        assert isinstance(plan, ApplicationWorkInfo), kind
        assert plan.pre is not None, kind
        assert plan.post is not None, kind
        assert len(plan.delegations) == 1, kind
        delegation = plan.delegations[0]
        assert delegation.role == expected_role, kind
        assert delegation.node_id is None, kind
        if kind == "ai-training":
            assert isinstance(
                delegation.requirements.require("gpu", GpuRequirement),
                GpuRequirement,
            )
