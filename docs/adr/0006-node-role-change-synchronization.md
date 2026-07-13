# ADR-0006: ノード役割変更の同期境界

- 状態: 採用
- 日付: 2026-07-13

## 文脈

ADR-0003ではNodeのRoleに対応する実行戦略を`RoleExecutor`へ分離し、役割変更時にExecutorを
差し替えると決定した。しかし、GameがNodeのRoleとExecutorを別々に代入すると、Nodeのworkerは
旧Roleと新Executorなどの不整合な組み合わせを観測できる。また、実行中の役割変更を許すと、
1つのWorkが開始時と異なる実行戦略やRoleを観測する可能性がある。

Gameは保存用`BuildRequest`とstate versionも所有するため、Node側の変更が失敗した場合に
これらだけを進めてはならない。

## 決定

Role変更は`Node.set_role()`が所有する。NodeはRoleから対応するExecutorを内部生成し、
Nodeの`Condition`内でRoleとExecutorを一体として更新する。workerはWorkをrunningへ移すとき、
同じ`Condition`内でExecutorを取得する。

実際のRole変更はNodeがidleの場合だけ許可する。queuedまたはrunning Workがあれば
`RuntimeError`で拒否する。停止済みNodeを別のRoleへ変更する場合も`RuntimeError`で拒否する。
同じRoleへの設定は状態にかかわらず副作用のないno-opとする。

Game所有Nodeは`ComputeTycoonGame.set_node_role()`から変更する。ロック順序はGameの`RLock`、
Nodeの`Condition`の順とする。Node側の変更が成功した後だけ、同じGameロック内で保存用
`BuildRequest`を置き換え、イベントを記録し、state versionを1回増やす。拒否または失敗時は
これらを変更しない。

## 結果

workerは1回のWork実行中に整合したRoleとExecutorを使用する。queued WorkがどちらのRoleで
動くかはタイミングに依存せず、Role変更要求が明示的に失敗する。呼び出し側はWork完了後に
再試行する必要がある。

RoleとExecutorの更新責務はNodeへ局所化される一方、Game所有NodeをNode APIから直接変更すると
保存用`BuildRequest`とstate versionは更新されない。Game集約内の変更は必ずGame APIを使う。
