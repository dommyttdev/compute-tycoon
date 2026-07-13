import argparse
import locale
import os
import sys
from collections.abc import Mapping, Sequence
from itertools import count
from random import uniform
from time import sleep

from hardware import (
    DEFAULT_PARTS_CATALOG,
    DEFAULT_WORKLOADS,
    HardwareModule,
    HardwareMonitor,
    Infrastructure,
    InfrastructureBuilder,
    MemoryModule,
    NetworkLink,
    Node,
    NodeAssemblyConfig,
    NodeBuilder,
    NodeRole,
    PartsCatalog,
    Processor,
    RuntimeConfig,
    SimulationConfig,
    StorageDevice,
    TycoonShell,
)
from hardware_sim.localization import resolve_locale

DEFAULT_SIMULATION_CONFIG = SimulationConfig(
    monitor_interval=1.0,
    work_id_start=1,
    spawn_interval_min=0.5,
    spawn_interval_max=3.0,
)

DEFAULT_CODE_RUNTIME_CONFIG = RuntimeConfig(
    hardware=None,
    simulation=DEFAULT_SIMULATION_CONFIG,
)

DEFAULT_APPLICATION_SERVER_ASSEMBLY = NodeAssemblyConfig(
    id="app-1",
    name="Application Server 1",
    role=NodeRole.APPLICATION_SERVER,
    motherboard="mb.starter.am4.ddr4",
    processors=("cpu.starter.4core",),
    memory_modules=("memory.starter",),
    storage_devices=("storage.starter.nvme",),
)

DEFAULT_DATABASE_SERVER_ASSEMBLY = NodeAssemblyConfig(
    id="db-1",
    name="Database Server 1",
    role=NodeRole.DATABASE_SERVER,
    motherboard="mb.server.sp5.ddr5",
    processors=("cpu.database.16core",),
    memory_modules=("memory.database",),
    storage_devices=("storage.database.nvme",),
)

DEFAULT_APP_DB_LINK = NetworkLink(
    source_node="app-1",
    target_node="db-1",
    network_interface="nic.1gbe",
)


def create_hardware_module(config: RuntimeConfig):
    hardware = config.hardware
    if hardware is None:
        raise ValueError("RuntimeConfig does not include hardware")

    return HardwareModule(
        cpu=Processor(
            cores=hardware.cpu.cores,
            clock_frequency_hz=hardware.cpu.clock_frequency_hz,
            name=hardware.cpu.name,
        ),
        memory=MemoryModule(
            capacity=hardware.memory.capacity,
            name=hardware.memory.name,
        ),
        storage=StorageDevice(
            capacity=hardware.storage.capacity,
            read_speed=hardware.storage.read_speed,
            write_speed=hardware.storage.write_speed,
            latency=hardware.storage.latency,
            queue_depth=hardware.storage.queue_depth,
            name=hardware.storage.name,
        ),
        workers=hardware.workers,
    )


def create_hardware_module_from_assembly(
    assembly: NodeAssemblyConfig,
    catalog: PartsCatalog = DEFAULT_PARTS_CATALOG,
):
    return NodeBuilder(catalog).build_module(assembly)


def create_node_from_assembly(
    assembly: NodeAssemblyConfig,
    catalog: PartsCatalog = DEFAULT_PARTS_CATALOG,
):
    return NodeBuilder(catalog).build(assembly)


def create_default_application_server(
    catalog: PartsCatalog = DEFAULT_PARTS_CATALOG,
):
    return create_node_from_assembly(
        DEFAULT_APPLICATION_SERVER_ASSEMBLY,
        catalog,
    )


def create_default_infrastructure(
    catalog: PartsCatalog = DEFAULT_PARTS_CATALOG,
):
    app_server = create_default_application_server(catalog)
    return Infrastructure(nodes={app_server.id: app_server})


def create_application_database_infrastructure(
    catalog: PartsCatalog = DEFAULT_PARTS_CATALOG,
):
    app_server = create_node_from_assembly(
        DEFAULT_APPLICATION_SERVER_ASSEMBLY,
        catalog,
    )
    db_server = create_node_from_assembly(
        DEFAULT_DATABASE_SERVER_ASSEMBLY,
        catalog,
    )
    return Infrastructure(
        nodes={
            app_server.id: app_server,
            db_server.id: db_server,
        },
        links=(DEFAULT_APP_DB_LINK,),
    )


def create_infrastructure_from_config(
    config: RuntimeConfig,
    catalog: PartsCatalog = DEFAULT_PARTS_CATALOG,
):
    if config.infrastructure is None:
        return create_default_infrastructure(catalog)
    return InfrastructureBuilder(catalog).build(config.infrastructure)


def main(
    max_jobs: int | None = None,
    config: RuntimeConfig | None = None,
    module: HardwareModule | Node | Infrastructure | None = None,
    workload_kind: str | None = None,
):
    config = config or DEFAULT_CODE_RUNTIME_CONFIG
    simulation = config.simulation
    module = module or create_runtime_module(config)
    monitor = None
    monitor_started = False

    try:
        monitor = HardwareMonitor(module, interval=simulation.monitor_interval)
        monitor.start()
        monitor_started = True

        for work_id in count(simulation.work_id_start):
            if max_jobs is not None and work_id > max_jobs:
                break

            work = DEFAULT_WORKLOADS.create_work(
                work_id,
                kind=workload_kind,
            )
            print(describe_work(work))
            put_work(module, work)

            interval = uniform(
                simulation.spawn_interval_min,
                simulation.spawn_interval_max,
            )
            sleep(interval)

    except KeyboardInterrupt:
        print("\nStopping...")

    finally:
        if monitor is None or not monitor_started:
            module.stop()
        else:
            try:
                module.wait_all()
            finally:
                try:
                    monitor.stop()
                finally:
                    module.stop()
                    print("Stopped")


def create_runtime_module(config: RuntimeConfig):
    if config.infrastructure is not None:
        return create_infrastructure_from_config(config)
    if config.hardware is not None:
        return create_hardware_module(config)
    return create_default_application_server()


def describe_work(work):
    if hasattr(work, "steps"):
        steps = ", ".join(f"{step.node_id}:{step.work.kind}" for step in work.steps)
        return f"Put: id={work.id}, kind={work.kind}, steps=[{steps}]"

    return (
        f"Put: id={work.id}, kind={work.kind}, "
        f"required_clocks={work.cpu.required_clocks:,}, "
        f"clock_usage_hz={work.cpu.clock_usage_hz:,}"
    )


def put_work(module: HardwareModule | Node | Infrastructure, work):
    if isinstance(module, Infrastructure):
        if hasattr(work, "steps"):
            for step in work.steps:
                module.put(step.node_id, step.work)
            return

        first_node_id = next(iter(module.nodes))
        module.put(first_node_id, work)
        return

    module.put(work)


def resolve_cli_locale(
    argv: Sequence[str], environment: Mapping[str, str], system: str | None
) -> str:
    parser = argparse.ArgumentParser(prog="main.py")
    parser.add_argument("--lang", metavar="LOCALE")
    arguments = parser.parse_args(argv)
    return resolve_locale(
        arguments.lang,
        environment.get("COMPUTE_TYCOON_LANG"),
        system,
    )


def run_cli(argv: Sequence[str] | None = None):
    try:
        detected_system_locale = locale.getlocale()[0]
    except OSError, ValueError:
        detected_system_locale = None
    selected_locale = resolve_cli_locale(
        () if argv is None else argv,
        os.environ,
        detected_system_locale,
    )
    shell = TycoonShell(locale=selected_locale)
    try:
        shell.cmdloop()
    finally:
        shell.game.stop_all()


if __name__ == "__main__":
    run_cli(sys.argv[1:])
