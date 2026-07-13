# ワークロード実行

## 生成と実行計画

`WorkloadCatalog`は`hardware_sim/data/workloads.json`を読み込みます。各要求量は
`[最小値, 最大値]`から実行時に乱数で選ばれます。`profiles`はコード駆動モデル向けの
NodeローカルWork、`application_profiles`はプレイ用の親Work実行計画です。

- Nodeローカル: `WorkInfo`を生成
- プレイ用: Application Serverの親Workと、明示されたphaseから実行計画を生成

要求は`ResourceRequirements`に格納され、CPU、Memory、Storage、GPU、Networkの
型付きRequirementとして取得されます。Executorは存在する要求だけを処理します。

プレイ用WorkloadではApplication Serverが常に入口です。親Workの計画は次の順序を持ちます。

1. `pre`: Application Server上の前処理
2. `delegations`: Database Server、GPU Worker、Storage Serverへ同期委譲する0個以上の子Work
3. `post`: すべての子が完了した後のApplication Server上の後処理

各phaseのRequirementと各子の対象Roleはカタログに明記します。CPUやStorageなどの
Requirementは複数Roleで利用されるため、Requirementの種類から対象Roleを推測しません。
子Workは通常の`WorkInfo`であり、backendから別の子を委譲できません。

役割ごとのRequirementとDevice操作の順序は`domain-model.md`のノード役割表に従います。
Network Requirementは受信と送信、Storage Requirementは読取と書込の各操作に対応し、
要求量がない操作は飛ばします。

## デバイス時間モデル

| デバイス | 所要時間・競合 |
| --- | --- |
| CPU | required clocks ÷ 割当Hz。必要コア数が空くまで待つ |
| Memory | 容量を一時確保。空き容量が不足すれば待つ |
| Storage | latency + amount ÷ speed。queue depthをSemaphoreで制限 |
| GPU | compute ÷ FLOPS。GPU memoryが空くまで待つ |
| NIC | latency + amount ÷ bandwidth。queue depthを制限 |

Memoryは処理終了時に解放され、Storage書き込み量は永続的な使用容量になります。
容量を超える要求は`ResourceCapacityError`です。Workが処理途中で失敗した場合も、Workが
一時的に確保したMemory、Deviceの実行枠、キュー深度などの資源は`finally`相当の経路で
必ず解放します。永続的なStorage書き込みなど、完了済み操作の効果は一時資源に含みません。
失敗したDevice操作以降の役割処理は実行しません。

親Workではpre、各子、postを別々の資源phaseとして扱います。preのMemoryなどの一時資源は
委譲を開始する前に必ず解放します。Application Serverは子を待つ間Device資源を保持せず、
子がすべて成功した後にpost用の資源を改めて取得します。各phase内の処理順序は
`domain-model.md`の対象Roleの順序に従います。

## 同期委譲

Application ServerのNode workerは親Workを`running`へ移してからRoleExecutorを呼びます。
RoleExecutorがpre、同期委譲、postを終えて戻るまで、親Workは同じNode上で`running`です。
子がqueuedまたはrunningの間も親はrunningであり、Application Serverのworkerを1つ占有します。

RoleExecutorはNodeへ注入されたdispatcherへ子の実行を要求します。dispatcherの実装と配置は
Gameが所有し、次の規則で実行します。

1. Nodeが明示された子は、そのNodeの存在とRoleを検証する。失敗時にfallbackしない。
2. Roleだけが指定された子は、そのRoleのNodeをNode ID昇順で調べる。
3. 親Application ServerからTopologyで到達できる最初のNodeを選ぶ。
4. 経路を両NodeのEventLogへ記録し、子Workを投入する。
5. `Node.wait_for(child)`でその子だけの終端状態を待つ。

委譲元は親を実行中のApplication Serverです。複数の子があっても、各経路は直前のbackendでは
なく同じApplication Serverから解決します。自己委譲、backendからの再委譲、到達不能Nodeへの
投入は行いません。GameのRLockといずれのNodeのConditionも、子の完了待ち中は保持しません。
`wait_all()`は無関係なWorkも待つため、同期委譲には使用しません。

preが失敗した場合は子を実行しません。子の配置、経路、Node実行のいずれかが失敗した場合は
残りの子と通常のpostを実行せず、親をfailedにします。postが失敗した場合は完了済みの子結果を
維持したまま親をfailedにします。失敗時専用cleanup phaseは持たず、各phaseの`finally`経路による
一時資源解放だけを必ず行います。

## 構造化結果

`ComputeTycoonGame.run_workload()`は表示文字列ではなく1つの`WorkloadResult`を返します。

- `WorkloadResult`: `kind`、`status`、`failure`、要求された順の`jobs`
- `JobResult`: `id`、`status`、`failure`、Application Serverの`root`
- `StepResult`: `work_id`、`role`、`node_id`、`status`、`phase`、`route`、`children`、`failure`
- `FailureReason`: 安定した`code`と人向けの`message`

親`StepResult.children`に委譲を試みた子`StepResult`を順番に格納します。配置または経路の失敗で
投入されなかった子は`work_id`を持たなくても、失敗した子Stepとして残します。未試行の後続子は
結果へ追加しません。どの階層でもcompletedでは`failure`がなく、failedでは必ず`failure`が
あります。Jobは親Stepの理由、Workloadは要求順で最初に失敗したJobの理由を伝播します。
入口Application Serverがない場合も`node_id`のない失敗した親Stepを作り、JobとWorkloadへ
`no_ingress`を伝播します。

安定した失敗codeは少なくとも`no_ingress`、`node_not_found`、`role_mismatch`、
`no_eligible_node`、`route_unreachable`、`node_execution_failed`、`delegation_failed`です。
生のExceptionは結果へ格納しません。子失敗時は子固有の理由を維持し、親は
`delegation_failed`、JobとWorkloadはfailedになります。複数Jobのうち1つが失敗しても、後続Jobを
続け、全Jobの結果を同じ`WorkloadResult`へ格納します。

Nodeは受け付けた個別Workについてqueued、running、completed、failedを観測でき、
`wait_for(work)`はそのWorkがcompletedまたはfailedになったときだけ`NodeWorkResult`を返します。
他のqueuedまたはrunning Workの完了は待ちません。

## 観測

DeviceとNodeは不変Snapshotを返します。`HardwareMonitor`は別スレッドで周期取得し、
使用率、累積処理量、キュー、成功・失敗数を表示します。Snapshotは保存データではなく
実行中状態の観測用です。
