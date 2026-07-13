# データ・設定リファレンス

## 管理対象データ

| ファイル | 内容 |
| --- | --- |
| `parts_catalog.json` | Motherboard、CPU、Memory、Storage、GPU、NIC、Cable |
| `workloads.json` | NodeローカルWorkとApplication Server親Workのプロファイル |
| `runtime_config.json` | コード駆動シミュレーションの構成と生成間隔 |

これらは`importlib.resources`でパッケージ内から読みます。各loaderは任意の外部Pathも
受け取れるため、テストや別構成に差し替えられます。モジュールimport時に既定カタログが
読み込まれるため、不正なJSONは起動時エラーになります。

## runtime_config

`simulation`は必須です。`hardware`または`infrastructure`を指定できます。
`infrastructure`があれば複数Node、`hardware`があれば単体HardwareModule、どちらもなければ
既定Application Serverを生成します。

## Workload範囲

各Requirement値は要素数2の配列で、両端を含む整数範囲です。未知のRequirement種別、
空のカタログ、不正な型は読み込み時に拒否されます。

## プレイ用Workload実行計画

`workloads.json`の`profiles`は従来どおりコード駆動モデル向けのNodeローカルWorkを定義します。
プレイ用profileは別の`application_profiles`配列に置き、Application Serverの親Workを次の
最小構造で定義します。従来の`infrastructure_profiles`はこの形式へ置き換えます。

```json
{
  "application_profiles": [
    {
      "kind": "ai-training",
      "application": {
        "pre": {
          "network": {"ingress": [10, 20], "egress": [0, 0], "connections": [1, 1]},
          "cpu": {"required_clocks": [100, 200], "clock_usage_hz": [100, 200]}
        },
        "delegations": [
          {
            "role": "gpu_worker",
            "requirements": {
              "memory": {"capacity": [512, 1024]},
              "gpu": {"compute": [1000, 2000], "memory": [256, 512]}
            }
          }
        ],
        "post": {
          "network": {"ingress": [0, 0], "egress": [10, 20], "connections": [1, 1]}
        }
      }
    }
  ]
}
```

`pre`と`post`はApplication Serverで消費するRequirement、`delegations`の各
`requirements`は対象backendで消費するRequirementです。委譲先は`role`で必ず明記し、
Requirementから推測しません。`role`には`database_server`、`gpu_worker`、`storage_server`を
指定できます。特定Nodeへ固定する場合だけ任意の`node`を追加します。

`delegations`は空でもよく、その場合はApplication Server内でpre、postを実行します。
`pre`または`post`を省略した場合、そのphaseは実行しません。存在するphaseのRequirement mapは
空にできません。範囲値の検証規則は従来と同じです。Application Server自身は配置データへ
記述せず、Gameが`application_server` RoleのNodeからID順で選びます。

## セーブデータ

`ComputeTycoonGame`の既定保存先は`hardware_sim/data/save_game.json`です。このファイルは
実行時生成物なのでGit管理しません。保存対象はversion、Inventory、NodeのBuildRequest、
Cable、InterfaceAddress、RouteEntryです。実行中Work、Device使用率、EventLogは保存しません。

書き込みは`.tmp`へJSONを作成してから置換するため、途中状態を本体ファイルへ露出しません。
置換までに失敗した場合は既存の本体ファイルを維持し、未完成の`.tmp`を削除してエラーを
呼び出し元へ返します。

現在の保存形式versionは整数`1`です。読み込みはNodeを生成する前にversionを検証し、versionが
欠落したデータ、対応外version、破損したJSONや不正な保存項目を`SaveDataError`で拒否します。
復元したInventory、Node、NetworkTopologyは全項目の検証と生成が成功した場合だけGameへ
反映します。途中で失敗した場合は読み込み中に生成したNodeを停止し、部分状態を公開しません。
