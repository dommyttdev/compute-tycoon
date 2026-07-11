from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from hardware_sim.assembly import NodeAssemblyConfig, NodeBuilder
from hardware_sim.catalog import PartsCatalog
from hardware_sim.node import Node
from hardware_sim.snapshots import NodeSnapshot
from hardware_sim.work import WorkInfo


@dataclass(frozen=True)
class NetworkLink:
    source_node: str
    target_node: str
    network_interface: str | None = None


@dataclass(frozen=True)
class InfrastructureConfig:
    nodes: tuple[NodeAssemblyConfig, ...]
    links: tuple[NetworkLink, ...] = ()


@dataclass(frozen=True)
class InfrastructureSnapshot:
    nodes: tuple[NodeSnapshot, ...]


class Infrastructure:
    def __init__(
        self,
        nodes: Mapping[str, Node],
        links: tuple[NetworkLink, ...] = (),
    ):
        if not nodes:
            raise ValueError("nodes must not be empty")

        self.nodes = MappingProxyType(dict(nodes))
        self.links = links

    def node(self, node_id: str):
        try:
            return self.nodes[node_id]
        except KeyError as error:
            raise KeyError(f"Unknown node: {node_id}") from error

    def put(self, node_id: str, work_info: WorkInfo):
        self.node(node_id).put(work_info)

    def snapshot(self):
        return InfrastructureSnapshot(
            nodes=tuple(node.snapshot() for node in self.nodes.values()),
        )

    def wait_all(self):
        for node in self.nodes.values():
            node.wait_all()

    def stop(self):
        for node in self.nodes.values():
            node.stop()


class InfrastructureBuilder:
    def __init__(self, catalog: PartsCatalog):
        self.catalog = catalog

    def build(self, config: InfrastructureConfig):
        node_builder = NodeBuilder(self.catalog)
        nodes = {
            node.id: node
            for node in (
                node_builder.build(node_config) for node_config in config.nodes
            )
        }
        return Infrastructure(nodes=nodes, links=config.links)
