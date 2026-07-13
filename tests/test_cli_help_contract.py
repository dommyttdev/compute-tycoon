import pytest

from hardware_sim import ComputeTycoonGame, NodeRole, TycoonShell
from hardware_sim.shell import BuildShell, NodeShell, ShopShell


def test_japanese_shell_intro_explains_the_game_and_keeps_help_syntax() -> None:
    game = ComputeTycoonGame(save_path=None, load_save=False)
    try:
        shell = TycoonShell(game, locale="ja")

        assert "Nodeを構築し、Topologyを接続して、Workloadを実行します。" in shell.intro
        assert "'help'" in shell.intro
        assert "'help COMMAND'" in shell.intro
    finally:
        game.stop_all()


def test_japanese_bare_help_groups_canonical_commands_by_player_purpose(capsys) -> None:
    game = ComputeTycoonGame(save_path=None, load_save=False)
    try:
        shell = TycoonShell(game, locale="ja")

        shell.onecmd("help")

        output = capsys.readouterr().out
        headings = (
            "購入と組み立て",
            "Nodeの管理",
            "Topologyの設定と確認",
            "Workloadの実行と観測",
            "セッション",
        )
        assert all(heading in output for heading in headings), output
        assert [output.index(heading) for heading in headings] == sorted(
            output.index(heading) for heading in headings
        )
        assert "shop" in output
        assert "node ..." in output
        assert "link ..." in output
        assert "run workload KIND" in output
        assert "help [COMMAND]" in output
        assert "exit | quit" in output
        assert "EOF" not in output
    finally:
        game.stop_all()


def test_japanese_node_help_explains_usage_examples_and_related_commands(
    capsys,
) -> None:
    game = ComputeTycoonGame(save_path=None, load_save=False)
    try:
        shell = TycoonShell(game, locale="ja")

        shell.onecmd("help node")

        output = capsys.readouterr().out
        assert "Nodeの配置、Role変更、状態確認を行う" in output
        assert "node list" in output
        assert "node ls" in output
        assert "node add NODE_ID ROLE" in output
        assert "node role set NODE_ID ROLE" in output
        assert "node show NODE_ID" in output
        assert "node add app-1 application_server" in output
        assert "関連コマンド" in output
        assert "shop" in output
        assert "build" in output
        assert "server" in output
    finally:
        game.stop_all()


@pytest.mark.parametrize(
    ("topic", "purpose", "syntaxes", "example"),
    (
        pytest.param("shop", "購入モードへ移動", ("shop",), "shop", id="shop"),
        pytest.param(
            "inventory",
            "購入済み資産を表示",
            ("inventory",),
            "inventory",
            id="inventory",
        ),
        pytest.param(
            "build",
            "手動組み立てモードへ移動",
            ("build NODE_ID",),
            "build compute-1",
            id="build",
        ),
        pytest.param(
            "node",
            "Nodeの配置、Role変更、状態確認を行う",
            (
                "node list | node ls",
                "node add NODE_ID ROLE",
                "node role set NODE_ID ROLE",
                "node show NODE_ID",
            ),
            "node add app-1 application_server",
            id="node",
        ),
        pytest.param(
            "server",
            "Server RoleのNode",
            (
                "server list | server ls",
                "server name set NODE_ID NAME",
                "server show NODE_ID",
            ),
            "server show app-1",
            id="server",
        ),
        pytest.param(
            "ssh",
            "Nodeローカルシェルへ移動",
            ("ssh NODE_ID",),
            "ssh app-1",
            id="ssh",
        ),
        pytest.param(
            "link",
            "Port間のCableを接続・切断する",
            (
                "link list | link ls",
                "link connect NODE:PORT NODE:PORT [CABLE]",
                "link disconnect NODE:PORT",
            ),
            "link list",
            id="link",
        ),
        pytest.param(
            "ip",
            "IPv4 addressを確認・設定する",
            (
                "ip addr",
                "ip addr add NODE:PORT CIDR",
                "ip route [NODE]",
            ),
            "ip addr",
            id="ip",
        ),
        pytest.param(
            "route",
            "Routeを確認・追加する",
            (
                "route list [NODE] | route ls [NODE]",
                "route add NODE DESTINATION via GATEWAY [dev PORT]",
            ),
            "route list",
            id="route",
        ),
        pytest.param(
            "ping",
            "到達性を確認",
            ("ping SOURCE_NODE TARGET_NODE",),
            "ping app-1 db-1",
            id="ping",
        ),
        pytest.param(
            "traceroute",
            "通過Nodeを表示",
            ("traceroute SOURCE_NODE TARGET_NODE",),
            "traceroute app-1 db-1",
            id="traceroute",
        ),
        pytest.param(
            "run",
            "Workloadを実行",
            ("run workload KIND [--jobs N]",),
            "run workload web",
            id="run",
        ),
        pytest.param(
            "logs",
            "EventLogを表示",
            ("logs [NODE]",),
            "logs app-1",
            id="logs",
        ),
        pytest.param(
            "exit",
            "保存をflushして終了",
            ("exit | quit",),
            "exit",
            id="exit",
        ),
    ),
)
def test_japanese_top_level_command_help_is_complete(
    capsys,
    topic: str,
    purpose: str,
    syntaxes: tuple[str, ...],
    example: str,
) -> None:
    game = ComputeTycoonGame(save_path=None, load_save=False)
    try:
        shell = TycoonShell(game, locale="ja")

        shell.onecmd(f"help {topic}")

        output = capsys.readouterr().out
        assert purpose in output
        assert "使い方" in output
        assert all(syntax in output for syntax in syntaxes), output
        assert "例" in output
        assert example in output
    finally:
        game.stop_all()


@pytest.mark.parametrize(
    ("mode", "expected_rows", "unrelated_rows"),
    (
        pytest.param(
            "shop",
            (
                "list [KIND] | ls [KIND]",
                "buy server ROLE [QTY]",
                "buy cable CABLE [QTY]",
                "buy KIND PART_ID [QTY]",
                "inventory",
                "exit | back",
            ),
            ("build NODE_ID", "node ...", "link ...", "run workload KIND"),
            id="shop",
        ),
        pytest.param(
            "build",
            (
                "motherboard list | motherboard ls",
                "motherboard select PART_ID",
                "cpu|ram|storage|gpu|nic list",
                "cpu|ram|storage|gpu|nic add PART_ID",
                "cpu|ram|storage|gpu|nic remove PART_ID",
                "name NAME",
                "workers COUNT",
                "summary",
                "validate",
                "commit",
                "cancel | exit",
            ),
            ("shop", "node ...", "link ...", "run workload KIND"),
            id="build",
        ),
        pytest.param(
            "node",
            (
                "ip addr",
                "ip route",
                "show interfaces",
                "show ip route",
                "top",
                "journalctl",
                "exit | logout",
            ),
            ("shop", "build NODE_ID", "node ...", "run workload KIND"),
            id="node",
        ),
    ),
)
def test_japanese_nested_shell_help_is_mode_local_and_categorized(
    capsys,
    mode: str,
    expected_rows: tuple[str, ...],
    unrelated_rows: tuple[str, ...],
) -> None:
    game = ComputeTycoonGame(save_path=None, load_save=False)
    try:
        if mode == "shop":
            shell = ShopShell(game, locale="ja")
        elif mode == "build":
            shell = BuildShell(game, "compute-1", locale="ja")
        else:
            game.buy_server(NodeRole.APPLICATION_SERVER)
            game.add_node("app-1", NodeRole.APPLICATION_SERVER)
            shell = NodeShell(game, "app-1", locale="ja")

        shell.onecmd("help")

        output = capsys.readouterr().out
        assert any("\u3040" <= character <= "\u30ff" for character in output), output
        assert all(row in output for row in expected_rows), output
        assert all(row not in output for row in unrelated_rows), output
        assert "EOF" not in output
        if mode == "build":
            groups = ("Partの選択", "構成", "確認と終了")
            assert all(group in output for group in groups), output
            assert [output.index(group) for group in groups] == sorted(
                output.index(group) for group in groups
            )
    finally:
        game.stop_all()


@pytest.mark.parametrize(
    ("explicit", "environment", "system", "expected", "check_invalid"),
    (
        pytest.param("ja-JP", "en", "en", "ja", True, id="explicit-wins"),
        pytest.param(
            "ja_JP.UTF-8",
            None,
            None,
            "ja",
            False,
            id="encoding-and-region-normalized",
        ),
        pytest.param(None, "en-US", "ja-JP", "en", False, id="environment-wins"),
        pytest.param(
            None,
            "fr-FR",
            "ja-JP",
            "en",
            False,
            id="unsupported-automatic-falls-back",
        ),
        pytest.param(None, None, "ja_JP.UTF-8", "ja", False, id="system-locale"),
        pytest.param(None, None, None, "en", False, id="default-english"),
    ),
)
def test_locale_resolution_normalizes_precedence_and_fallback(
    explicit: str | None,
    environment: str | None,
    system: str | None,
    expected: str,
    check_invalid: bool,
) -> None:
    from hardware_sim.localization import resolve_locale

    assert resolve_locale(explicit, environment, system) == expected
    if check_invalid:
        with pytest.raises(ValueError) as error:
            resolve_locale("fr-FR", "ja", "ja")

        assert "en" in str(error.value)
        assert "ja" in str(error.value)


def test_english_shell_intro_explains_the_complete_first_journey() -> None:
    game = ComputeTycoonGame(save_path=None, load_save=False)
    try:
        shell = TycoonShell(game, locale="en")

        assert "Build Nodes, connect a Topology, and run Workloads." in shell.intro
        assert (
            "shop -> node add / build NODE_ID -> link / ip -> run workload"
            in shell.intro
        )
        assert "'help'" in shell.intro
        assert "'help COMMAND'" in shell.intro
    finally:
        game.stop_all()


def test_japanese_help_topic_describes_structured_help_itself(capsys) -> None:
    game = ComputeTycoonGame(save_path=None, load_save=False)
    try:
        shell = TycoonShell(game, locale="ja")

        shell.onecmd("help help")

        output = capsys.readouterr().out
        assert "カテゴリ一覧または指定コマンドの詳細を表示" in output
        assert "使い方" in output
        assert "help [COMMAND]" in output
        assert "例" in output
        assert "help node" in output
        assert "List available commands" not in output
        assert "detailed help with" not in output
    finally:
        game.stop_all()


@pytest.mark.parametrize(
    ("mode", "topics", "summary", "syntaxes", "example"),
    (
        pytest.param(
            "shop",
            ("list", "ls"),
            "購入可能な完成品、Cable、Partを表示",
            ("list [KIND] | ls [KIND]",),
            "list server",
            id="shop-list",
        ),
        pytest.param(
            "shop",
            ("buy",),
            "完成品、Cable、Partを購入",
            (
                "buy server ROLE [QTY]",
                "buy cable CABLE [QTY]",
                "buy KIND PART_ID [QTY]",
            ),
            "buy server application_server",
            id="shop-buy",
        ),
        pytest.param(
            "shop",
            ("inventory",),
            "購入済み資産を表示",
            ("inventory",),
            "inventory",
            id="shop-inventory",
        ),
        pytest.param(
            "shop",
            ("exit", "back"),
            "トップレベルへ戻る",
            ("exit | back",),
            "exit",
            id="shop-exit",
        ),
        pytest.param(
            "build",
            ("motherboard",),
            "Motherboardを表示・選択",
            (
                "motherboard list | motherboard ls",
                "motherboard select PART_ID",
            ),
            "motherboard list",
            id="build-motherboard",
        ),
        *(
            pytest.param(
                "build",
                (kind,),
                f"{label} Partを管理",
                (
                    f"{kind} list",
                    f"{kind} add PART_ID",
                    f"{kind} remove PART_ID",
                ),
                f"{kind} list",
                id=f"build-{kind}",
            )
            for kind, label in (
                ("cpu", "CPU"),
                ("ram", "RAM"),
                ("storage", "Storage"),
                ("gpu", "GPU"),
                ("nic", "NIC"),
            )
        ),
        pytest.param(
            "build",
            ("name",),
            "Nodeの表示名を設定",
            ("name NAME",),
            "name web-1",
            id="build-name",
        ),
        pytest.param(
            "build",
            ("workers",),
            "Worker数を設定",
            ("workers COUNT",),
            "workers 4",
            id="build-workers",
        ),
        pytest.param(
            "build",
            ("summary",),
            "組み立てdraftを表示",
            ("summary",),
            "summary",
            id="build-summary",
        ),
        pytest.param(
            "build",
            ("validate",),
            "Inventoryと互換性の制約を検証",
            ("validate",),
            "validate",
            id="build-validate",
        ),
        pytest.param(
            "build",
            ("commit",),
            "検証済みdraftをNodeとして構築",
            ("commit",),
            "commit",
            id="build-commit",
        ),
        pytest.param(
            "build",
            ("cancel", "exit"),
            "構築せずトップレベルへ戻る",
            ("cancel | exit",),
            "cancel",
            id="build-cancel",
        ),
        pytest.param(
            "node",
            ("ip",),
            "接続先NodeのIPv4 addressとRouteを表示",
            ("ip addr", "ip route"),
            "ip addr",
            id="node-ip",
        ),
        pytest.param(
            "node",
            ("show",),
            "接続先NodeのInterfaceとRouteを表示",
            ("show interfaces", "show ip route"),
            "show interfaces",
            id="node-show",
        ),
        pytest.param(
            "node",
            ("top",),
            "接続先NodeのSnapshotを表示",
            ("top",),
            "top",
            id="node-top",
        ),
        pytest.param(
            "node",
            ("journalctl",),
            "接続先NodeのEventLogを表示",
            ("journalctl",),
            "journalctl",
            id="node-journalctl",
        ),
        pytest.param(
            "node",
            ("exit", "logout"),
            "トップレベルへ戻る",
            ("exit | logout",),
            "exit",
            id="node-exit",
        ),
    ),
)
def test_japanese_nested_command_help_is_structured_and_aliases_resolve(
    capsys,
    mode: str,
    topics: tuple[str, ...],
    summary: str,
    syntaxes: tuple[str, ...],
    example: str,
) -> None:
    game = ComputeTycoonGame(save_path=None, load_save=False)
    try:
        if mode == "shop":
            shell = ShopShell(game, locale="ja")
        elif mode == "build":
            shell = BuildShell(game, "compute-1", locale="ja")
        else:
            game.buy_server(NodeRole.APPLICATION_SERVER)
            game.add_node("app-1", NodeRole.APPLICATION_SERVER)
            shell = NodeShell(game, "app-1", locale="ja")

        outputs = []
        for topic in topics:
            shell.onecmd(f"help {topic}")
            outputs.append(capsys.readouterr().out)

        output = outputs[0]
        assert summary in output
        assert "使い方" in output
        assert all(syntax in output for syntax in syntaxes), output
        assert "例" in output
        assert example in output
        assert all(alias_output == output for alias_output in outputs[1:])
    finally:
        game.stop_all()
