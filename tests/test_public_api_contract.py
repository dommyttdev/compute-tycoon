import hardware
import hardware_sim


def test_application_workload_types_are_exported_by_both_public_apis() -> None:
    required_names = (
        "ApplicationWorkInfo",
        "ApplicationWorkDelegation",
        "FailureReason",
        "StepResult",
        "JobResult",
        "WorkloadResult",
        "ApplicationWorkloadProfile",
        "ApplicationDelegationProfile",
    )

    for name in required_names:
        assert name in hardware_sim.__all__, name
        assert name in hardware.__all__, name
        assert getattr(hardware_sim, name) is getattr(hardware, name), name
