# ADR-0007: Application Serverからの同期委譲

- 状態: 採用
- 日付: 2026-07-13

## 文脈

プレイ用Workloadは、Application Serverが入口のWorkを受け付け、必要な処理を
Database Server、GPU Worker、Storage Serverへ委譲する。親Workを先に完了させてから
別NodeのWorkを実行すると、Application Serverが応答を待っている状態を表現できない。
一方、NodeやRoleExecutorへTopologyと配置規則を持たせると、ローカルなDevice実行と
ゲーム全体の調整が密結合になる。

## 決定

Application Serverの親Workは、pre phase、0個以上のdelegated phase、post phaseを
この順に実行する。delegated phaseでは子Workを別Nodeへ投入してそのWorkだけを同期的に
待つ。親Workはpre開始からpost終了まで`running`であり、子を待つ間も`running`を保つ。

各phaseのRequirementとdelegated phaseの対象RoleはWorkload定義に明記し、Requirement
から委譲先を推測しない。preで確保したMemoryなどの一時資源は子を待つ前に解放し、postは
子の完了後に改めて必要な資源を確保する。

配置と経路解決は`ComputeTycoonGame`が所有する。Application ServerのRoleExecutorは
Nodeへ注入された狭いdispatcherを通してGameへ委譲を要求する。NodeとRoleExecutorは
Topologyや候補選択規則を知らない。Gameは対象RoleのNodeをID順に調べ、Application
Serverから到達できる最初のNodeを選ぶ。Nodeが明示された定義ではそのNodeだけを検証し、
失敗時に別Nodeへfallbackしない。

待機は`Node.wait_for(work)`で対象の子Workだけを待つ。NodeのCondition、GameのRLock、
pre phaseの一時資源を保持したまま待ってはならない。委譲はApplication Serverから
Database Server、GPU Worker、Storage Serverへの一方向だけとし、自己委譲と子Workからの
再委譲を認めない。

実行結果はWorkload、Job、親Step、子Stepの不変な階層値として返す。子の配置、経路、実行の
いずれかが失敗した場合、子Stepを失敗として残し、親は`delegation_failed`で失敗する。
残りの子と通常のpostは実行しない。現在は失敗時専用cleanup phaseを設けず、取得済み一時資源の
解放だけを`finally`経路で保証する。同じ`run workload`で後続Jobがあれば実行を継続する。

## 結果

親Workの待機状態と子Workの実行状態を同時に観測でき、RoleExecutorのローカルDevice処理と
Gameの配置責務を分離できる。Application Serverのworkerは子を待つ間占有されるため、
worker数が同時に待機できる親Work数の上限になる。backendからApplication Serverへ待ち戻る
経路を禁止することで、同期委譲のwait graphを非循環に保つ。
