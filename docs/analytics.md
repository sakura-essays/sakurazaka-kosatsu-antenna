# 読者行動の計測（2026-11-14仕様）

対象：プロパティ562867721 / G-48Y73ZJHVL。仕様切替前のデータは遡って修復しない。

## 運営者・検証アクセス

管理に使う各ブラウザで公開サイトの `?analytics=off` を一度開く。そのブラウザでは全ページでGoogleタグを読み込まず、設定はlocalStorageに保持する。再開は `?analytics=on`。ブラウザのデータ消去・別端末・別ブラウザには引き継がれない。地域による除外はしない。

`?analytics=test` ではサイト操作から生成されたイベントをページ下部に表示し、Googleには送信しない。設定自体は保存しない。自動操作ブラウザ（navigator.webdriver）、本番以外のホスト・パスも送信しない。これはすべてのボットを識別する仕組みではない。

## PVと主要成果

- `page_view` は物理的なページ読込につき1回。history.pushStateでの条件変更・画面切替では増やさない。
- `site_view` は記事/書き手一覧/掲載方針などの表示切替。`filter_change`は絞り込み・並び順変更。
- 記事送客は `article_click` のみで集計。標準 `click` と足さない。
- `article_impression` はクリック可能な記事リンクの50%以上が1秒間表示された場合。同じ画面・条件・記事・表示場所では物理的な読込内1回。実際に読んだ保証ではない。
- `placement`: list / pickup / random / related / author_page / song_index。
- 記事クリックにarticle_id、article_title、author_id、author_name、article_groupと、検索状態・結果件数・選択グループ・並び順を付ける。通常クリック、修飾キー付きクリック、中クリックに対応。ブラウザのコンテキストメニュー・長押しから開く動作は保証しない。

## 検索・機能

- 記事検索：`view_search_results`。入力後750ms、送信、または記事クリック直前に確定。変化のない同一検索の重複送信を抑える。
- 書き手検索：`writer_search`。同じ規則。`search_scope`がauthors/articlesを区別。
- `result_count`は検索結果全件、`zero_results`はtrue/false文字列。
- `search_active`は検索語あり/なし。検索語は100文字まで。メールアドレス、URL、電話番号のような文字列は `[redacted]`。
- 生のURL検索文字列はpage_locationに送らず、UTMのみ制限付きで引き継ぐ。リンク先は登録済みの公開記事URL。
- `random_draw` / `random_shuffle` / `writer_shuffle` / `pickup_open` / `related_open` を記録。
- `measurement_version=20261114` で旧仕様と分ける。

## GA4管理画面

拡張計測：履歴変更によるPV、自動サイト内検索、自動フォーム操作をオフ。物理PV、スクロール、標準外部クリック等は維持。独自コードの物理PVはconfigのsend_page_view:falseで一重にする。

登録するイベントスコープのカスタムディメンション：placement、author_name、article_title、article_group、site_view、filter_group、search_active、search_scope、zero_results、sort_order、measurement_version。search_termとlink_urlは標準ディメンションを使う。result_countは標準単位のイベントスコープのカスタム指標「検索結果件数」として登録した。

GA4の既存Internal Trafficフィルタはテスト状態を維持。自己アクセスは各端末の送信停止で除く。Production hostname audit（sakura-essays.github.io完全一致・次のみを含む）をテスト状態で追加し、判定の監査に使用できるようにした。GA4側で不可逆にデータを捨てるフィルタは有効にしていない。本番以外からの新コードの送信はクライアント側ホスト検査で停止する。

## 分析の分母

- セッション当たり記事クリック：article_clickイベント数 / セッション数。
- 記事選択セッション率：article_clickのあるセッション / 全セッション。
- 検索後選択率は検索イベントと後続記事クリックを同一セッション内で連結し、単なるイベント数の割算を使わない。
- ピックアップの表示後クリックを評価するときはplacementで絞り、記事別の表示・クリックを照合。click / impressionは厳密な人物別CTRではなくイベント比率。長押し等で分子の欠測はあり得る。
- 人数・セッションを地域行・新規再訪行から足さない。Cookie・同意・遮断・処理遅延・位置推定の限界は残る。
- 全セッションの完全なイベント列や厳密な多記事クリック率の再構築には、探索の適切な条件または別途BigQuery等の生データ連携が必要。今回クラウド課金や新規データエクスポートは設定していない。

## 確認

`python3 -m unittest discover -s tests -v`、`python3 scripts/build.py --public`、`python3 scripts/check_release.py`。
GA4の独自項目のレポート反映は登録後24～48時間程度。テスト画面のイベント表示はGoogleでの受信を保証するものではない。

## 公開処理

Web・計測・ビルドだけのpushは保存済み記事から公開し、RSS全件収集を待たない。定期実行、手動実行、configまたは収集・管理ロジック変更時は従来どおり収集する。計測のデプロイと記事取得の負荷を分ける。
