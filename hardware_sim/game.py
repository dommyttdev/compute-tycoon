import json
from dataclasses import dataclass, field, replace
from itertools import count
from pathlib import Path
from threading import RLock

from hardware_sim.assembly import NodeAssemblyConfig, NodeBuilder
from hardware_sim.catalog import DEFAULT_PARTS_CATALOG, PartsCatalog
from hardware_sim.errors import SaveDataError
from hardware_sim.events import EventLog
from hardware_sim.monitor import HardwareMonitor
from hardware_sim.networking import (
    InterfaceAddress,
    NetworkPortRef,
    NetworkTopology,
    RouteEntry,
)
from hardware_sim.node import Node, NodeRole
from hardware_sim.persistence import AutosaveWorker
from hardware_sim.workloads import DEFAULT_WORKLOADS, WorkloadCatalog

DEFAULT_SAVE_PATH = Path(__file__).parent / "data" / "save_game.json"
SAVE_VERSION = 1
DEFAULT_CABLE_ID = "cable.cat6.patch"


DEFAULT_NODE_PARTS = {
    NodeRole.APPLICATION_SERVER: {
        "motherboard": "mb.starter.am4.ddr4",
        "processors": ("cpu.starter.4core",),
        "memory_modules": ("memory.app",),
        "storage_devices": ("storage.app.nvme",),
        "expansion_network_interfaces": (),
    },
    NodeRole.DATABASE_SERVER: {
        "motherboard": "mb.server.sp5.ddr5",
        "processors": ("cpu.database.16core",),
        "memory_modules": ("memory.database",),
        "storage_devices": ("storage.database.nvme",),
        "expansion_network_interfaces": (),
    },
    NodeRole.NETWORK_SWITCH: {
        "motherboard": "mb.server.sp5.ddr5",
        "processors": ("cpu.database.16core",),
        "memory_modules": ("memory.database",),
        "storage_devices": ("storage.database.nvme",),
        "expansion_network_interfaces": ("nic.switch.48port",),
        "workers": 1,
    },
    NodeRole.ROUTER: {
        "motherboard": "mb.server.sp5.ddr5",
        "processors": ("cpu.database.16core",),
        "memory_modules": ("memory.database",),
        "storage_devices": ("storage.database.nvme",),
        "expansion_network_interfaces": (),
        "workers": 1,
    },
}


PART_KIND_ALIASES = {
    "motherboard": "motherboards",
    "motherboards": "motherboards",
    "cpu": "processors",
    "processor": "processors",
    "processors": "processors",
    "ram": "memory",
    "memory": "memory",
    "storage": "storage",
    "gpu": "gpus",
    "gpus": "gpus",
    "nic": "network_interfaces",
    "network": "network_interfaces",
    "network_interface": "network_interfaces",
    "network_interfaces": "network_interfaces",
}


REQUEST_PART_FIELDS = {
    "motherboards": ("motherboard",),
    "processors": ("processors",),
    "memory": ("memory_modules",),
    "storage": ("storage_devices",),
    "gpus": ("gpus",),
    "network_interfaces": ("network_interfaces",),
}


@dataclass(frozen=True)
class BuildRequest:
    node_id: str
    role: NodeRole = NodeRole.UNASSIGNED
    name: str | None = None
    motherboard: str | None = None
    processors: tuple[str, ...] = ()
    memory_modules: tuple[str, ...] = ()
    storage_devices: tuple[str, ...] = ()
    gpus: tuple[str, ...] = ()
    network_interfaces: tuple[str, ...] = ()
    workers: int | None = None


@dataclass
class Inventory:
    parts: dict[str, dict[str, int]] = field(default_factory=dict)
    servers: dict[str, int] = field(default_factory=dict)
    cables: dict[str, int] = field(default_factory=dict)

    def add_part(self, kind: str, part_id: str, quantity: int = 1):
        kind = normalize_part_kind(kind)
        _require_positive_quantity(quantity)
        bucket = self.parts.setdefault(kind, {})
        bucket[part_id] = bucket.get(part_id, 0) + quantity

    def add_server(self, role: NodeRole | str, quantity: int = 1):
        role = NodeRole(role)
        _require_positive_quantity(quantity)
        self.servers[role.value] = self.servers.get(role.value, 0) + quantity

    def add_cable(self, cable_id: str, quantity: int = 1):
        _require_positive_quantity(quantity)
        self.cables[cable_id] = self.cables.get(cable_id, 0) + quantity

    def require_cable(self, cable_id: str, quantity: int = 1):
        if self.cables.get(cable_id, 0) < quantity:
            raise ValueError(f"No purchased cable available: {cable_id}")

    def consume_cable(self, cable_id: str, quantity: int = 1):
        self.require_cable(cable_id, quantity)
        self.cables[cable_id] -= quantity

    def first_available_cable(self):
        for cable_id, quantity in sorted(self.cables.items()):
            if quantity > 0:
                return cable_id
        raise ValueError("No purchased cable available")

    def require_server(self, role: NodeRole | str, quantity: int = 1):
        role = NodeRole(role)
        if self.servers.get(role.value, 0) < quantity:
            raise ValueError(f"No purchased server available for {role.value}")

    def consume_server(self, role: NodeRole | str, quantity: int = 1):
        self.require_server(role, quantity)
        role = NodeRole(role)
        self.servers[role.value] -= quantity

    def require_parts_for(self, request: BuildRequest):
        required = _required_parts(request)
        for kind, counts in required.items():
            for part_id, quantity in counts.items():
                if self.parts.get(kind, {}).get(part_id, 0) < quantity:
                    raise ValueError(
                        f"Missing purchased part: {kind} {part_id} x{quantity}"
                    )

    def consume_parts_for(self, request: BuildRequest):
        self.require_parts_for(request)
        for kind, counts in _required_parts(request).items():
            for part_id, quantity in counts.items():
                self.parts[kind][part_id] -= quantity

    def part_quantity(self, kind: str, part_id: str):
        kind = normalize_part_kind(kind)
        return self.parts.get(kind, {}).get(part_id, 0)

    def to_dict(self):
        return {
            "parts": self.parts,
            "servers": self.servers,
            "cables": self.cables,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]):
        return cls(
            parts={
                str(kind): {
                    str(part_id): int(quantity) for part_id, quantity in parts.items()
                }
                for kind, parts in value.get("parts", {}).items()
            },
            servers={
                str(role): int(quantity)
                for role, quantity in value.get("servers", {}).items()
            },
            cables={
                str(cable_id): int(quantity)
                for cable_id, quantity in value.get("cables", {}).items()
            },
        )


class ComputeTycoonGame:
    def __init__(
        self,
        catalog: PartsCatalog = DEFAULT_PARTS_CATALOG,
        workloads: WorkloadCatalog = DEFAULT_WORKLOADS,
        event_log: EventLog | None = None,
        save_path: str | Path | None = DEFAULT_SAVE_PATH,
        load_save: bool = True,
    ):
        self.catalog = catalog
        self.workloads = workloads
        self.event_log = event_log or EventLog()
        self.save_path = Path(save_path) if save_path is not None else None
        self._state_lock = RLock()
        self._state_version = 0
        self.inventory = Inventory()
        self._nodes: dict[str, Node] = {}
        self._build_requests: dict[str, BuildRequest] = {}
        self._work_ids = count(1)
        self.topology = NetworkTopology(nodes=self._nodes)
        if load_save and self.save_path is not None and self.save_path.exists():
            self._load()
        self._autosave_worker = (
            AutosaveWorker(self, self.save_path) if self.save_path is not None else None
        )
        if self._autosave_worker is not None:
            self._autosave_worker.start()

    @property
    def nodes(self):
        with self._state_lock:
            return self._nodes.copy()

    @property
    def state_version(self):
        with self._state_lock:
            return self._state_version

    def add_node(self, node_id: str, role: NodeRole | str):
        with self._state_lock:
            role = NodeRole(role)
            self.inventory.require_server(role)
            node = self._build_node(self.default_build_request(node_id, role))
            self.inventory.consume_server(role)
            self.event_log.record(
                node.id,
                f"Purchased server placed as {role.value}",
            )
            self._mark_changed()
            return node

    def create_node(self, node_id: str, role: NodeRole | str):
        return self.add_node(node_id, role)

    def default_build_request(self, node_id: str, role: NodeRole | str):
        role = NodeRole(role)
        defaults = DEFAULT_NODE_PARTS.get(role)
        if defaults is None:
            raise ValueError(f"No default build profile for role: {role.value}")
        return BuildRequest(
            node_id=node_id,
            role=role,
            name=_default_name(node_id, role),
            motherboard=defaults["motherboard"],
            processors=defaults["processors"],
            memory_modules=defaults["memory_modules"],
            storage_devices=defaults["storage_devices"],
            network_interfaces=defaults["expansion_network_interfaces"],
            workers=defaults.get("workers"),
        )

    def build_node(self, request: BuildRequest):
        with self._state_lock:
            self.inventory.require_parts_for(request)
            node = self._build_node(request)
            self.inventory.consume_parts_for(request)
            self.event_log.record(node.id, f"Node assembled as {node.role.value}")
            self._mark_changed()
            return node

    def set_node_role(self, node_id: str, role: NodeRole | str):
        with self._state_lock:
            role = NodeRole(role)
            node = self._node(node_id)
            request = self._build_requests[node_id]
            replacement = replace(request, role=role)

            if not node.set_role(role):
                return node

            self._build_requests[node_id] = replacement
            self.event_log.record(node.id, f"Node role set to {role.value}")
            self._mark_changed()
            return node

    def rename_server(self, server_id: str, name: str):
        name = name.strip()
        if not name:
            raise ValueError("server name must not be empty")

        with self._state_lock:
            server = self._node(server_id)
            server.name = name
            request = self._build_requests[server_id]
            self._build_requests[server_id] = BuildRequest(
                node_id=request.node_id,
                role=request.role,
                name=name,
                motherboard=request.motherboard,
                processors=request.processors,
                memory_modules=request.memory_modules,
                storage_devices=request.storage_devices,
                gpus=request.gpus,
                network_interfaces=request.network_interfaces,
                workers=request.workers,
            )
            self.event_log.record(server.id, f"Server renamed to {name}")
            self._mark_changed()
            return server

    def validate_build_request(self, request: BuildRequest):
        with self._state_lock:
            if request.node_id in self._nodes:
                raise ValueError(f"Node already exists: {request.node_id}")
            self.inventory.require_parts_for(request)
            NodeBuilder(self.catalog).validate(_assembly_from_request(request))

    def _build_node(self, request: BuildRequest):
        if request.node_id in self._nodes:
            raise ValueError(f"Node already exists: {request.node_id}")

        request = _request_with_default_name(request)
        assembly = _assembly_from_request(request)
        node = NodeBuilder(self.catalog, event_log=self.event_log).build(
            assembly,
        )
        self._nodes[node.id] = node
        self._build_requests[node.id] = request
        self._refresh_topology()
        return node

    def buy_part(self, kind: str, part_id: str, quantity: int = 1):
        with self._state_lock:
            kind = normalize_part_kind(kind)
            self._require_catalog_part(kind, part_id)
            self.inventory.add_part(kind, part_id, quantity)
            self._mark_changed()

    def buy_server(self, role: NodeRole | str, quantity: int = 1):
        with self._state_lock:
            role = NodeRole(role)
            if role not in DEFAULT_NODE_PARTS:
                raise ValueError(f"No prebuilt server in shop for {role.value}")
            self.inventory.add_server(role, quantity)
            self._mark_changed()

    def buy_cable(self, cable_id: str, quantity: int = 1):
        with self._state_lock:
            self._require_catalog_cable(cable_id)
            self.inventory.add_cable(cable_id, quantity)
            self._mark_changed()

    def connect(self, left: str, right: str, cable_id: str | None = None):
        with self._state_lock:
            cable_id = cable_id or self.inventory.first_available_cable()
            self._require_catalog_cable(cable_id)
            self.inventory.require_cable(cable_id)
            self.topology = self.topology.add_cable(
                NetworkPortRef.parse(left),
                NetworkPortRef.parse(right),
                cable_id=cable_id,
            )
            self.inventory.consume_cable(cable_id)
            self._mark_changed()

    def disconnect(self, port: str):
        with self._state_lock:
            self.topology, cable = self.topology.remove_cable(
                NetworkPortRef.parse(port),
            )
            self.inventory.add_cable(cable.cable_id)
            self._mark_changed()
            return cable

    def add_address(self, port: str, cidr: str):
        with self._state_lock:
            self.topology = self.topology.add_address(
                InterfaceAddress.create(NetworkPortRef.parse(port), cidr),
            )
            self._mark_changed()

    def add_route(
        self,
        node_id: str,
        destination: str,
        gateway: str | None = None,
        interface: str | None = None,
    ):
        with self._state_lock:
            self.topology = self.topology.add_route(
                RouteEntry.create(
                    node_id=node_id,
                    destination=destination,
                    gateway=gateway,
                    interface=interface,
                )
            )
            self._mark_changed()

    def ping(self, source_node_id: str, target_node_id: str):
        return self.topology.ping(source_node_id, target_node_id)

    def traceroute(self, source_node_id: str, target_node_id: str):
        return self.topology.resolve(source_node_id, target_node_id)

    def run_workload(self, kind: str, jobs: int = 1):
        if jobs < 1:
            raise ValueError("jobs must be greater than 0")

        results = []
        for _ in range(jobs):
            work_id = next(self._work_ids)
            work = self.workloads.create_work(work_id, kind=kind)
            results.append(self._run_work(work))
        return tuple(results)

    def node_summary(self):
        return tuple(
            f"{node.id}\t{node.role.value}\t{node.name}\t"
            f"ports={','.join(self.topology.port_names(node.id)) or '-'}"
            for node in self._nodes.values()
        )

    def server_summary(self):
        return self.node_summary()

    def link_summary(self):
        return tuple(
            f"{cable.a} <-> {cable.b}\t{cable.cable_id}"
            for cable in self.topology.cables
        )

    def cable_summary(self):
        return self.link_summary()

    def address_summary(self, node_id: str | None = None):
        addresses = self.topology.addresses
        if node_id is not None:
            addresses = tuple(
                address for address in addresses if address.port.node_id == node_id
            )
        return tuple(f"{address.port}\t{address.interface}" for address in addresses)

    def route_summary(self, node_id: str | None = None):
        routes = self.topology.routes
        if node_id is not None:
            routes = tuple(route for route in routes if route.node_id == node_id)
        return tuple(_format_route(route) for route in routes)

    def interface_summary(self, node_id: str):
        node = self._node(node_id)
        names = self.topology.port_names(node_id)
        addresses = {
            address.port.name: address.interface
            for address in self.topology.addresses_for(node_id)
        }
        lines = []
        for name in names:
            address = addresses.get(name)
            lines.append(
                f"{name}\t{node.role.value}\t"
                f"{address if address is not None else 'unassigned'}"
            )
        return tuple(lines)

    def snapshot_text(self, node_id: str):
        return HardwareMonitor.format_snapshot(self._node(node_id).snapshot())

    def logs(self, node_id: str | None = None, limit: int | None = 50):
        return tuple(
            entry.format()
            for entry in self.event_log.entries(node_id=node_id, limit=limit)
        )

    def shop_summary(self, kind: str | None = None):
        lines = []
        if kind is None or kind in {"server", "servers"}:
            lines.append("[servers]")
            lines.extend(
                f"{role.value}\tprebuilt {role.value}" for role in DEFAULT_NODE_PARTS
            )
            if kind in {"server", "servers"}:
                return tuple(lines)

        if kind is None or kind in {"cable", "cables"}:
            lines.append("[cables]")
            lines.extend(
                f"{cable_id}\tbandwidth={cable.bandwidth}\t{cable.name}"
                for cable_id, cable in self.catalog.cables.items()
            )
            if kind in {"cable", "cables"}:
                return tuple(lines)

        part_kind = normalize_part_kind(kind) if kind is not None else None
        groups = _catalog_groups(self.catalog)
        for group_name, parts in groups.items():
            if part_kind is not None and group_name != part_kind:
                continue
            lines.append(f"[{group_name}]")
            lines.extend(
                f"{part_id}\t{getattr(part, 'name', type(part).__name__)}"
                for part_id, part in parts.items()
            )
        return tuple(lines)

    def inventory_summary(self):
        lines = ["[servers]"]
        lines.extend(
            f"{role}\t{quantity}"
            for role, quantity in sorted(self.inventory.servers.items())
            if quantity > 0
        )
        lines.append("[cables]")
        lines.extend(
            f"{cable_id}\t{quantity}"
            for cable_id, quantity in sorted(self.inventory.cables.items())
            if quantity > 0
        )
        lines.append("[parts]")
        for kind, parts in sorted(self.inventory.parts.items()):
            for part_id, quantity in sorted(parts.items()):
                if quantity > 0:
                    lines.append(f"{kind}\t{part_id}\t{quantity}")
        return tuple(lines)

    def stop_all(self):
        if self._autosave_worker is not None:
            self._autosave_worker.stop()
            self._autosave_worker = None
        for node in self._nodes.values():
            node.wait_all()
        for node in self._nodes.values():
            node.stop()

    def _mark_changed(self):
        self._state_version += 1

    def save_snapshot(self):
        with self._state_lock:
            return self._state_version, self.to_save_data()

    def to_save_data(self):
        return {
            "version": SAVE_VERSION,
            "inventory": self.inventory.to_dict(),
            "nodes": [
                _build_request_to_dict(request)
                for request in self._build_requests.values()
            ],
            "network": {
                "links": [
                    {
                        "a": str(cable.a),
                        "b": str(cable.b),
                        "cable": cable.cable_id,
                    }
                    for cable in self.topology.cables
                ],
                "addresses": [
                    {
                        "port": str(address.port),
                        "address": str(address.interface),
                    }
                    for address in self.topology.addresses
                ],
                "routes": [
                    {
                        "node": route.node_id,
                        "destination": str(route.destination),
                        "gateway": (
                            str(route.gateway) if route.gateway is not None else None
                        ),
                        "interface": route.interface,
                    }
                    for route in self.topology.routes
                ],
            },
        }

    def _run_work(self, work):
        if not hasattr(work, "steps"):
            first_node_id = next(iter(self._nodes))
            self._node(first_node_id).put(work)
            self._node(first_node_id).wait_all()
            return f"{work.kind} ran on {first_node_id}"

        previous_node_id = None
        routes = []
        for step in work.steps:
            self._node(step.node_id)
            if previous_node_id is not None:
                route = self.topology.resolve(previous_node_id, step.node_id)
                routes.append(route.describe())
                self.event_log.record(
                    previous_node_id,
                    f"Network route to {step.node_id}: {route.describe()}",
                )
                self.event_log.record(
                    step.node_id,
                    f"Network route from {previous_node_id}: {route.describe()}",
                )

            node = self._node(step.node_id)
            node.put(step.work)
            node.wait_all()
            previous_node_id = step.node_id

        route_text = "; ".join(routes) if routes else "local"
        return f"{work.kind} completed routes=[{route_text}]"

    def _refresh_topology(self):
        self.topology = NetworkTopology(
            nodes=self._nodes,
            cables=self.topology.cables,
            addresses=self.topology.addresses,
            routes=self.topology.routes,
        )

    def _load(self):
        try:
            with self.save_path.open(encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise SaveDataError("Invalid save data") from error

        try:
            if "version" not in data:
                raise SaveDataError("Save data version is missing")
            version = data["version"]
        except TypeError as error:
            raise SaveDataError(f"Invalid save data: {error}") from error
        if type(version) is not int or version != SAVE_VERSION:
            raise SaveDataError(f"Unsupported save version: {version!r}")

        staged_nodes: dict[str, Node] = {}
        try:
            staged_inventory = Inventory.from_dict(data.get("inventory", {}))
            staged_build_requests: dict[str, BuildRequest] = {}
            for node_config in data.get("nodes", []):
                request = _build_request_from_dict(node_config)
                if request.node_id in staged_nodes:
                    raise ValueError(f"Node already exists: {request.node_id}")
                request = _request_with_default_name(request)
                node = NodeBuilder(self.catalog, event_log=self.event_log).build(
                    _assembly_from_request(request)
                )
                staged_nodes[node.id] = node
                staged_build_requests[node.id] = request

            staged_topology = NetworkTopology(nodes=staged_nodes)
            network = data.get("network", {})
            links = network.get("links", network.get("cables", []))
            for cable in links:
                staged_topology = staged_topology.add_cable(
                    NetworkPortRef.parse(cable["a"]),
                    NetworkPortRef.parse(cable["b"]),
                    cable_id=str(cable.get("cable", DEFAULT_CABLE_ID)),
                )
            for address in network.get("addresses", []):
                staged_topology = staged_topology.add_address(
                    InterfaceAddress.create(
                        NetworkPortRef.parse(address["port"]),
                        address["address"],
                    )
                )
            for route in network.get("routes", []):
                staged_topology = staged_topology.add_route(
                    RouteEntry.create(
                        node_id=route["node"],
                        destination=route["destination"],
                        gateway=route.get("gateway"),
                        interface=route.get("interface"),
                    )
                )
        except BaseException as error:
            for node in staged_nodes.values():
                try:
                    node.stop()
                except BaseException:
                    pass
            if isinstance(error, SaveDataError):
                raise
            if isinstance(error, (AttributeError, TypeError, KeyError, ValueError)):
                raise SaveDataError(f"Invalid save data: {error}") from error
            raise

        with self._state_lock:
            self.inventory = staged_inventory
            self._nodes = staged_nodes
            self._build_requests = staged_build_requests
            self.topology = staged_topology
            self._state_version = 0

    def _node(self, node_id: str):
        try:
            return self._nodes[node_id]
        except KeyError as error:
            raise KeyError(f"Unknown node: {node_id}") from error

    def _require_catalog_part(self, kind: str, part_id: str):
        parts = _catalog_groups(self.catalog)[kind]
        if part_id not in parts:
            raise KeyError(f"Unknown {kind} part: {part_id}")

    def _require_catalog_cable(self, cable_id: str):
        if cable_id not in self.catalog.cables:
            raise KeyError(f"Unknown cable: {cable_id}")


def _default_name(node_id: str, role: NodeRole):
    if role == NodeRole.UNASSIGNED:
        return f"Server {node_id}"
    return f"{role.value.replace('_', ' ').title()} {node_id}"


def _request_with_default_name(request: BuildRequest):
    if request.name is not None:
        return request
    return BuildRequest(
        node_id=request.node_id,
        role=request.role,
        name=_default_name(request.node_id, request.role),
        motherboard=request.motherboard,
        processors=request.processors,
        memory_modules=request.memory_modules,
        storage_devices=request.storage_devices,
        gpus=request.gpus,
        network_interfaces=request.network_interfaces,
        workers=request.workers,
    )


def _format_route(route: RouteEntry):
    gateway = f"via {route.gateway}" if route.gateway is not None else "connected"
    interface = f" dev {route.interface}" if route.interface is not None else ""
    return f"{route.node_id}\t{route.destination}\t{gateway}{interface}"


def normalize_part_kind(kind: str):
    try:
        return PART_KIND_ALIASES[kind]
    except KeyError as error:
        raise KeyError(f"Unknown part kind: {kind}") from error


def _catalog_groups(catalog: PartsCatalog):
    return {
        "motherboards": catalog.motherboards,
        "processors": catalog.processors,
        "memory": catalog.memory,
        "storage": catalog.storage,
        "gpus": catalog.gpus,
        "network_interfaces": catalog.network_interfaces,
    }


def _require_positive_quantity(quantity: int):
    if quantity < 1:
        raise ValueError("quantity must be greater than 0")


def _required_parts(request: BuildRequest):
    required: dict[str, dict[str, int]] = {}
    if request.motherboard is not None:
        required.setdefault("motherboards", {})[request.motherboard] = 1

    for kind, field_names in REQUEST_PART_FIELDS.items():
        if kind == "motherboards":
            continue
        for field_name in field_names:
            for part_id in getattr(request, field_name):
                bucket = required.setdefault(kind, {})
                bucket[part_id] = bucket.get(part_id, 0) + 1
    return required


def _assembly_from_request(request: BuildRequest):
    if request.motherboard is None:
        raise ValueError("motherboard must be selected")
    return NodeAssemblyConfig(
        id=request.node_id,
        name=request.name or _default_name(request.node_id, request.role),
        role=request.role,
        motherboard=request.motherboard,
        processors=request.processors,
        memory_modules=request.memory_modules,
        storage_devices=request.storage_devices,
        gpus=request.gpus,
        expansion_network_interfaces=request.network_interfaces,
        workers=request.workers,
    )


def _build_request_to_dict(request: BuildRequest):
    return {
        "id": request.node_id,
        "role": request.role.value,
        "name": request.name,
        "motherboard": request.motherboard,
        "processors": list(request.processors),
        "memory_modules": list(request.memory_modules),
        "storage_devices": list(request.storage_devices),
        "gpus": list(request.gpus),
        "network_interfaces": list(request.network_interfaces),
        "workers": request.workers,
    }


def _build_request_from_dict(value: dict[str, object]):
    return BuildRequest(
        node_id=str(value["id"]),
        role=NodeRole(str(value["role"])),
        name=(str(value["name"]) if value.get("name") is not None else None),
        motherboard=(
            str(value["motherboard"]) if value.get("motherboard") is not None else None
        ),
        processors=_string_tuple(value.get("processors", [])),
        memory_modules=_string_tuple(value.get("memory_modules", [])),
        storage_devices=_string_tuple(value.get("storage_devices", [])),
        gpus=_string_tuple(value.get("gpus", [])),
        network_interfaces=_string_tuple(value.get("network_interfaces", [])),
        workers=(int(value["workers"]) if value.get("workers") is not None else None),
    )


def _string_tuple(value: object):
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)
