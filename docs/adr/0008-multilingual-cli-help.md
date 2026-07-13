# ADR-0008: 多言語CLI Helpを表示層で管理する

- 状態: 採用
- 日付: 2026-07-13

## 文脈

従来のCLI Helpは`cmd.Cmd`がコマンド名とdocstringをアルファベット順に列挙しており、購入、
Node構築、Topology設定、Workload実行というGameの操作体系を伝えていない。また、Helpを
日本語化するためにコマンド文字列やDomain層のメッセージまで翻訳すると、入力構文や保存値、
failure codeの安定性を損ない、`TycoonShell`が表示adapterであるという境界も崩れる。

LocaleをGameの保存対象にすると、表示設定の変更で`state_version`が進み、Snapshot schemaと
load処理にもCLIだけの関心事が入り込む。

## 決定

起動メッセージとHelpだけを最初の多言語化対象とし、英語 (`en`) と日本語 (`ja`) を提供する。
LocaleはCLI entrypointで一度だけ解決し、`TycoonShell`から`ShopShell`、`BuildShell`、
`NodeShell`へ明示的に渡す。Domain objectとGame APIへlocaleやtranslatorを渡さない。

Localeの選択優先順位は、明示的な`--lang`、`COMPUTE_TYCOON_LANG`環境変数、OS locale、英語の
順とする。大文字小文字、`_` / `-`、encoding suffix、地域tagを正規化して基底言語を選ぶ。
明示した未対応localeは利用可能な値を示して起動を拒否する。環境変数またはOSの未対応値と
取得失敗は英語へfallbackする。翻訳項目の欠落も項目単位で英語へfallbackする。

Helpの正本は順序付きの構造化metadataとする。Metadataはコマンドkeyword、alias、全構文、
カテゴリ、例、翻訳対象文章のmessage keyを分ける。コマンドkeyword、構文、placeholder、ID、
enum値、catalog値は全localeで同一にする。翻訳辞書は英語を完全な基準とし、日本語を対応させる。
Help表示をmetadataへ集約し、docstringと翻訳済みHelp本文を別々の正本にしない。

情報量は、短い起動案内、目的別に分類した引数なし`help`、完全な構文と説明を示す
`help COMMAND`の3段階に分ける。トップレベルは「購入と組み立て」「Nodeの管理」
「Topologyの設定と確認」「Workloadの実行と観測」「Session」に分類する。別モードのHelpは
そのモードのコマンドだけを示す。Aliasは正規コマンドとまとめ、`EOF`は一覧に表示しない。

コマンド実行結果、EventLog、Workload結果、警告、エラーはこの決定の翻訳対象に含めない。
Localeは`RuntimeConfig`、Game Snapshot、保存データ、`state_version`へ追加しない。

## 結果

利用者は起動直後に最初の行動を理解でき、必要に応じてカテゴリ一覧と個別構文へ進める。
日本語Helpでも入力するコマンドとDomain値は既存の英語表現を保つため、互換性を維持できる。
Localeを表示層に閉じ込めることで、保存互換性とDomain APIは影響を受けない。

一方、Help metadataと翻訳辞書へコマンド追加を反映する必要がある。公開コマンドのカテゴリ所属、
英語の全message key、日本語の翻訳範囲、全localeで同じ構文をcontract testで検証する。
Help以外の出力を翻訳する場合やlocaleを次回起動へ永続化する場合は、表示文の所有者、エラーの
安定性、設定保存先を改めて決定する。
