import cmd
import shlex
from dataclasses import dataclass, field

from hardware_sim.game import (
    BuildRequest,
    ComputeTycoonGame,
    normalize_part_kind,
)
from hardware_sim.node import NodeRole
from hardware_sim.work import StepResult, WorkloadResult

INTRO = """Compute Tycoon
Type 'help' for commands, or start with 'shop' / 'build SERVER_ID'.
"""


@dataclass
class BuildDraft:
    node_id: str
    role: NodeRole = NodeRole.UNASSIGNED
    name: str | None = None
    motherboard: str | None = None
    processors: list[str] = field(default_factory=list)
    memory_modules: list[str] = field(default_factory=list)
    storage_devices: list[str] = field(default_factory=list)
    gpus: list[str] = field(default_factory=list)
    network_interfaces: list[str] = field(default_factory=list)
    workers: int | None = None

    def to_request(self):
        return BuildRequest(
            node_id=self.node_id,
            role=self.role,
            name=self.name,
            motherboard=self.motherboard,
            processors=tuple(self.processors),
            memory_modules=tuple(self.memory_modules),
            storage_devices=tuple(self.storage_devices),
            gpus=tuple(self.gpus),
            network_interfaces=tuple(self.network_interfaces),
            workers=self.workers,
        )


class TycoonShell(cmd.Cmd):
    intro = INTRO
    prompt = "compute-tycoon> "

    def __init__(self, game: ComputeTycoonGame | None = None):
        super().__init__()
        self.game = game or ComputeTycoonGame()

    def do_node(self, arg: str):
        """node list | node add ID ROLE | node role set ID ROLE | node show ID"""
        try:
            args = _split(arg)
            if not args or args[0] in {"list", "ls"}:
                _print_lines(self.game.node_summary())
                return
            if args[0] == "create":
                raise ValueError(
                    "node create was removed. Use 'node add' for purchased "
                    "prebuilt nodes or 'build' for manual assembly."
                )
            if args[0] == "add":
                _require_len(args, 3, "node add ID ROLE")
                node = self.game.add_node(args[1], args[2])
                print(f"added {node.id} ({node.role.value})")
                return
            if args[0] == "role":
                if len(args) != 4 or args[1] != "set":
                    raise ValueError("usage: node role set ID ROLE")
                node = self.game.set_node_role(args[2], args[3])
                print(f"role set: {node.id} -> {node.role.value}")
                return
            if args[0] == "show":
                _require_len(args, 2, "node show ID")
                _print_lines(self.game.interface_summary(args[1]))
                return
            raise ValueError(f"Unknown node command: {args[0]}")
        except Exception as error:
            print(f"error: {error}")

    def do_server(self, arg: str):
        """server list | server name set ID NAME | server show ID"""
        try:
            args = _split(arg)
            if not args or args[0] in {"list", "ls"}:
                _print_lines(self.game.server_summary())
                return
            if args[0] == "name":
                if len(args) < 4 or args[1] != "set":
                    raise ValueError("usage: server name set ID NAME")
                server = self.game.rename_server(args[2], " ".join(args[3:]))
                print(f"server renamed: {server.id} -> {server.name}")
                return
            if args[0] == "show":
                _require_len(args, 2, "server show ID")
                _print_lines(self.game.interface_summary(args[1]))
                return
            raise ValueError(f"Unknown server command: {args[0]}")
        except Exception as error:
            print(f"error: {error}")

    def do_build(self, arg: str):
        """build ID"""
        try:
            args = _split(arg)
            _require_len(args, 1, "build ID")
            BuildShell(self.game, args[0]).cmdloop()
        except Exception as error:
            print(f"error: {error}")

    def do_shop(self, arg: str):
        """shop"""
        try:
            args = _split(arg)
            if not args:
                ShopShell(self.game).cmdloop()
                return
            raise ValueError(
                "shop commands are only available in shop mode. "
                "Enter shop mode with: shop"
            )
        except Exception as error:
            print(f"error: {error}")

    def do_inventory(self, arg: str):
        """inventory"""
        _print_lines(self.game.inventory_summary())

    def do_link(self, arg: str):
        """link list | link connect NODE:PORT NODE:PORT [CABLE] | link disconnect NODE:PORT"""
        try:
            args = _split(arg)
            if not args or args[0] in {"list", "ls"}:
                _print_lines(self.game.link_summary())
                return
            if args[0] == "connect":
                if len(args) not in {3, 4}:
                    raise ValueError("usage: link connect NODE:PORT NODE:PORT [CABLE]")
                cable_id = args[3] if len(args) == 4 else None
                self.game.connect(args[1], args[2], cable_id=cable_id)
                suffix = f" using {cable_id}" if cable_id is not None else ""
                print(f"connected {args[1]} <-> {args[2]}{suffix}")
                return
            if args[0] == "disconnect":
                _require_len(args, 2, "link disconnect NODE:PORT")
                cable = self.game.disconnect(args[1])
                print(f"disconnected {cable.a} <-> {cable.b}")
                return
            raise ValueError(f"Unknown link command: {args[0]}")
        except Exception as error:
            print(f"error: {error}")

    def do_ip(self, arg: str):
        """ip addr | ip addr add NODE:PORT CIDR | ip route [NODE]"""
        try:
            args = _split(arg)
            if len(args) >= 1 and args[0] == "addr":
                self._ip_addr(args[1:])
                return
            if len(args) >= 1 and args[0] == "route":
                node_id = args[1] if len(args) > 1 else None
                _print_lines(self.game.route_summary(node_id))
                return
            raise ValueError("usage: ip addr | ip addr add NODE:PORT CIDR")
        except Exception as error:
            print(f"error: {error}")

    def do_route(self, arg: str):
        """route list [NODE] | route add NODE DESTINATION via GATEWAY [dev PORT]"""
        try:
            args = _split(arg)
            if not args or args[0] in {"list", "ls"}:
                node_id = args[1] if len(args) > 1 else None
                _print_lines(self.game.route_summary(node_id))
                return
            if args[0] == "add":
                if len(args) not in {5, 7}:
                    raise ValueError(
                        "usage: route add NODE DESTINATION via GATEWAY [dev PORT]"
                    )
                if args[3] != "via":
                    raise ValueError("route add requires 'via'")
                interface = None
                if len(args) > 5:
                    if args[5] != "dev":
                        raise ValueError("optional interface must be: dev PORT")
                    interface = args[6]
                self.game.add_route(
                    args[1], args[2], gateway=args[4], interface=interface
                )
                print(f"route added on {args[1]}")
                return
            raise ValueError(f"Unknown route command: {args[0]}")
        except Exception as error:
            print(f"error: {error}")

    def do_ping(self, arg: str):
        """ping SOURCE_NODE TARGET_NODE"""
        try:
            args = _split(arg)
            _require_len(args, 2, "ping SOURCE_NODE TARGET_NODE")
            route = self.game.ping(args[0], args[1])
            print(f"reply from {route.target_ip}: {route.describe()}")
        except Exception as error:
            print(f"error: {error}")

    def do_traceroute(self, arg: str):
        """traceroute SOURCE_NODE TARGET_NODE"""
        try:
            args = _split(arg)
            _require_len(args, 2, "traceroute SOURCE_NODE TARGET_NODE")
            route = self.game.traceroute(args[0], args[1])
            for index, hop in enumerate(route.hops, start=1):
                print(f"{index}\t{hop}")
        except Exception as error:
            print(f"error: {error}")

    def do_ssh(self, arg: str):
        """ssh NODE"""
        try:
            args = _split(arg)
            _require_len(args, 1, "ssh NODE")
            NodeShell(self.game, args[0]).cmdloop()
        except Exception as error:
            print(f"error: {error}")

    def do_run(self, arg: str):
        """run workload KIND [--jobs N]"""
        try:
            args = _split(arg)
            if len(args) < 2 or args[0] != "workload":
                raise ValueError("usage: run workload KIND [--jobs N]")
            jobs = 1
            if len(args) > 2:
                if len(args) != 4 or args[2] != "--jobs":
                    raise ValueError("usage: run workload KIND [--jobs N]")
                jobs = int(args[3])
            result = self.game.run_workload(args[1], jobs=jobs)
            if isinstance(result, WorkloadResult):
                _print_lines(_format_workload_result(result))
            else:
                _print_lines(result)
        except Exception as error:
            print(f"error: {error}")

    def do_logs(self, arg: str):
        """logs [NODE]"""
        args = _split(arg)
        _print_lines(self.game.logs(node_id=args[0] if args else None))

    def do_exit(self, arg: str):
        """exit"""
        self.game.stop_all()
        return True

    def do_quit(self, arg: str):
        """quit"""
        return self.do_exit(arg)

    def do_EOF(self, arg: str):
        print()
        return self.do_exit(arg)

    def emptyline(self):
        return None

    def _ip_addr(self, args: list[str]):
        if not args:
            _print_lines(self.game.address_summary())
            return
        if args[0] == "add":
            _require_len(args, 3, "ip addr add NODE:PORT CIDR")
            self.game.add_address(args[1], args[2])
            print(f"assigned {args[2]} to {args[1]}")
            return
        raise ValueError("usage: ip addr | ip addr add NODE:PORT CIDR")


class ShopShell(cmd.Cmd):
    intro = "Shop mode. Type 'list', 'buy ...', 'inventory', or 'exit'."
    prompt = "shop> "

    def __init__(self, game: ComputeTycoonGame):
        super().__init__()
        self.game = game

    def do_list(self, arg: str):
        """list [KIND]"""
        try:
            args = _split(arg)
            if len(args) > 1:
                raise ValueError("usage: list [KIND]")
            _print_lines(self.game.shop_summary(args[0] if args else None))
        except Exception as error:
            print(f"error: {error}")

    def do_ls(self, arg: str):
        """ls [KIND]"""
        return self.do_list(arg)

    def do_buy(self, arg: str):
        """buy server ROLE [QTY] | buy cable CABLE [QTY] | buy KIND PART [QTY]"""
        try:
            args = _split(arg)
            if len(args) not in {2, 3}:
                raise ValueError(
                    "usage: buy server ROLE [QTY] | buy cable CABLE [QTY] | "
                    "buy KIND PART [QTY]"
                )
            quantity = int(args[2]) if len(args) == 3 else 1
            if args[0] == "server":
                self.game.buy_server(args[1], quantity=quantity)
                print(f"bought server {args[1]} x{quantity}")
                return
            if args[0] == "cable":
                self.game.buy_cable(args[1], quantity=quantity)
                print(f"bought cable {args[1]} x{quantity}")
                return
            self.game.buy_part(args[0], args[1], quantity=quantity)
            print(f"bought {args[0]} {args[1]} x{quantity}")
        except Exception as error:
            print(f"error: {error}")

    def do_inventory(self, arg: str):
        """inventory"""
        _print_lines(self.game.inventory_summary())

    def do_exit(self, arg: str):
        """exit"""
        return True

    def do_back(self, arg: str):
        """back"""
        return True

    def do_EOF(self, arg: str):
        print()
        return True

    def emptyline(self):
        return None


class BuildShell(cmd.Cmd):
    def __init__(self, game: ComputeTycoonGame, node_id: str):
        super().__init__()
        self.game = game
        self.draft = BuildDraft(node_id=node_id)
        self.prompt = f"build({node_id})> "

    def do_motherboard(self, arg: str):
        """motherboard list | motherboard select PART"""
        self._single_part("motherboards", "motherboard", arg)

    def do_cpu(self, arg: str):
        """cpu list | cpu add PART | cpu remove PART"""
        self._list_part("processors", self.draft.processors, arg)

    def do_ram(self, arg: str):
        """ram list | ram add PART | ram remove PART"""
        self._list_part("memory", self.draft.memory_modules, arg)

    def do_storage(self, arg: str):
        """storage list | storage add PART | storage remove PART"""
        self._list_part("storage", self.draft.storage_devices, arg)

    def do_gpu(self, arg: str):
        """gpu list | gpu add PART | gpu remove PART"""
        self._list_part("gpus", self.draft.gpus, arg)

    def do_nic(self, arg: str):
        """nic list | nic add PART | nic remove PART"""
        self._list_part("network_interfaces", self.draft.network_interfaces, arg)

    def do_name(self, arg: str):
        """name VALUE"""
        value = arg.strip()
        if not value:
            print("error: usage: name VALUE")
            return
        self.draft.name = value
        print(f"name set to {value}")

    def do_workers(self, arg: str):
        """workers COUNT"""
        try:
            args = _split(arg)
            _require_len(args, 1, "workers COUNT")
            workers = int(args[0])
            if workers < 1:
                raise ValueError("workers must be greater than 0")
            self.draft.workers = workers
            print(f"workers set to {workers}")
        except Exception as error:
            print(f"error: {error}")

    def do_summary(self, arg: str):
        """summary"""
        _print_lines(self._summary_lines())

    def do_validate(self, arg: str):
        """validate"""
        try:
            self.game.validate_build_request(self.draft.to_request())
            print("valid")
        except Exception as error:
            print(f"invalid: {error}")

    def do_commit(self, arg: str):
        """commit"""
        try:
            node = self.game.build_node(self.draft.to_request())
            print(f"built {node.id} ({node.role.value})")
            return True
        except Exception as error:
            print(f"error: {error}")
            return None

    def do_cancel(self, arg: str):
        """cancel"""
        print("cancelled")
        return True

    def do_exit(self, arg: str):
        """exit"""
        return self.do_cancel(arg)

    def do_EOF(self, arg: str):
        print()
        return self.do_cancel(arg)

    def emptyline(self):
        return None

    def _single_part(self, kind: str, attr: str, arg: str):
        try:
            args = _split(arg)
            if not args or args[0] in {"list", "ls"}:
                _print_lines(self._part_lines(kind))
                return
            if args[0] == "select":
                _require_len(args, 2, f"{attr} select PART")
                self._require_owned(kind, args[1], extra=1)
                setattr(self.draft, attr, args[1])
                print(f"{attr} selected: {args[1]}")
                return
            raise ValueError(f"Unknown {attr} command: {args[0]}")
        except Exception as error:
            print(f"error: {error}")

    def _list_part(self, kind: str, values: list[str], arg: str):
        try:
            args = _split(arg)
            if not args or args[0] in {"list", "ls"}:
                _print_lines(self._part_lines(kind))
                return
            if args[0] == "add":
                _require_len(args, 2, "PART add PART")
                self._require_owned(kind, args[1], extra=1, values=values)
                values.append(args[1])
                print(f"added {args[1]}")
                return
            if args[0] == "remove":
                _require_len(args, 2, "PART remove PART")
                values.remove(args[1])
                print(f"removed {args[1]}")
                return
            raise ValueError(f"Unknown part command: {args[0]}")
        except Exception as error:
            print(f"error: {error}")

    def _part_lines(self, kind: str):
        parts = _parts_for_kind(self.game, kind)
        return tuple(
            f"{part_id}\towned={self.game.inventory.part_quantity(kind, part_id)}\t"
            f"{getattr(part, 'name', type(part).__name__)}"
            for part_id, part in parts.items()
        )

    def _require_owned(
        self,
        kind: str,
        part_id: str,
        extra: int = 1,
        values: list[str] | None = None,
    ):
        parts = _parts_for_kind(self.game, kind)
        if part_id not in parts:
            raise KeyError(f"Unknown {kind} part: {part_id}")
        used = 0 if values is None else values.count(part_id)
        owned = self.game.inventory.part_quantity(kind, part_id)
        if owned < used + extra:
            raise ValueError(f"{kind} {part_id} is not available in inventory")

    def _summary_lines(self):
        return (
            f"id: {self.draft.node_id}",
            f"role: {self.draft.role.value}",
            f"name: {self.draft.name or '-'}",
            f"motherboard: {self.draft.motherboard or '-'}",
            f"cpu: {_join(self.draft.processors)}",
            f"ram: {_join(self.draft.memory_modules)}",
            f"storage: {_join(self.draft.storage_devices)}",
            f"gpu: {_join(self.draft.gpus)}",
            f"nic: {_join(self.draft.network_interfaces)}",
            f"workers: {self.draft.workers or '-'}",
        )


class NodeShell(cmd.Cmd):
    def __init__(self, game: ComputeTycoonGame, node_id: str):
        super().__init__()
        self.game = game
        self.node_id = node_id
        role = self.game.nodes[node_id].role
        suffix = "#" if role in {NodeRole.ROUTER, NodeRole.NETWORK_SWITCH} else "$"
        self.prompt = f"{node_id}{suffix} "

    def do_ip(self, arg: str):
        """ip addr | ip route"""
        try:
            args = _split(arg)
            if not args or args[0] == "addr":
                _print_lines(self.game.address_summary(self.node_id))
                return
            if args[0] == "route":
                _print_lines(self.game.route_summary(self.node_id))
                return
            raise ValueError("usage: ip addr | ip route")
        except Exception as error:
            print(f"error: {error}")

    def do_show(self, arg: str):
        """show interfaces | show ip route"""
        try:
            args = _split(arg)
            if args == ["interfaces"]:
                _print_lines(self.game.interface_summary(self.node_id))
                return
            if args == ["ip", "route"]:
                _print_lines(self.game.route_summary(self.node_id))
                return
            raise ValueError("usage: show interfaces | show ip route")
        except Exception as error:
            print(f"error: {error}")

    def do_top(self, arg: str):
        """top"""
        print(self.game.snapshot_text(self.node_id))

    def do_journalctl(self, arg: str):
        """journalctl"""
        _print_lines(self.game.logs(node_id=self.node_id))

    def do_exit(self, arg: str):
        """exit"""
        return True

    def do_logout(self, arg: str):
        """logout"""
        return True

    def do_EOF(self, arg: str):
        print()
        return True

    def emptyline(self):
        return None


def _parts_for_kind(game: ComputeTycoonGame, kind: str):
    kind = normalize_part_kind(kind)
    groups = {
        "motherboards": game.catalog.motherboards,
        "processors": game.catalog.processors,
        "memory": game.catalog.memory,
        "storage": game.catalog.storage,
        "gpus": game.catalog.gpus,
        "network_interfaces": game.catalog.network_interfaces,
    }
    return groups[kind]


def _join(values: list[str]):
    return ", ".join(values) if values else "-"


def _split(arg: str):
    return shlex.split(arg)


def _require_len(args: list[str], expected: int, usage: str):
    if len(args) != expected:
        raise ValueError(f"usage: {usage}")


def _print_lines(lines):
    printed = False
    for line in lines:
        printed = True
        print(line)
    if not printed:
        print("(empty)")


def _format_workload_result(result: WorkloadResult):
    lines = [f"Workload {result.kind}: {result.status}"]
    if result.failure is not None:
        lines.append(f"  failure={result.failure.code}: {result.failure.message}")
    for job in result.jobs:
        lines.append(f"Job {job.id}: {job.status}")
        if job.failure is not None:
            lines.append(f"  failure={job.failure.code}: {job.failure.message}")
        lines.extend(_format_step_result(job.root, indent="  "))
    return tuple(lines)


def _format_step_result(step: StepResult, indent: str):
    node = step.node_id or "-"
    route = " -> ".join(step.route) if step.route else "-"
    lines = [
        f"{indent}{step.phase}: {step.status} role={step.role} "
        f"node={node} work={step.work_id} route={route}"
    ]
    if step.failure is not None:
        lines.append(f"{indent}  failure={step.failure.code}: {step.failure.message}")
    for child in step.children:
        lines.extend(_format_step_result(child, indent=f"{indent}  "))
    return lines
