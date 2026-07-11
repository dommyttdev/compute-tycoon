from collections import deque
from dataclasses import dataclass
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    ip_address,
    ip_interface,
    ip_network,
)
from types import MappingProxyType
from typing import Mapping

from hardware_sim.node import Node, NodeRole


@dataclass(frozen=True, order=True)
class NetworkPortRef:
    node_id: str
    name: str

    @classmethod
    def parse(cls, value: str):
        if ":" not in value:
            raise ValueError("port must be formatted as node:port")
        node_id, name = value.split(":", 1)
        if not node_id or not name:
            raise ValueError("port must include both node and port")
        return cls(node_id=node_id, name=name)

    def __str__(self):
        return f"{self.node_id}:{self.name}"


@dataclass(frozen=True)
class Cable:
    a: NetworkPortRef
    b: NetworkPortRef
    cable_id: str = "cable.cat6.patch"

    def other(self, port: NetworkPortRef):
        if port == self.a:
            return self.b
        if port == self.b:
            return self.a
        raise ValueError(f"{port} is not connected to this cable")


@dataclass(frozen=True)
class InterfaceAddress:
    port: NetworkPortRef
    interface: IPv4Interface

    @classmethod
    def create(cls, port: NetworkPortRef, cidr: str):
        interface = ip_interface(cidr)
        if interface.version != 4:
            raise ValueError("only IPv4 addresses are supported")
        return cls(port=port, interface=interface)

    @property
    def ip(self):
        return self.interface.ip

    @property
    def network(self):
        return self.interface.network


@dataclass(frozen=True)
class RouteEntry:
    node_id: str
    destination: IPv4Network
    gateway: IPv4Address | None = None
    interface: str | None = None

    @classmethod
    def create(
        cls,
        node_id: str,
        destination: str,
        gateway: str | None = None,
        interface: str | None = None,
    ):
        network = ip_network(destination, strict=False)
        if network.version != 4:
            raise ValueError("only IPv4 routes are supported")
        return cls(
            node_id=node_id,
            destination=network,
            gateway=ip_address(gateway) if gateway is not None else None,
            interface=interface,
        )

    def matches(self, address: IPv4Address):
        return address in self.destination


@dataclass(frozen=True)
class RouteResolution:
    source: str
    target: str
    target_ip: IPv4Address
    hops: tuple[str, ...]

    def describe(self):
        return " -> ".join(self.hops)


class NetworkTopology:
    def __init__(
        self,
        nodes: Mapping[str, Node],
        cables: tuple[Cable, ...] = (),
        addresses: tuple[InterfaceAddress, ...] = (),
        routes: tuple[RouteEntry, ...] = (),
    ):
        self.nodes = MappingProxyType(dict(nodes))
        self.cables = tuple(cables)
        self.addresses = tuple(addresses)
        self.routes = tuple(routes)

    def port_names(self, node_id: str):
        node = self._node(node_id)
        if node.role == NodeRole.NETWORK_SWITCH:
            total_ports = sum(
                network_interface.ports for network_interface in node.network_interfaces
            )
            return tuple(f"port{index}" for index in range(1, total_ports + 1))
        return tuple(f"lan{index}" for index, _ in enumerate(node.network_interfaces))

    def add_cable(
        self,
        a: NetworkPortRef,
        b: NetworkPortRef,
        cable_id: str = "cable.cat6.patch",
    ):
        self._require_port(a)
        self._require_port(b)
        if a == b:
            raise ValueError("cannot connect a port to itself")
        if self._cable_for(a) is not None:
            raise ValueError(f"{a} is already connected")
        if self._cable_for(b) is not None:
            raise ValueError(f"{b} is already connected")
        return self._copy(cables=(*self.cables, Cable(a=a, b=b, cable_id=cable_id)))

    def remove_cable(self, port: NetworkPortRef):
        cable = self._cable_for(port)
        if cable is None:
            raise ValueError(f"{port} is not connected")
        return (
            self._copy(
                cables=tuple(current for current in self.cables if current != cable)
            ),
            cable,
        )

    def add_address(self, address: InterfaceAddress):
        self._require_port(address.port)
        remaining = tuple(
            current for current in self.addresses if current.port != address.port
        )
        return self._copy(addresses=(*remaining, address))

    def add_route(self, route: RouteEntry):
        self._node(route.node_id)
        if route.interface is not None:
            self._require_port(
                NetworkPortRef(node_id=route.node_id, name=route.interface)
            )
        remaining = tuple(
            current
            for current in self.routes
            if not (
                current.node_id == route.node_id
                and current.destination == route.destination
            )
        )
        return self._copy(routes=(*remaining, route))

    def resolve(self, source_node_id: str, target_node_id: str):
        self._node(source_node_id)
        self._node(target_node_id)
        target = self.primary_address(target_node_id)
        target_ip = target.ip
        hops = [source_node_id]
        current_node_id = source_node_id
        visited = {source_node_id}

        for _ in range(len(self.nodes) + 1):
            direct_path = self._direct_path(current_node_id, target)
            if direct_path is not None:
                _append_unique(hops, direct_path)
                return RouteResolution(
                    source=source_node_id,
                    target=target_node_id,
                    target_ip=target_ip,
                    hops=tuple(hops),
                )

            route = self._best_route(current_node_id, target_ip)
            if route is None or route.gateway is None:
                raise ValueError(f"No route from {current_node_id} to {target_ip}")

            gateway = self._address_by_ip(route.gateway)
            gateway_path = self._path_to_gateway(current_node_id, gateway)
            if gateway_path is None:
                raise ValueError(
                    f"Gateway {route.gateway} is not reachable from {current_node_id}"
                )

            _append_unique(hops, gateway_path)
            current_node_id = gateway.port.node_id
            if current_node_id in visited:
                raise ValueError(f"Routing loop at {current_node_id}")
            visited.add(current_node_id)

        raise ValueError(f"No route from {source_node_id} to {target_ip}")

    def ping(self, source_node_id: str, target_node_id: str):
        return self.resolve(source_node_id, target_node_id)

    def primary_address(self, node_id: str):
        for address in self.addresses:
            if address.port.node_id == node_id:
                return address
        raise ValueError(f"{node_id} has no IP address")

    def addresses_for(self, node_id: str):
        return tuple(
            address for address in self.addresses if address.port.node_id == node_id
        )

    def routes_for(self, node_id: str):
        return tuple(route for route in self.routes if route.node_id == node_id)

    def _copy(
        self,
        cables: tuple[Cable, ...] | None = None,
        addresses: tuple[InterfaceAddress, ...] | None = None,
        routes: tuple[RouteEntry, ...] | None = None,
    ):
        return NetworkTopology(
            nodes=self.nodes,
            cables=self.cables if cables is None else cables,
            addresses=self.addresses if addresses is None else addresses,
            routes=self.routes if routes is None else routes,
        )

    def _direct_path(
        self,
        source_node_id: str,
        target: InterfaceAddress,
    ):
        source_addresses = [
            address
            for address in self.addresses_for(source_node_id)
            if target.ip in address.network
        ]
        for source in source_addresses:
            path = self._l2_path(source.port, target.port)
            if path is not None:
                return path
        return None

    def _path_to_gateway(
        self,
        source_node_id: str,
        gateway: InterfaceAddress,
    ):
        source_addresses = [
            address
            for address in self.addresses_for(source_node_id)
            if gateway.ip in address.network
        ]
        for source in source_addresses:
            path = self._l2_path(source.port, gateway.port)
            if path is not None:
                return path
        return None

    def _l2_path(self, source: NetworkPortRef, target: NetworkPortRef):
        if source == target:
            return (source.node_id,)

        queue = deque([(source, (source,))])
        visited = {source}

        while queue:
            port, path = queue.popleft()
            for neighbor in self._l2_neighbors(port):
                if neighbor in visited:
                    continue
                next_path = (*path, neighbor)
                if neighbor == target:
                    return _node_path(next_path)
                visited.add(neighbor)
                queue.append((neighbor, next_path))

        return None

    def _l2_neighbors(self, port: NetworkPortRef):
        cable = self._cable_for(port)
        if cable is not None:
            yield cable.other(port)

        node = self._node(port.node_id)
        if node.role == NodeRole.NETWORK_SWITCH:
            for port_name in self.port_names(node.id):
                neighbor = NetworkPortRef(node_id=node.id, name=port_name)
                if neighbor != port:
                    yield neighbor

    def _best_route(self, node_id: str, target_ip: IPv4Address):
        candidates = [
            route for route in self.routes_for(node_id) if route.matches(target_ip)
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda route: route.destination.prefixlen)

    def _address_by_ip(self, address: IPv4Address):
        for current in self.addresses:
            if current.ip == address:
                return current
        raise ValueError(f"Unknown gateway address: {address}")

    def _node(self, node_id: str):
        try:
            return self.nodes[node_id]
        except KeyError as error:
            raise KeyError(f"Unknown node: {node_id}") from error

    def _require_port(self, port: NetworkPortRef):
        names = self.port_names(port.node_id)
        if port.name not in names:
            raise ValueError(
                f"Unknown port {port}; available: {', '.join(names) or '-'}"
            )

    def _cable_for(self, port: NetworkPortRef):
        for cable in self.cables:
            if cable.a == port or cable.b == port:
                return cable
        return None


def _node_path(ports: tuple[NetworkPortRef, ...]):
    nodes = []
    for port in ports:
        if not nodes or nodes[-1] != port.node_id:
            nodes.append(port.node_id)
    return tuple(nodes)


def _append_unique(target: list[str], values: tuple[str, ...]):
    for value in values:
        if not target or target[-1] != value:
            target.append(value)
