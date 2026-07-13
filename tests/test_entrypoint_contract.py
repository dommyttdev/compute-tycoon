from __future__ import annotations

import pytest

import hardware
import hardware_sim
import main as application


def test_compatibility_module_reexports_the_public_hardware_api() -> None:
    assert hardware.__all__ == hardware_sim.__all__

    for name in hardware_sim.__all__:
        assert getattr(hardware, name) is getattr(hardware_sim, name)


def test_default_runtime_factory_creates_a_runnable_node() -> None:
    node = application.create_runtime_module(application.DEFAULT_CODE_RUNTIME_CONFIG)

    try:
        assert isinstance(node, hardware_sim.Node)
        assert node.id == application.DEFAULT_APPLICATION_SERVER_ASSEMBLY.id
    finally:
        node.stop()


class _ModuleProbe:
    def __init__(self, failure: str | None = None) -> None:
        self.calls: list[str] = []
        self.failure = failure

    def put(self, work: object) -> None:
        self.calls.append("put")

    def wait_all(self) -> None:
        self.calls.append("wait_all")
        if self.failure == "wait_all":
            raise RuntimeError("wait_all failed")

    def stop(self) -> None:
        self.calls.append("stop")
        if self.failure == "stop":
            raise RuntimeError("stop failed")


class _MonitorProbe:
    def __init__(
        self, module: object, interval: float, failure: str | None = None
    ) -> None:
        self.module = module
        self.interval = interval
        self.calls: list[str] = []
        self.failure = failure

    def start(self) -> None:
        self.calls.append("start")
        if self.failure == "start":
            raise RuntimeError("monitor start failed")

    def stop(self) -> None:
        self.calls.append("stop")
        if self.failure == "stop":
            raise RuntimeError("monitor stop failed")


def _install_monitor(monkeypatch, failure: str | None = None) -> list[_MonitorProbe]:
    monitors: list[_MonitorProbe] = []

    def create_monitor(module: object, interval: float) -> _MonitorProbe:
        if failure == "constructor":
            raise RuntimeError("monitor construction failed")
        monitor = _MonitorProbe(module, interval, failure)
        monitors.append(monitor)
        return monitor

    monkeypatch.setattr(application, "HardwareMonitor", create_monitor)
    monkeypatch.setattr(application, "sleep", lambda interval: None)
    monkeypatch.setattr(
        application.DEFAULT_WORKLOADS,
        "create_work",
        lambda *args, **kwargs: object(),
    )
    return monitors


def test_main_stops_monitor_and_module_after_normal_completion(monkeypatch) -> None:
    module = _ModuleProbe()
    monitors = _install_monitor(monkeypatch)

    application.main(max_jobs=0, module=module)

    assert monitors[0].calls == ["start", "stop"]
    assert module.calls == ["wait_all", "stop"]


def test_main_stops_module_when_monitor_start_fails(monkeypatch) -> None:
    module = _ModuleProbe()
    monitors = _install_monitor(monkeypatch, failure="start")

    try:
        application.main(max_jobs=0, module=module)
    except RuntimeError as error:
        assert str(error) == "monitor start failed"
    else:
        raise AssertionError("monitor start error was not propagated")

    assert monitors[0].calls == ["start"]
    assert module.calls == ["stop"]


def test_main_stops_module_when_monitor_construction_fails(monkeypatch) -> None:
    module = _ModuleProbe()
    monitors = _install_monitor(monkeypatch, failure="constructor")

    try:
        application.main(max_jobs=0, module=module)
    except RuntimeError as error:
        assert str(error) == "monitor construction failed"
    else:
        raise AssertionError("monitor construction error was not propagated")

    assert monitors == []
    assert module.calls == ["stop"]


def test_main_stops_monitor_and_module_when_workload_creation_fails(
    monkeypatch,
) -> None:
    module = _ModuleProbe()
    monitors = _install_monitor(monkeypatch)

    def fail_to_create_work(work_id: int, kind: str | None = None) -> object:
        raise RuntimeError("workload failed")

    monkeypatch.setattr(
        application.DEFAULT_WORKLOADS, "create_work", fail_to_create_work
    )

    try:
        application.main(max_jobs=1, module=module)
    except RuntimeError as error:
        assert str(error) == "workload failed"
    else:
        raise AssertionError("workload creation error was not propagated")

    assert monitors[0].calls == ["start", "stop"]
    assert module.calls == ["wait_all", "stop"]


def test_main_stops_monitor_and_module_when_wait_all_fails(monkeypatch) -> None:
    module = _ModuleProbe(failure="wait_all")
    monitors = _install_monitor(monkeypatch)

    try:
        application.main(max_jobs=0, module=module)
    except RuntimeError as error:
        assert str(error) == "wait_all failed"
    else:
        raise AssertionError("wait_all error was not propagated")

    assert monitors[0].calls == ["start", "stop"]
    assert module.calls == ["wait_all", "stop"]


def test_main_stops_module_when_monitor_stop_fails(monkeypatch) -> None:
    module = _ModuleProbe()
    monitors = _install_monitor(monkeypatch, failure="stop")

    try:
        application.main(max_jobs=0, module=module)
    except RuntimeError as error:
        assert str(error) == "monitor stop failed"
    else:
        raise AssertionError("monitor stop error was not propagated")

    assert monitors[0].calls == ["start", "stop"]
    assert module.calls == ["wait_all", "stop"]


def test_cli_entrypoint_creates_game_and_stops_it_on_exit(monkeypatch) -> None:
    games: list[object] = []

    class GameProbe:
        def __init__(self) -> None:
            self.stopped = False
            games.append(self)

        def stop_all(self) -> None:
            self.stopped = True

    def exit_immediately(shell: hardware_sim.TycoonShell) -> None:
        shell.do_exit("")

    monkeypatch.setattr("hardware_sim.shell.ComputeTycoonGame", GameProbe)
    monkeypatch.setattr(hardware_sim.TycoonShell, "cmdloop", exit_immediately)

    application.run_cli()

    assert len(games) == 1
    assert games[0].stopped is True


def test_cli_entrypoint_stops_game_when_command_loop_fails(monkeypatch) -> None:
    games: list[object] = []

    class GameProbe:
        def __init__(self) -> None:
            self.stopped = False
            games.append(self)

        def stop_all(self) -> None:
            self.stopped = True

    def fail_command_loop(shell: hardware_sim.TycoonShell) -> None:
        raise RuntimeError("command loop failed")

    monkeypatch.setattr("hardware_sim.shell.ComputeTycoonGame", GameProbe)
    monkeypatch.setattr(hardware_sim.TycoonShell, "cmdloop", fail_command_loop)

    try:
        application.run_cli()
    except RuntimeError as error:
        assert str(error) == "command loop failed"
    else:
        raise AssertionError("command loop error was not propagated")

    assert len(games) == 1
    assert games[0].stopped is True


@pytest.mark.parametrize(
    ("argv", "environment", "system", "expected"),
    (
        pytest.param(
            ("--lang", "ja-JP"),
            {"COMPUTE_TYCOON_LANG": "en-US"},
            "en-US",
            "ja",
            id="explicit-overrides-automatic-sources",
        ),
        pytest.param(
            (),
            {"COMPUTE_TYCOON_LANG": "ja_JP.UTF-8"},
            "en-US",
            "ja",
            id="environment-used-without-argument",
        ),
        pytest.param(
            (),
            {},
            "ja-JP",
            "ja",
            id="system-used-without-higher-sources",
        ),
        pytest.param(
            ("--lang", "fr-FR"),
            {"COMPUTE_TYCOON_LANG": "ja"},
            "ja",
            None,
            id="unsupported-explicit-rejected",
        ),
    ),
)
def test_cli_locale_resolution_parses_argument_and_delegates_precedence(
    argv: tuple[str, ...],
    environment: dict[str, str],
    system: str,
    expected: str | None,
) -> None:
    if expected is None:
        with pytest.raises(ValueError) as error:
            application.resolve_cli_locale(argv, environment, system)

        assert "en" in str(error.value)
        assert "ja" in str(error.value)
    else:
        assert application.resolve_cli_locale(argv, environment, system) == expected
