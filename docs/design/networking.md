# ネットワーク設計

## モデル

プレイ用ネットワークは、物理層と論理層を分けて表現します。

- `NetworkPortRef`: `node-id:port-name`形式のポート参照
- `Cable`: 二つのポートを結ぶ購入済み物理ケーブル
- `InterfaceAddress`: ポートに割り当てたIPv4 CIDR
- `RouteEntry`: ノード単位のIPv4経路
- `NetworkTopology`: 上記をまとめる不変値オブジェクト

Topologyの変更メソッドは自身を変更せず、新しいTopologyを返します。Node集合は
`MappingProxyType`で読み取り専用化されます。

## ポート

通常ノードはNICごとに`lan0`、`lan1`…を持ちます。Switchは全NICのポート数を合計し、
`port1`から始まるポート名を持ちます。各ポートに接続できるCableは1本です。

## 到達性解決

`resolve(source, target)`は対象ノードの先頭IPv4アドレスを宛先にします。

1. 同一サブネットの送信元アドレスを探す。
2. CableとSwitch内部転送を幅優先探索し、L2経路を探す。
3. 直接到達できなければ最長一致でRouteEntryを選ぶ。
4. GatewayまでのL2経路を確認し、Gatewayノードから繰り返す。
5. 訪問済みノードへの再入をRouting loopとして拒否する。

IPv4のみ対応します。`ping`は到達性解決の別名、`traceroute`は得られたノード列を
表示します。複数ノードWorkloadでも、次のStepへ進む前に同じ解決を行います。

## 制約

- Targetには少なくとも1つのIPアドレスが必要。
- Routeの明示Interfaceは実在する必要がある。
- Gatewayは既知のInterfaceAddressで、送信元から同一サブネット上で到達可能であること。
- Switchだけが同一ノード内の異なる物理ポート間をL2転送する。
