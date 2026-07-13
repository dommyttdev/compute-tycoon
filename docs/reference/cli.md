# CLIリファレンス

## 起動と言語

```text
python main.py [--lang LOCALE]
```

起動メッセージとHelpは英語 (`en`) と日本語 (`ja`) を提供します。表示言語はShell生成時に
一度だけ、次の優先順位で決定します。

1. `--lang LOCALE`
2. 環境変数`COMPUTE_TYCOON_LANG`
3. OSのlocale
4. 英語 (`en`)

Localeは大文字と小文字を区別せず、`_`を`-`として扱い、encoding suffixを無視します。
地域を含む値とOS固有名は基底言語へ正規化するため、`ja-JP`、`ja_JP.UTF-8`、
Windowsの`Japanese_Japan`は`ja`、`en-US`と`English_United States`は`en`になります。

`--lang`へ未対応のlocaleを明示した場合は、利用可能なlocaleを示す起動エラーとし、Shellを
開始しません。環境変数またはOSから得たlocaleが未対応、空、または取得不能の場合は英語を
使用します。選択した言語に翻訳文がないHelp項目も、その項目だけ英語へfallbackします。

LocaleはCLI表示だけの設定です。Gameの`RuntimeConfig`、Snapshot、保存データ、
`state_version`には含めません。

## Helpの段階

Helpは情報量を次の3段階に分けます。

1. 起動直後はGameの目的、最初の操作、`help`の使い方だけを表示します。全コマンドは列挙しません。
2. 引数なしの`help`はトップレベルコマンドを目的別カテゴリで表示します。
3. `help COMMAND`は用途、すべての構文、引数の意味、alias、短い例、別モードへ移動するかを表示します。

起動時の日本語表示例:

```text
Compute Tycoon
Nodeを構築し、Topologyを接続して、Workloadを実行します。

はじめに: shop -> node add / build NODE_ID -> link / ip -> run workload
コマンド体系は 'help'、詳細は 'help COMMAND' で確認できます。
```

`shop`、`build NODE_ID`、`ssh NODE`は別モードを開始します。各モードで実行した`help`は、
そのモードで使用できるコマンドだけを表示します。`EOF`は対話入力の終了方法ですが、
コマンド一覧には表示しません。Aliasは正規コマンドと同じ行に表示します。

### 購入と組み立て

| コマンド | 用途 |
| --- | --- |
| `shop` | 購入モードへ移動 |
| `inventory` | 購入済み資産を表示 |
| `build NODE_ID` | 所有Partを使う手動組み立てモードへ移動 |

### Nodeの管理

| コマンド | 用途 |
| --- | --- |
| `node list` / `node ls` | 構築済みNodeを表示 |
| `node add NODE_ID ROLE` | 購入済み完成品を配置 |
| `node role set NODE_ID ROLE` | 構築済みNodeへ役割を設定 |
| `node show NODE_ID` | NodeのInterfaceを表示 |
| `server list` / `server ls` | Server RoleのNodeを表示 |
| `server name set NODE_ID NAME` | 表示名を変更 |
| `server show NODE_ID` | Server RoleのNodeのInterfaceを表示 |
| `ssh NODE_ID` | Nodeローカルシェルへ移動 |

`Node`は構築済みMachine全般を表し、RouterとNetwork Switchも含みます。`server`は
Server RoleのNodeに対する表示名などの操作であり、すべてのNodeの別名ではありません。

### Topologyの設定と確認

| コマンド | 用途 |
| --- | --- |
| `link list` / `link ls` | 接続済みCableを表示 |
| `link connect NODE:PORT NODE:PORT [CABLE]` | ポート間を接続 |
| `link disconnect NODE:PORT` | Cableを外してInventoryへ戻す |
| `ip addr` | IPv4 addressを表示 |
| `ip addr add NODE:PORT CIDR` | IPv4アドレスを設定 |
| `ip route [NODE]` | Routeを表示 |
| `route list [NODE]` / `route ls [NODE]` | Routeを表示 |
| `route add NODE DESTINATION via GATEWAY [dev PORT]` | 経路を設定 |
| `ping SOURCE_NODE TARGET_NODE` | 到達性を確認 |
| `traceroute SOURCE_NODE TARGET_NODE` | 通過Nodeを表示 |

`route`をRoute管理の正規の入口とします。`ip route [NODE]`は参照専用の同等操作です。

### Workloadの実行と観測

| コマンド | 用途 |
| --- | --- |
| `run workload KIND [--jobs N]` | Application Serverを入口としてWorkloadを実行し、構造化結果を表示 |
| `logs [NODE]` | EventLogを表示 |

### Session

| コマンド | 用途 |
| --- | --- |
| `help [COMMAND]` | カテゴリ一覧または指定コマンドの詳細を表示 |
| `exit` / `quit` | 保存をflushして終了 |

Help本文は選択したlocaleで表示しますが、コマンドkeyword、構文、`NODE_ID`などのplaceholder、
Node ID、Part ID、Role、Workload kind、failure codeは翻訳しません。コマンドの成功出力、
EventLog、Workload結果、警告、エラーも現在は翻訳対象外です。

## ShopShell

| コマンド | 用途 |
| --- | --- |
| `list [KIND]` / `ls [KIND]` | 購入可能な完成品、Cable、Partを表示 |
| `buy server ROLE [QTY]` | 完成品を購入 |
| `buy cable CABLE [QTY]` | Cableを購入 |
| `buy KIND PART_ID [QTY]` | Partを購入 |
| `inventory` | 購入済み資産を表示 |
| `exit` / `back` | トップレベルへ戻る |

## BuildShell

| コマンド | 用途 |
| --- | --- |
| `motherboard list` / `motherboard ls` | 選択可能なMotherboardを表示 |
| `motherboard select PART_ID` | Motherboardを選択 |
| `cpu|ram|storage|gpu|nic list` | 種別ごとの選択可能なPartを表示 |
| `cpu|ram|storage|gpu|nic add PART_ID` | 構成へPartを追加 |
| `cpu|ram|storage|gpu|nic remove PART_ID` | 構成からPartを外す |
| `name NAME` | Nodeの表示名を設定 |
| `workers COUNT` | Worker数を設定 |
| `summary` | 組み立てdraftを表示 |
| `validate` | Inventoryと互換性の制約を検証 |
| `commit` | 検証済みdraftをNodeとして構築 |
| `cancel` / `exit` | 構築せずトップレベルへ戻る |

`commit`したNodeは`unassigned`なので、後から`node role set`を実行します。

引数なしの`help`では次のカテゴリに分けます。

- Partの選択: `motherboard`、`cpu`、`ram`、`storage`、`gpu`、`nic`
- 構成: `name`、`workers`
- 確認と終了: `summary`、`validate`、`commit`、`cancel` / `exit`

## NodeShell

| コマンド | 用途 |
| --- | --- |
| `ip addr` | 接続先NodeのIPv4 addressを表示 |
| `ip route` | 接続先NodeのRouteを表示 |
| `show interfaces` | 接続先NodeのInterfaceを表示 |
| `show ip route` | 接続先NodeのRouteを表示 |
| `top` | 接続先NodeのSnapshotを表示 |
| `journalctl` | 接続先NodeのEventLogを表示 |
| `exit` / `logout` | トップレベルへ戻る |

## Workload結果

`run workload`はGameが返した`WorkloadResult`をShellが表示します。Gameは表示文字列を
組み立てません。出力にはWorkload、各Job、各Stepのcompleted/failedと失敗理由、入口
Application Server、各backend子StepのRoleとNode、解決した経路を含めます。各失敗理由は
安定したcodeと人向けmessageとして表示します。

親Application ServerのWorkは、preの開始からbackend子Workの同期待機とpostの終了まで
runningです。子が失敗した場合は子の理由に加えて親の`delegation_failed`を表示し、通常のpostは
実行されません。`--jobs N`で一つのJobが失敗しても後続Jobは実行し、最後にすべてのJob結果を
表示します。入口がない、対象Roleがない、Node/Roleが不一致、経路不能、Node実行失敗は
Python例外や`StopIteration`の表示ではなく、安定したdomain failure codeとして表示します。

## 最小例

```text
compute-tycoon> shop
shop> buy server application_server
shop> buy server database_server
shop> buy cable cable.cat6.patch 2
shop> exit
compute-tycoon> node add app-1 application_server
compute-tycoon> node add db-1 database_server
compute-tycoon> link connect app-1:lan0 db-1:lan0
compute-tycoon> ip addr add app-1:lan0 192.168.10.10/24
compute-tycoon> ip addr add db-1:lan0 192.168.10.20/24
compute-tycoon> ping app-1 db-1
```
