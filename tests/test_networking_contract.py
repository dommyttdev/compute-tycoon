from __future__ import annotations

import pytest

from hardware_sim import (
    InterfaceAddress,
    MemoryModule,
    NetworkInterface,
    NetworkPortRef,
    NetworkTopology,
    Node,
    NodeDevices,
    NodeRole,
    Processor,
    RouteEntry,
    StorageDevice,
)


def _node(
    node_id: str, role: NodeRole = NodeRole.APPLICATION_SERVER, nics: int = 1
) -> Node:
    return Node(
        id=node_id,
        name=node_id,
        role=role,
        devices=NodeDevices(
            cpu=Processor(1, 1),
            memory=MemoryModule(1),
            storage=StorageDevice(1, 1, 1),
            network_interfaces=tuple(NetworkInterface(1, 0, 1, 1) for _ in range(nics)),
        ),
        executor=object(),
        workers=1,
    )


@pytest.fixture
def nodes() -> dict[str, Node]:
    values = {
        "source": _node("source"),
        "target": _node("target"),
        "switch": _node("switch", NodeRole.NETWORK_SWITCH, 4),
        "router-a": _node("router-a", NodeRole.ROUTER, 2),
        "router-b": _node("router-b", NodeRole.ROUTER, 2),
    }
    yield values
    for node in values.values():
        node.stop()


def _port(value: str) -> NetworkPortRef:
    return NetworkPortRef.parse(value)


def test_port_address_and_route_factories_accept_ipv4_values() -> None:
    port = _port("source:lan0")
    address = InterfaceAddress.create(port, "192.0.2.10/24")
    route = RouteEntry.create("source", "198.51.100.7/24", "192.0.2.1", "lan0")

    assert str(port) == "source:lan0"
    assert str(address.ip) == "192.0.2.10"
    assert str(address.network) == "192.0.2.0/24"
    assert str(route.destination) == "198.51.100.0/24"
    assert str(route.gateway) == "192.0.2.1"


@pytest.mark.parametrize("value", ["source", ":lan0", "source:"])
def test_port_parser_rejects_incomplete_references(value: str) -> None:
    with pytest.raises(ValueError, match="port"):
        NetworkPortRef.parse(value)


def test_address_and_route_factories_reject_ipv6() -> None:
    with pytest.raises(ValueError, match="only IPv4"):
        InterfaceAddress.create(_port("source:lan0"), "2001:db8::1/64")
    with pytest.raises(ValueError, match="only IPv4"):
        RouteEntry.create("source", "2001:db8::/64")
    with pytest.raises(ValueError, match="only IPv4"):
        RouteEntry.create("source", "0.0.0.0/0", "2001:db8::1")


def test_cable_changes_return_new_topologies_and_enforce_port_occupancy(
    nodes: dict[str, Node],
) -> None:
    original = NetworkTopology(nodes)
    connected = original.add_cable(_port("source:lan0"), _port("switch:port1"))

    assert original.cables == ()
    assert len(connected.cables) == 1
    with pytest.raises(ValueError, match="already connected"):
        connected.add_cable(_port("source:lan0"), _port("switch:port2"))
    assert len(connected.cables) == 1

    removed, cable = connected.remove_cable(_port("switch:port1"))
    assert removed.cables == ()
    assert connected.cables == (cable,)


def test_address_and_route_changes_replace_values_without_mutating_source(
    nodes: dict[str, Node],
) -> None:
    original = NetworkTopology(nodes)
    first_address = InterfaceAddress.create(_port("source:lan0"), "192.0.2.10/24")
    addressed = original.add_address(first_address)
    replaced = addressed.add_address(
        InterfaceAddress.create(_port("source:lan0"), "192.0.2.11/24")
    )
    first_route = RouteEntry.create("source", "0.0.0.0/0", "192.0.2.1")
    routed = replaced.add_route(first_route)
    rerouted = routed.add_route(RouteEntry.create("source", "0.0.0.0/0", "192.0.2.2"))

    assert original.addresses == original.routes == ()
    assert addressed.addresses == (first_address,)
    assert str(replaced.primary_address("source").ip) == "192.0.2.11"
    assert routed.routes == (first_route,)
    assert str(rerouted.routes_for("source")[0].gateway) == "192.0.2.2"


def _direct_topology(nodes: dict[str, Node]) -> NetworkTopology:
    topology = NetworkTopology(nodes)
    for a, b in (
        ("source:lan0", "switch:port1"),
        ("target:lan0", "switch:port2"),
    ):
        topology = topology.add_cable(_port(a), _port(b))
    for port, cidr in (
        ("source:lan0", "192.0.2.10/24"),
        ("target:lan0", "192.0.2.20/24"),
    ):
        topology = topology.add_address(InterfaceAddress.create(_port(port), cidr))
    return topology


def test_resolve_finds_direct_path_without_mutating_topology(
    nodes: dict[str, Node],
) -> None:
    topology = _direct_topology(nodes)
    state = (topology.cables, topology.addresses, topology.routes)

    resolution = topology.resolve("source", "target")

    assert resolution.hops == ("source", "switch", "target")
    assert resolution.describe() == "source -> switch -> target"
    assert (topology.cables, topology.addresses, topology.routes) == state


def _routed_topology(nodes: dict[str, Node]) -> NetworkTopology:
    topology = NetworkTopology(nodes)
    for a, b in (
        ("source:lan0", "router-a:lan0"),
        ("router-a:lan1", "target:lan0"),
    ):
        topology = topology.add_cable(_port(a), _port(b))
    for port, cidr in (
        ("source:lan0", "192.0.2.10/24"),
        ("router-a:lan0", "192.0.2.1/24"),
        ("router-a:lan1", "198.51.100.1/24"),
        ("target:lan0", "198.51.100.10/24"),
    ):
        topology = topology.add_address(InterfaceAddress.create(_port(port), cidr))
    return topology.add_route(
        RouteEntry.create("source", "198.51.100.0/24", "192.0.2.1")
    )


def test_resolve_follows_gateway_to_routed_network(nodes: dict[str, Node]) -> None:
    topology = _routed_topology(nodes)

    assert topology.resolve("source", "target").hops == (
        "source",
        "router-a",
        "target",
    )


def test_longest_prefix_route_wins(nodes: dict[str, Node]) -> None:
    topology = _routed_topology(nodes).add_address(
        InterfaceAddress.create(_port("router-b:lan0"), "192.0.2.2/24")
    )
    topology = topology.add_cable(_port("router-b:lan0"), _port("switch:port1"))
    # Put source and both gateways on one L2 network.
    topology, _ = topology.remove_cable(_port("source:lan0"))
    topology = topology.add_cable(_port("source:lan0"), _port("switch:port2"))
    topology = topology.add_cable(_port("router-a:lan0"), _port("switch:port3"))
    topology = topology.add_route(
        RouteEntry.create("source", "198.51.0.0/16", "192.0.2.2")
    )

    assert topology.resolve("source", "target").hops == (
        "source",
        "switch",
        "router-a",
        "target",
    )


def test_unknown_gateway_and_no_route_fail_without_mutating_topology(
    nodes: dict[str, Node],
) -> None:
    direct = _direct_topology(nodes)
    isolated = NetworkTopology(nodes, addresses=direct.addresses)
    no_route_state = (isolated.cables, isolated.addresses, isolated.routes)
    with pytest.raises(ValueError, match="No route"):
        isolated.resolve("source", "target")
    assert (isolated.cables, isolated.addresses, isolated.routes) == no_route_state

    routed = isolated.add_route(
        RouteEntry.create("source", "192.0.2.0/24", "192.0.2.254")
    )
    routed = routed.add_cable(_port("source:lan0"), _port("switch:port1"))
    state = (routed.cables, routed.addresses, routed.routes)
    with pytest.raises(ValueError, match="Unknown gateway"):
        routed.resolve("source", "target")
    assert (routed.cables, routed.addresses, routed.routes) == state


def test_routing_loop_fails_without_mutating_topology(nodes: dict[str, Node]) -> None:
    topology = NetworkTopology(nodes)
    for a, b in (
        ("source:lan0", "router-a:lan0"),
        ("router-a:lan1", "router-b:lan0"),
    ):
        topology = topology.add_cable(_port(a), _port(b))
    for port, cidr in (
        ("source:lan0", "192.0.2.10/24"),
        ("router-a:lan0", "192.0.2.1/24"),
        ("router-a:lan1", "203.0.113.1/24"),
        ("router-b:lan0", "203.0.113.2/24"),
        ("target:lan0", "198.51.100.10/24"),
    ):
        topology = topology.add_address(InterfaceAddress.create(_port(port), cidr))
    for node_id, gateway in (
        ("source", "192.0.2.1"),
        ("router-a", "203.0.113.2"),
        ("router-b", "203.0.113.1"),
    ):
        topology = topology.add_route(
            RouteEntry.create(node_id, "198.51.100.0/24", gateway)
        )
    state = (topology.cables, topology.addresses, topology.routes)

    with pytest.raises(ValueError, match="Routing loop"):
        topology.resolve("source", "target")
    assert (topology.cables, topology.addresses, topology.routes) == state
