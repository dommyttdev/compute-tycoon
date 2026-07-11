# Compute Tycoon domain context

## Purpose

Compute Tycoon simulates player-built compute infrastructure. A player acquires
parts or prebuilt servers, assembles nodes, assigns roles, configures an IPv4
network, and runs workloads whose resource demand consumes simulated device
capacity over time.

## System map

- `ComputeTycoonGame` is the application service and mutable aggregate root.
- `Inventory` owns purchased parts, prebuilt servers, and cables.
- `NodeBuilder` validates a `NodeAssemblyConfig` against the `PartsCatalog` and
  creates a `Node` with runtime devices.
- `Node` is a concurrent work queue with a `NodeRole` and role-specific executor.
- `NetworkTopology` is an immutable value graph for cables, IPv4 addresses, and
  routes.
- `WorkloadCatalog` creates sampled single-node or multi-step workloads.
- Device objects simulate CPU, memory, storage, GPU, and network contention.
- `AutosaveWorker` persists changed game state independently of commands.
- `TycoonShell` and its nested shells are presentation adapters only.

## Canonical vocabulary

| Term | Meaning |
| --- | --- |
| Game | The mutable player session coordinated by `ComputeTycoonGame`. |
| Inventory | Purchased assets not yet consumed by placement or assembly. |
| Part | A catalog configuration used to assemble a node. |
| Node | A built machine with devices, a role, and a work queue. |
| Role | The node's logical workload behavior; it selects a role executor. |
| Device | A runtime CPU, memory, storage, GPU, or network resource. |
| Assembly | The selected parts and worker count used to build a node. |
| Topology | Nodes plus physical cables, interface addresses, and routes. |
| Workload | A generated resource-demand scenario. |
| Work | One executable unit containing typed resource requirements. |
| Step | One node-local unit in a multi-node infrastructure workload. |
| Snapshot | An immutable observation of runtime device and queue state. |
| State version | A monotonic counter indicating save-relevant game mutation. |

Avoid using "server" as a synonym for every node: switches and routers are also
nodes. Use "link" only for the legacy static infrastructure model; the playable
game model uses cables between ports.

## Invariants

- Purchased assets must exist before they are consumed.
- Node IDs are unique within a game.
- Assemblies require at least one CPU, memory module, and storage device.
- Parts must fit motherboard sockets, slots, connectors, capacity, ECC, and PCIe
  constraints.
- One physical port can have at most one cable and one IPv4 address.
- Cross-node workload steps require a resolvable network route.
- Save-relevant mutations occur under the game lock and increment state version.
- A stopped node accepts no new work.

## Documentation ownership

- Human-facing design: `docs/architecture/` and `docs/design/`.
- Operational reference: `docs/reference/`.
- Development workflow: `docs/development/`.
- Architectural decisions: `docs/adr/` (content in Japanese).
