# CLI network design

## Goal

Compute Tycoon should treat networking as a player-operated system instead of
static JSON. The player assembles machines, buys LAN cables, plugs them into ports,
assigns IP/CIDR addresses, configures routes, checks reachability, and runs
workloads from a pseudo CLI.

## Module split

- `hardware_sim.game.ComputeTycoonGame`
  Owns the mutable game state: purchased inventory, built nodes, physical
  physical links, cable inventory, IP addresses, route tables, logs, workload
  execution, and autosave.

- `hardware_sim.networking.NetworkTopology`
  Resolves L2 reachability, IP routes, ping, and traceroute from physical
  physical links plus interface addresses. Switches are L2 devices. Routers forward
  between subnets through route entries.

- `hardware_sim.shell.TycoonShell`
  A thin `cmd.Cmd` adapter for player commands such as `shop`, `inventory`,
  `server name set`, `node add`, `build`, `link connect`, `ip addr add`,
  `route add`, `ping`, `traceroute`, `ssh`, and `run workload`.

- `hardware_sim.shell.ShopShell`
  A dedicated shop mode. Catalog browsing and purchasing can only be done
  inside this mode, so top-level gameplay commands do not also carry shop
  subcommands.

- `hardware_sim.shell.BuildShell`
  A pseudo assembly bench. It lets the player select a motherboard, add CPU,
  RAM, storage, GPU, and NIC parts from purchased inventory, validate the
  draft, and commit it as an unassigned physical server. Logical server roles
  are assigned later with `node role set`.

- `hardware_sim.shell.NodeShell`
  A pseudo SSH shell scoped to one node. It exposes node-local views such as
  `ip addr`, `ip route`, `show interfaces`, `top`, and `journalctl`.

- `hardware_sim.events.EventLog`
  Collects execution and device logs by node. Device classes accept a log sink,
  so the same hardware simulation can either print directly or write to the
  pseudo SSH log buffer.

- `hardware_sim.persistence.AutosaveWorker`
  Runs in a separate thread. It observes the game's state version, snapshots
  the game when the version changes, and writes the save JSON. Game commands
  only mutate game state and advance the version; they do not write JSON
  directly.

## Gameplay model

Physical connection and logical routing are separate.

1. The player starts with no purchased or built servers.
2. The player buys prebuilt servers/network devices or individual parts from
   `shop`.
3. The player can only place purchased prebuilt nodes with `node add`, or
   assemble unassigned physical servers with parts already in `inventory`.
4. The player can rename a completed physical server with `server name set`.
5. The player assigns a logical role with `node role set server role`.
6. The player buys cables with `shop` and connects ports with
   `link connect node:port node:port`.
7. The player assigns addresses with `ip addr add node:iface 192.168.10.10/24`.
8. The player adds routes with `route add node 0.0.0.0/0 via 192.168.10.1`.
9. `ping` and `traceroute` ask `NetworkTopology` whether the destination is
   reachable.
10. Workloads use the same topology before executing cross-node steps.
11. Every successful state-changing command advances the game state version.
12. The autosave thread notices the version change and updates JSON.

## Command examples

```text
compute-tycoon> shop
shop> list server
shop> buy server application_server
shop> buy server database_server
shop> buy server network_switch
shop> buy cable cable.cat6.patch 2
shop> exit
compute-tycoon> node add app-1 application_server
compute-tycoon> server name set app-1 "Frontend 1"
compute-tycoon> node add db-1 database_server
compute-tycoon> node add sw-1 network_switch
compute-tycoon> link connect app-1:lan0 sw-1:port1
compute-tycoon> link connect db-1:lan0 sw-1:port2
compute-tycoon> ip addr add app-1:lan0 192.168.10.10/24
compute-tycoon> ip addr add db-1:lan0 192.168.10.20/24
compute-tycoon> ping app-1 db-1
compute-tycoon> ssh app-1
```

Router example:

```text
compute-tycoon> shop
shop> list server
shop> buy server router
shop> exit
compute-tycoon> node add router-1 router
compute-tycoon> ip addr add router-1:lan0 192.168.10.1/24
compute-tycoon> ip addr add router-1:lan1 192.168.20.1/24
compute-tycoon> route add app-1 0.0.0.0/0 via 192.168.10.1
compute-tycoon> route add db-1 0.0.0.0/0 via 192.168.20.1
```

Manual assembly example:

```text
compute-tycoon> shop
shop> list motherboard
shop> buy motherboard mb.starter.am4.ddr4
shop> list cpu
shop> buy cpu cpu.starter.4core
shop> list ram
shop> buy ram memory.app
shop> list storage
shop> buy storage storage.app.nvme
shop> exit
compute-tycoon> build app-2
build(app-2)> motherboard select mb.starter.am4.ddr4
build(app-2)> cpu add cpu.starter.4core
build(app-2)> ram add memory.app
build(app-2)> storage add storage.app.nvme
build(app-2)> validate
build(app-2)> commit
compute-tycoon> server name set app-2 "Frontend 2"
compute-tycoon> node role set app-2 application_server
```

## Autosave

The autosave file is JSON at `hardware_sim/data/save_game.json`.
The autosave writer is intentionally decoupled from command handling:

1. `ComputeTycoonGame` mutates state under a lock.
2. The mutation increments `state_version`.
3. `AutosaveWorker` runs in its own thread.
4. The worker polls `state_version`, snapshots the game if it changed, and
   atomically replaces the save JSON.

Saved state includes:

- purchased part inventory
- purchased prebuilt server inventory
- built nodes and their original build requests
- cable inventory
- physical links
- interface addresses
- routes

The game loads the autosave file on startup when it exists. If the file does
not exist, the player starts with an empty inventory and no built nodes.
