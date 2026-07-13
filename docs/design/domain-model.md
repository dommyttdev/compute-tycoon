# ドメインモデル

## ゲーム状態

`ComputeTycoonGame`は1セッションの集約ルートです。以下を所有します。

- 購入済み資産を表す`Inventory`
- 構築済み`Node`と、その復元に必要な`BuildRequest`
- 現在の`NetworkTopology`
- `PartsCatalog`と`WorkloadCatalog`
- `EventLog`、状態バージョン、自動保存ワーカー

状態変更はゲームの`RLock`内で行い、成功後に`state_version`を増やします。

## 保存と復元

保存データはInventory、NodeのBuildRequest、NetworkTopologyを一つのGame Snapshotとして
扱います。読み込みはversionを検証した後、一時的なInventory、Node集合、BuildRequest集合、
NetworkTopologyを構築します。すべての検証と生成が成功した場合だけ、`RLock`内でGame状態を
まとめて置き換えます。

復元途中で失敗した場合はGame状態を変更せず、一時状態へ生成したNodeをすべて停止します。
保存データのversion欠落、対応外version、破損、不正な項目は`SaveDataError`として呼び出し元へ
返します。version検証はworker threadを持つNodeの生成より前に行います。

## 購入・消費・構築

完成品サーバー、部品、ケーブルは購入時にInventoryへ追加されます。完成品配置では
該当役割の在庫を1つ消費します。手動組み立てでは要求部品を検査した後、すべてを
まとめて消費します。ケーブルは接続時に消費し、切断時に戻します。

手動組み立ては次の順序です。

1. `BuildRequest`を作成する。
2. Inventoryの数量を確認する。
3. `NodeBuilder.validate()`で互換性を検査する。
4. カタログ上の構成値から実行時Deviceを作る。
5. `Node`を登録し、Topologyのノード集合を更新する。
6. Inventoryを消費し、イベントと状態変更を記録する。

## 組み立て制約

- CPUソケット型と個数
- メモリ規格、スロット数、1枚/合計容量、ECC対応
- ストレージコネクタ型と個数
- GPU・拡張NICのPCIe世代とレーン数
- CPU、メモリ、ストレージを最低1つずつ搭載

複数部品は、CPUコア数・メモリ容量・ストレージ容量/速度を合算します。CPU周波数と
ストレージ遅延は最も遅い・小さい値を採用します。

## ノード役割

`NodeRole`はExecutorを選択します。

| 役割 | RequirementとDevice処理の順序 |
| --- | --- |
| `unassigned` | 実行不可 |
| `application_server` | Network受信→Memory確保→Storage読取→CPU処理→Storage書込→Network送信 |
| `database_server` | Network受信→Memory確保→Storage読取→CPU処理→Storage書込→Network送信 |
| `storage_server` | Network受信→Storage読取→Storage書込→Network送信 |
| `network_switch` | Network受信→Network送信 |
| `router` | Network受信→CPU処理→Network送信 |
| `gpu_worker` | Memory確保→Storage読取→GPU処理→CPU処理→Storage書込 |

ExecutorはWorkに存在するRequirementだけを上表の順序で処理します。同じNetwork
Requirementを受信と送信に、同じStorage Requirementの読取量と書込量をそれぞれの
Device操作に対応させます。要求量がない操作は実行しません。

役割変更は`Node.set_role()`が所有し、Nodeの同期境界内で役割とExecutorを一体として
更新します。実際の変更はキューと実行中Workがないidle状態だけで許可します。queuedまたは
running Workがある場合、および停止済みNodeを別の役割へ変更する場合は`RuntimeError`で拒否し、
役割とExecutorを変更しません。同じ役割への設定は状態にかかわらず副作用のないno-opです。

Gameが所有するNodeは`ComputeTycoonGame.set_node_role()`から変更します。Gameは`RLock`を
取得してNodeの変更を先に成功させた後、保存用`BuildRequest`を置き換え、イベントを記録し、
`state_version`を1回増やします。Nodeの変更が拒否または失敗した場合、`BuildRequest`、イベント、
`state_version`は変更しません。

## ライフサイクル

Nodeは生成時にワーカースレッドを開始します。Nodeが受け付けた1回の実行試行では、Workは
queued→running→completedまたはfailedへ進み、その試行の終端状態から別の状態へは
遷移しません。Device処理が失敗した場合は残りの処理を行わずfailedになります。同じ
`WorkInfo`を再投入した場合の再試行や状態の再利用はこの契約の対象外です。再試行する
呼出し側は新しい`WorkInfo`を投入します。

複数workerの起動途中で後続workerの開始に失敗した場合、Nodeは先に起動したworkerを停止して
から生成失敗を返します。生成に失敗したNodeのworkerを呼び出し側へ残しません。

Workは投入を受け付けた順にキューへ入り、ワーカーはその順に取り出します。ワーカーが
1つなら実行開始順もFIFOになります。複数ワーカーでは完了順を保証しません。

`wait_all()`はキューと実行中集合の両方が空になったときだけ戻ります。`stop()`は呼出し前に
受け付けたキュー内および実行中のWorkを処理し終えてから同期的に戻ります。複数回呼び出しても
同じ停止状態を保ちます。`stop()`が戻った後の新規Work投入は、キュー、実行中集合、成功数、
失敗数を変更せず拒否します。

workerはWorkをrunningへ移すとき、同じNode同期境界内で対応するExecutorを取得します。
Role変更はbusy中に拒否されるため、1回のWork実行中は開始時のRoleとExecutorの組み合わせを
維持します。

`wait_for(work)`は、投入済みの特定Workがcompletedまたはfailedになるまで同じConditionで待ち、
そのWorkの`NodeWorkResult`を返します。他のWorkの状態は完了条件に含めません。Nodeが保持する
失敗Exceptionそのものは公開せず、安定した失敗理由へ変換します。

## Application Serverの親Work

プレイ用WorkloadはApplication Serverの親Workとして開始します。親Workはpre phaseの開始から、
同期委譲したすべての子Workの待機、post phaseの終了までrunningです。子WorkはDatabase Server、
GPU Worker、Storage Serverのいずれかで通常のNodeライフサイクルを進みます。

Application ServerのRoleExecutorはphaseの実行順を所有しますが、委譲先の選択と経路解決は
所有しません。Nodeへ注入された狭いdispatcherが要求をGameへ渡します。Nodeはdispatcherを
呼ぶ間に自身のConditionを保持しません。preで確保した一時資源はdispatcherを呼ぶ前に解放し、
postは子の成功後に新しく確保します。

委譲はApplication Serverからbackendへの一方向だけです。backend Workは子を作らず、同じ親への
待ち戻りもありません。子が失敗した場合は通常のpostを実行せず親もfailedになります。
取得済み資源の解放は各Executorの`finally`経路が行い、失敗時専用のcleanup phaseは現在持ちません。
