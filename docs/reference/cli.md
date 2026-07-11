# CLIリファレンス

## トップレベル

| コマンド | 用途 |
| --- | --- |
| `shop` | 購入モードへ移動 |
| `inventory` | 購入済み資産を表示 |
| `node add ID ROLE` | 購入済み完成品を配置 |
| `node role set ID ROLE` | 構築済みNodeへ役割を設定 |
| `server name set ID NAME` | 表示名を変更 |
| `build ID` | 手動組み立てモードへ移動 |
| `link connect A B [CABLE]` | ポート間を接続 |
| `link disconnect PORT` | Cableを外してInventoryへ戻す |
| `ip addr add PORT CIDR` | IPv4アドレスを設定 |
| `route add NODE DEST via GW [dev IFACE]` | 経路を設定 |
| `ping SOURCE TARGET` | 到達性を確認 |
| `traceroute SOURCE TARGET` | 通過Nodeを表示 |
| `ssh NODE` | Nodeローカルシェルへ移動 |
| `run workload KIND [--jobs N]` | Workloadを実行 |
| `logs [NODE]` | EventLogを表示 |
| `exit` / `quit` | 保存をflushして終了 |

## ShopShell

`list [kind]`、`buy server ROLE [QTY]`、`buy cable ID [QTY]`、
`buy KIND PART_ID [QTY]`、`inventory`を提供します。

## BuildShell

`motherboard select ID`、`cpu|ram|storage|gpu|nic add ID`、`name NAME`、
`workers N`、`summary`、`validate`、`commit`、`cancel`を提供します。`commit`したNodeは
`unassigned`なので、後から`node role set`を実行します。

## NodeShell

`ip addr`、`ip route`、`show interfaces`、`top`、`journalctl`を提供します。

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
