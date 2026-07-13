ENGLISH_INTRO = """Compute Tycoon
Build Nodes, connect a Topology, and run Workloads.

Start with: shop -> node add / build NODE_ID -> link / ip -> run workload
Type 'help' for command groups or 'help COMMAND' for details.
"""

SUPPORTED_LOCALES = ("en", "ja")

JAPANESE_INTRO = """Compute Tycoon
Nodeを構築し、Topologyを接続して、Workloadを実行します。

はじめに: shop -> node add / build NODE_ID -> link / ip -> run workload
コマンド体系は 'help'、詳細は 'help COMMAND' で確認できます。
"""

MESSAGES = {
    "en": {
        "help.title": "Available commands",
        "help.section.usage": "Usage",
        "help.section.examples": "Examples",
        "help.section.related": "Related commands",
        "help.group.acquire": "Acquire & assemble",
        "help.group.nodes": "Manage Nodes",
        "help.group.topology": "Configure & verify Topology",
        "help.group.workloads": "Run & observe Workloads",
        "help.group.session": "Session",
        "help.shop.summary": "Browse and buy servers, Cables, and Parts",
        "help.inventory.summary": "Show purchased assets available for use",
        "help.build.summary": "Assemble a Node from purchased Parts",
        "help.node.summary": "List, add, inspect, or change the Role of Nodes",
        "help.server.summary": "List, rename, or inspect Server Role Nodes",
        "help.ssh.summary": "Enter the local inspection shell for a Node",
        "help.link.summary": "Connect or disconnect physical Cables",
        "help.ip.summary": "List or assign Interface addresses",
        "help.route.summary": "List or add network Routes",
        "help.ping.summary": "Test reachability between Nodes",
        "help.traceroute.summary": "Show the path between Nodes",
        "help.run.summary": "Run one or more Workload jobs",
        "help.logs.summary": "Show Game-wide or Node-specific events",
        "help.help.summary": "Show command groups or detailed Help",
        "help.exit.summary": "Stop the Game and leave",
        "shop.intro": "Shop mode. Type 'list', 'buy ...', 'inventory', or 'exit'.",
        "shop.group.commands": "Shop commands",
        "shop.list.summary": "Show assets available to purchase",
        "shop.list_detail.summary": "Show available prebuilt Nodes, Cables, and Parts",
        "shop.buy.summary": "Buy prebuilt Nodes, Cables, or Parts",
        "shop.buy_server.summary": "Buy a prebuilt Node",
        "shop.buy_cable.summary": "Buy Cables",
        "shop.buy_part.summary": "Buy Parts by kind",
        "shop.exit.summary": "Return to the top-level shell",
        "build.group.parts": "Select Parts",
        "build.group.configure": "Configure Assembly",
        "build.group.finish": "Review & finish",
        "build.part_list.summary": "Show available Parts",
        "build.part_select.summary": "Select the Motherboard",
        "build.part_add.summary": "Add a Part to the Assembly",
        "build.part_remove.summary": "Remove a Part from the Assembly",
        "build.motherboard.summary": "Show or select the Motherboard",
        "build.cpu.summary": "Manage CPU Parts",
        "build.ram.summary": "Manage RAM Parts",
        "build.storage.summary": "Manage Storage Parts",
        "build.gpu.summary": "Manage GPU Parts",
        "build.nic.summary": "Manage NIC Parts",
        "build.name.summary": "Set the Node display name",
        "build.workers.summary": "Set the worker count",
        "build.summary.summary": "Show the Assembly draft",
        "build.validate.summary": "Validate inventory and compatibility",
        "build.commit.summary": "Build the validated Node",
        "build.cancel.summary": "Return without building",
        "node_shell.group.inspect": "Inspect Node",
        "node_shell.address.summary": "Show IPv4 addresses",
        "node_shell.route.summary": "Show Routes",
        "node_shell.interfaces.summary": "Show Interfaces",
        "node_shell.top.summary": "Show the Node Snapshot",
        "node_shell.journal.summary": "Show the Node EventLog",
        "node_shell.exit.summary": "Return to the top-level shell",
        "node_shell.ip.summary": "Show IPv4 addresses and Routes for the connected Node",
        "node_shell.show.summary": "Show Interfaces and Routes for the connected Node",
    },
    "ja": {
        "help.title": "利用可能なコマンド",
        "help.section.usage": "使い方",
        "help.section.examples": "例",
        "help.section.related": "関連コマンド",
        "help.group.acquire": "購入と組み立て",
        "help.group.nodes": "Nodeの管理",
        "help.group.topology": "Topologyの設定と確認",
        "help.group.workloads": "Workloadの実行と観測",
        "help.group.session": "セッション",
        "help.shop.summary": "完成品、Cable、Partの購入モードへ移動する",
        "help.inventory.summary": "購入済み資産を表示する",
        "help.build.summary": "Nodeの手動組み立てモードへ移動する",
        "help.node.summary": "Nodeの配置、Role変更、状態確認を行う",
        "help.server.summary": "Server RoleのNodeを一覧・改名・確認する",
        "help.ssh.summary": "Nodeローカルシェルへ移動する",
        "help.link.summary": "Port間のCableを接続・切断する",
        "help.ip.summary": "InterfaceのIPv4 addressを確認・設定する",
        "help.route.summary": "Routeを確認・追加する",
        "help.ping.summary": "Node間の到達性を確認する",
        "help.traceroute.summary": "Node間の通過Nodeを表示する",
        "help.run.summary": "Workloadを実行する",
        "help.logs.summary": "GameまたはNodeのEventLogを表示する",
        "help.help.summary": "カテゴリ一覧または指定コマンドの詳細を表示する",
        "help.exit.summary": "保存をflushして終了する",
        "shop.intro": "Shopモードです。'list'、'buy ...'、'inventory'、'exit'を使用できます。",
        "shop.group.commands": "Shopの操作",
        "shop.list.summary": "購入可能な資産を表示する",
        "shop.list_detail.summary": "購入可能な完成品、Cable、Partを表示する",
        "shop.buy.summary": "完成品、Cable、Partを購入する",
        "shop.buy_server.summary": "完成品のNodeを購入する",
        "shop.buy_cable.summary": "Cableを購入する",
        "shop.buy_part.summary": "種類を指定してPartを購入する",
        "shop.exit.summary": "トップレベルへ戻る",
        "build.group.parts": "Partの選択",
        "build.group.configure": "構成",
        "build.group.finish": "確認と終了",
        "build.part_list.summary": "選択可能なPartを表示する",
        "build.part_select.summary": "Motherboardを選択する",
        "build.part_add.summary": "AssemblyへPartを追加する",
        "build.part_remove.summary": "AssemblyからPartを外す",
        "build.motherboard.summary": "Motherboardを表示・選択する",
        "build.cpu.summary": "CPU Partを管理する",
        "build.ram.summary": "RAM Partを管理する",
        "build.storage.summary": "Storage Partを管理する",
        "build.gpu.summary": "GPU Partを管理する",
        "build.nic.summary": "NIC Partを管理する",
        "build.name.summary": "Nodeの表示名を設定する",
        "build.workers.summary": "Worker数を設定する",
        "build.summary.summary": "組み立てdraftを表示する",
        "build.validate.summary": "Inventoryと互換性の制約を検証する",
        "build.commit.summary": "検証済みdraftをNodeとして構築する",
        "build.cancel.summary": "構築せずトップレベルへ戻る",
        "node_shell.group.inspect": "Nodeの確認",
        "node_shell.address.summary": "IPv4 addressを表示する",
        "node_shell.route.summary": "Routeを表示する",
        "node_shell.interfaces.summary": "Interfaceを表示する",
        "node_shell.top.summary": "接続先NodeのSnapshotを表示する",
        "node_shell.journal.summary": "接続先NodeのEventLogを表示する",
        "node_shell.exit.summary": "トップレベルへ戻る",
        "node_shell.ip.summary": "接続先NodeのIPv4 addressとRouteを表示する",
        "node_shell.show.summary": "接続先NodeのInterfaceとRouteを表示する",
    },
}


def shell_intro(locale: str) -> str:
    if locale == "ja":
        return JAPANESE_INTRO
    return ENGLISH_INTRO


def message(locale: str, key: str) -> str:
    return MESSAGES.get(locale, MESSAGES["en"]).get(key, MESSAGES["en"][key])


def resolve_locale(
    explicit: str | None, environment: str | None, system: str | None
) -> str:
    if explicit is not None:
        locale = _normalize_locale(explicit)
        if locale not in SUPPORTED_LOCALES:
            available = ", ".join(SUPPORTED_LOCALES)
            raise ValueError(
                f"Unsupported locale: {explicit!r}. Available locales: {available}"
            )
        return locale

    automatic = environment if environment is not None else system
    if automatic is None:
        return "en"
    locale = _normalize_locale(automatic)
    return locale if locale in SUPPORTED_LOCALES else "en"


def _normalize_locale(locale: str) -> str:
    normalized = locale.strip().lower().split(".", maxsplit=1)[0]
    normalized = normalized.replace("_", "-")
    return normalized.split("-", maxsplit=1)[0]
