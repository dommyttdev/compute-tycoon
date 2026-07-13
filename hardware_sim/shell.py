import cmd
import shlex
from dataclasses import dataclass, field

from hardware_sim.game import (
    BuildRequest,
    ComputeTycoonGame,
    normalize_part_kind,
)
from hardware_sim.localization import ENGLISH_INTRO, message, shell_intro
from hardware_sim.node import NodeRole
from hardware_sim.work import StepResult, WorkloadResult

INTRO = ENGLISH_INTRO


@dataclass(frozen=True)
class HelpTopic:
    usage: str
    summary_key: str
    detail_usages: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    related: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()

    @property
    def command(self) -> str:
        return self.usage.partition(" ")[0]


@dataclass(frozen=True)
class HelpGroup:
    heading_key: str
    topics: tuple[HelpTopic, ...]


TOP_LEVEL_HELP = (
    HelpGroup(
        "help.group.acquire",
        (
            HelpTopic(
                "shop",
                "help.shop.summary",
                detail_usages=("shop",),
                examples=("shop",),
            ),
            HelpTopic(
                "inventory",
                "help.inventory.summary",
                detail_usages=("inventory",),
                examples=("inventory",),
            ),
            HelpTopic(
                "build NODE_ID",
                "help.build.summary",
                detail_usages=("build NODE_ID",),
                examples=("build compute-1",),
            ),
        ),
    ),
    HelpGroup(
        "help.group.nodes",
        (
            HelpTopic(
                "node ...",
                "help.node.summary",
                detail_usages=(
                    "node list | node ls",
                    "node add NODE_ID ROLE",
                    "node role set NODE_ID ROLE",
                    "node show NODE_ID",
                ),
                examples=("node add app-1 application_server",),
                related=("shop", "build", "server"),
            ),
            HelpTopic(
                "server ...",
                "help.server.summary",
                detail_usages=(
                    "server list | server ls",
                    "server name set NODE_ID NAME",
                    "server show NODE_ID",
                ),
                examples=("server show app-1",),
            ),
            HelpTopic(
                "ssh NODE_ID",
                "help.ssh.summary",
                detail_usages=("ssh NODE_ID",),
                examples=("ssh app-1",),
            ),
        ),
    ),
    HelpGroup(
        "help.group.topology",
        (
            HelpTopic(
                "link ...",
                "help.link.summary",
                detail_usages=(
                    "link list | link ls",
                    "link connect NODE:PORT NODE:PORT [CABLE]",
                    "link disconnect NODE:PORT",
                ),
                examples=("link list",),
            ),
            HelpTopic(
                "ip ...",
                "help.ip.summary",
                detail_usages=(
                    "ip addr",
                    "ip addr add NODE:PORT CIDR",
                    "ip route [NODE]",
                ),
                examples=("ip addr",),
            ),
            HelpTopic(
                "route ...",
                "help.route.summary",
                detail_usages=(
                    "route list [NODE] | route ls [NODE]",
                    "route add NODE DESTINATION via GATEWAY [dev PORT]",
                ),
                examples=("route list",),
            ),
            HelpTopic(
                "ping SOURCE_NODE TARGET_NODE",
                "help.ping.summary",
                detail_usages=("ping SOURCE_NODE TARGET_NODE",),
                examples=("ping app-1 db-1",),
            ),
            HelpTopic(
                "traceroute SOURCE_NODE TARGET_NODE",
                "help.traceroute.summary",
                detail_usages=("traceroute SOURCE_NODE TARGET_NODE",),
                examples=("traceroute app-1 db-1",),
            ),
        ),
    ),
    HelpGroup(
        "help.group.workloads",
        (
            HelpTopic(
                "run workload KIND",
                "help.run.summary",
                detail_usages=("run workload KIND [--jobs N]",),
                examples=("run workload web",),
            ),
            HelpTopic(
                "logs [NODE]",
                "help.logs.summary",
                detail_usages=("logs [NODE]",),
                examples=("logs app-1",),
            ),
        ),
    ),
    HelpGroup(
        "help.group.session",
        (
            HelpTopic(
                "help [COMMAND]",
                "help.help.summary",
                detail_usages=("help [COMMAND]",),
                examples=("help node",),
            ),
            HelpTopic(
                "exit | quit",
                "help.exit.summary",
                detail_usages=("exit | quit",),
                examples=("exit",),
                aliases=("quit",),
            ),
        ),
    ),
)

SHOP_HELP = (
    HelpGroup(
        "shop.group.commands",
        (
            HelpTopic("list [KIND] | ls [KIND]", "shop.list.summary"),
            HelpTopic("buy server ROLE [QTY]", "shop.buy_server.summary"),
            HelpTopic("buy cable CABLE [QTY]", "shop.buy_cable.summary"),
            HelpTopic("buy KIND PART_ID [QTY]", "shop.buy_part.summary"),
            HelpTopic("inventory", "help.inventory.summary"),
            HelpTopic("exit | back", "shop.exit.summary"),
        ),
    ),
)

BUILD_HELP = (
    HelpGroup(
        "build.group.parts",
        (
            HelpTopic("motherboard list | motherboard ls", "build.part_list.summary"),
            HelpTopic("motherboard select PART_ID", "build.part_select.summary"),
            HelpTopic("cpu|ram|storage|gpu|nic list", "build.part_list.summary"),
            HelpTopic("cpu|ram|storage|gpu|nic add PART_ID", "build.part_add.summary"),
            HelpTopic(
                "cpu|ram|storage|gpu|nic remove PART_ID",
                "build.part_remove.summary",
            ),
        ),
    ),
    HelpGroup(
        "build.group.configure",
        (
            HelpTopic("name NAME", "build.name.summary"),
            HelpTopic("workers COUNT", "build.workers.summary"),
        ),
    ),
    HelpGroup(
        "build.group.finish",
        (
            HelpTopic("summary", "build.summary.summary"),
            HelpTopic("validate", "build.validate.summary"),
            HelpTopic("commit", "build.commit.summary"),
            HelpTopic("cancel | exit", "build.cancel.summary"),
        ),
    ),
)

NODE_HELP = (
    HelpGroup(
        "node_shell.group.inspect",
        (
            HelpTopic("ip addr", "node_shell.address.summary"),
            HelpTopic("ip route", "node_shell.route.summary"),
            HelpTopic("show interfaces", "node_shell.interfaces.summary"),
            HelpTopic("show ip route", "node_shell.route.summary"),
            HelpTopic("top", "node_shell.top.summary"),
            HelpTopic("journalctl", "node_shell.journal.summary"),
            HelpTopic("exit | logout", "node_shell.exit.summary"),
        ),
    ),
)

SHOP_DETAIL_HELP = (
    HelpGroup(
        "shop.group.commands",
        (
            HelpTopic(
                "list [KIND] | ls [KIND]",
                "shop.list_detail.summary",
                detail_usages=("list [KIND] | ls [KIND]",),
                examples=("list server",),
                aliases=("ls",),
            ),
            HelpTopic(
                "buy ...",
                "shop.buy.summary",
                detail_usages=(
                    "buy server ROLE [QTY]",
                    "buy cable CABLE [QTY]",
                    "buy KIND PART_ID [QTY]",
                ),
                examples=("buy server application_server",),
            ),
            HelpTopic(
                "inventory",
                "help.inventory.summary",
                detail_usages=("inventory",),
                examples=("inventory",),
            ),
            HelpTopic(
                "exit | back",
                "shop.exit.summary",
                detail_usages=("exit | back",),
                examples=("exit",),
                aliases=("back",),
            ),
        ),
    ),
)

BUILD_DETAIL_HELP = (
    HelpGroup(
        "build.group.parts",
        (
            HelpTopic(
                "motherboard ...",
                "build.motherboard.summary",
                detail_usages=(
                    "motherboard list | motherboard ls",
                    "motherboard select PART_ID",
                ),
                examples=("motherboard list",),
            ),
            HelpTopic(
                "cpu ...",
                "build.cpu.summary",
                detail_usages=(
                    "cpu list",
                    "cpu add PART_ID",
                    "cpu remove PART_ID",
                ),
                examples=("cpu list",),
            ),
            HelpTopic(
                "ram ...",
                "build.ram.summary",
                detail_usages=(
                    "ram list",
                    "ram add PART_ID",
                    "ram remove PART_ID",
                ),
                examples=("ram list",),
            ),
            HelpTopic(
                "storage ...",
                "build.storage.summary",
                detail_usages=(
                    "storage list",
                    "storage add PART_ID",
                    "storage remove PART_ID",
                ),
                examples=("storage list",),
            ),
            HelpTopic(
                "gpu ...",
                "build.gpu.summary",
                detail_usages=(
                    "gpu list",
                    "gpu add PART_ID",
                    "gpu remove PART_ID",
                ),
                examples=("gpu list",),
            ),
            HelpTopic(
                "nic ...",
                "build.nic.summary",
                detail_usages=(
                    "nic list",
                    "nic add PART_ID",
                    "nic remove PART_ID",
                ),
                examples=("nic list",),
            ),
        ),
    ),
    HelpGroup(
        "build.group.configure",
        (
            HelpTopic(
                "name NAME",
                "build.name.summary",
                detail_usages=("name NAME",),
                examples=("name web-1",),
            ),
            HelpTopic(
                "workers COUNT",
                "build.workers.summary",
                detail_usages=("workers COUNT",),
                examples=("workers 4",),
            ),
        ),
    ),
    HelpGroup(
        "build.group.finish",
        (
            HelpTopic(
                "summary",
                "build.summary.summary",
                detail_usages=("summary",),
                examples=("summary",),
            ),
            HelpTopic(
                "validate",
                "build.validate.summary",
                detail_usages=("validate",),
                examples=("validate",),
            ),
            HelpTopic(
                "commit",
                "build.commit.summary",
                detail_usages=("commit",),
                examples=("commit",),
            ),
            HelpTopic(
                "cancel | exit",
                "build.cancel.summary",
                detail_usages=("cancel | exit",),
                examples=("cancel",),
                aliases=("exit",),
            ),
        ),
    ),
)

NODE_DETAIL_HELP = (
    HelpGroup(
        "node_shell.group.inspect",
        (
            HelpTopic(
                "ip ...",
                "node_shell.ip.summary",
                detail_usages=("ip addr", "ip route"),
                examples=("ip addr",),
            ),
            HelpTopic(
                "show ...",
                "node_shell.show.summary",
                detail_usages=("show interfaces", "show ip route"),
                examples=("show interfaces",),
            ),
            HelpTopic(
                "top",
                "node_shell.top.summary",
                detail_usages=("top",),
                examples=("top",),
            ),
            HelpTopic(
                "journalctl",
                "node_shell.journal.summary",
                detail_usages=("journalctl",),
                examples=("journalctl",),
            ),
            HelpTopic(
                "exit | logout",
                "node_shell.exit.summary",
                detail_usages=("exit | logout",),
                examples=("exit",),
                aliases=("logout",),
            ),
        ),
    ),
)


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

    def __init__(self, game: ComputeTycoonGame | None = None, *, locale: str = "en"):
        super().__init__()
        self.game = game or ComputeTycoonGame()
        self.locale = locale
        self.intro = shell_intro(locale)

    def do_help(self, arg: str):
        topic_name = arg.strip()
        if topic_name:
            topic = _top_level_help_topic(topic_name)
            if topic is not None and topic.detail_usages:
                _print_topic_help(self.locale, topic)
                return None
            return super().do_help(arg)
        _print_bare_help(self.locale, TOP_LEVEL_HELP, title_key="help.title")

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
            BuildShell(self.game, args[0], locale=self.locale).cmdloop()
        except Exception as error:
            print(f"error: {error}")

    def do_shop(self, arg: str):
        """shop"""
        try:
            args = _split(arg)
            if not args:
                ShopShell(self.game, locale=self.locale).cmdloop()
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
            NodeShell(self.game, args[0], locale=self.locale).cmdloop()
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

    def __init__(self, game: ComputeTycoonGame, *, locale: str = "en"):
        super().__init__()
        self.game = game
        self.locale = locale
        self.intro = message(locale, "shop.intro")

    def do_help(self, arg: str):
        topic_name = arg.strip()
        if topic_name:
            topic = _help_topic(SHOP_DETAIL_HELP, topic_name)
            if topic is not None:
                _print_topic_help(self.locale, topic)
                return None
            return super().do_help(arg)
        _print_bare_help(self.locale, SHOP_HELP)

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
    def __init__(self, game: ComputeTycoonGame, node_id: str, *, locale: str = "en"):
        super().__init__()
        self.game = game
        self.locale = locale
        self.draft = BuildDraft(node_id=node_id)
        self.prompt = f"build({node_id})> "

    def do_help(self, arg: str):
        topic_name = arg.strip()
        if topic_name:
            topic = _help_topic(BUILD_DETAIL_HELP, topic_name)
            if topic is not None:
                _print_topic_help(self.locale, topic)
                return None
            return super().do_help(arg)
        _print_bare_help(self.locale, BUILD_HELP)

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
    def __init__(self, game: ComputeTycoonGame, node_id: str, *, locale: str = "en"):
        super().__init__()
        self.game = game
        self.locale = locale
        self.node_id = node_id
        role = self.game.nodes[node_id].role
        suffix = "#" if role in {NodeRole.ROUTER, NodeRole.NETWORK_SWITCH} else "$"
        self.prompt = f"{node_id}{suffix} "

    def do_help(self, arg: str):
        topic_name = arg.strip()
        if topic_name:
            topic = _help_topic(NODE_DETAIL_HELP, topic_name)
            if topic is not None:
                _print_topic_help(self.locale, topic)
                return None
            return super().do_help(arg)
        _print_bare_help(self.locale, NODE_HELP)

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


def _top_level_help_topic(command: str) -> HelpTopic | None:
    return _help_topic(TOP_LEVEL_HELP, command)


def _help_topic(groups: tuple[HelpGroup, ...], command: str) -> HelpTopic | None:
    for group in groups:
        for topic in group.topics:
            if topic.command == command or command in topic.aliases:
                return topic
    return None


def _print_bare_help(
    locale: str, groups: tuple[HelpGroup, ...], *, title_key: str | None = None
) -> None:
    if title_key is not None:
        print(message(locale, title_key))
    for group in groups:
        if title_key is not None or group is not groups[0]:
            print()
        print(message(locale, group.heading_key))
        for topic in group.topics:
            print(f"  {topic.usage:<38} {message(locale, topic.summary_key)}")


def _print_topic_help(locale: str, topic: HelpTopic) -> None:
    print(f"{topic.command} — {message(locale, topic.summary_key)}")
    print()
    print(f"{message(locale, 'help.section.usage')}:")
    _print_indented(topic.detail_usages)
    if topic.examples:
        print()
        print(f"{message(locale, 'help.section.examples')}:")
        _print_indented(topic.examples)
    if topic.related:
        print()
        print(f"{message(locale, 'help.section.related')}:")
        _print_indented(topic.related)


def _print_indented(lines: tuple[str, ...]) -> None:
    for line in lines:
        print(f"  {line}")


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
