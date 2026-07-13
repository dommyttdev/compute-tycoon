from hardware_sim import NodeRole
from hardware_sim.monitor import HardwareMonitor
from hardware_sim.shell import ShopShell, TycoonShell
from hardware_sim.snapshots import (
    HardwareSnapshot,
    MemorySnapshot,
    NodeSnapshot,
    ProcessorSnapshot,
    StorageSnapshot,
)


class _GameProbe:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def buy_server(self, role: str, *, quantity: int) -> None:
        self.calls.append(("buy_server", role, quantity))

    def buy_cable(self, cable_id: str, *, quantity: int) -> None:
        self.calls.append(("buy_cable", cable_id, quantity))

    def buy_part(self, kind: str, part_id: str, *, quantity: int) -> None:
        self.calls.append(("buy_part", kind, part_id, quantity))

    def run_workload(self, kind: str, *, jobs: int) -> tuple[str, ...]:
        self.calls.append(("run_workload", kind, jobs))
        return ("scheduled",)

    def add_route(
        self,
        node_id: str,
        destination: str,
        *,
        gateway: str,
        interface: str | None,
    ) -> None:
        self.calls.append(("add_route", node_id, destination, gateway, interface))


def test_shop_buy_parses_quantity_before_calling_public_game_api(capsys) -> None:
    game = _GameProbe()

    ShopShell(game).onecmd("buy cpu cpu-basic 3")

    assert game.calls == [("buy_part", "cpu", "cpu-basic", 3)]
    assert capsys.readouterr().out == "bought cpu cpu-basic x3\n"


def test_run_workload_passes_integer_jobs_to_public_game_api(capsys) -> None:
    game = _GameProbe()

    TycoonShell(game).onecmd("run workload web --jobs 4")

    assert game.calls == [("run_workload", "web", 4)]
    assert capsys.readouterr().out == "scheduled\n"


def test_route_add_maps_optional_interface_to_typed_game_argument(capsys) -> None:
    game = _GameProbe()
    shell = TycoonShell(game)

    shell.onecmd("route add edge 10.0.0.0/24 via 192.0.2.1")
    shell.onecmd("route add core 10.1.0.0/24 via 192.0.2.2 dev eth1")

    assert game.calls == [
        ("add_route", "edge", "10.0.0.0/24", "192.0.2.1", None),
        ("add_route", "core", "10.1.0.0/24", "192.0.2.2", "eth1"),
    ]
    assert capsys.readouterr().out == "route added on edge\nroute added on core\n"


def test_shell_renders_domain_error_without_leaking_it(capsys) -> None:
    class RejectingGame(_GameProbe):
        def run_workload(self, kind: str, *, jobs: int) -> tuple[str, ...]:
            raise ValueError("no eligible worker")

    TycoonShell(RejectingGame()).onecmd("run workload web")

    assert capsys.readouterr().out == "error: no eligible worker\n"


def test_monitor_formats_representative_node_snapshot_without_thread_or_sleep() -> None:
    snapshot = NodeSnapshot(
        id="node-1",
        name="api",
        role=NodeRole.APPLICATION_SERVER,
        hardware=HardwareSnapshot(
            cpu=ProcessorSnapshot(
                name="cpu",
                active_cores=1,
                total_cores=2,
                clock_frequency_hz=2_000_000_000,
                used_clock_hz=1_000_000_000,
                active_required_clocks=250,
                total_processed_clocks=1_000,
            ),
            memory=MemorySnapshot(name="ram", used=2, capacity=8),
            storage=StorageSnapshot(
                name="disk",
                active_transfers=1,
                queue_depth=4,
                used=20,
                capacity=100,
                total_read=30,
                total_written=40,
            ),
            queued_works=1,
            running_works=2,
            completed_works=3,
            failed_works=4,
        ),
    )

    assert HardwareMonitor.format_snapshot(snapshot) == (
        "[Monitor] api (node-1, application_server) | cpu=25% (1/2 cores, "
        "2.00GHz, "
        "active_clock=1,000,000,000Hz/4,000,000,000Hz, work_clocks=250, "
        "processed=1,000) | ram=25% (2/8) | disk IO=25% (1/4), "
        "capacity=20% (20/100) | read=30, written=40 | jobs queued=1, "
        "running=2, done=3, failed=4"
    )
