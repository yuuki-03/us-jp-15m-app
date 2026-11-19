# GitHub Pages 実データ自動更新

GitHub リポジトリのルートに `index.html`, `requirements.txt`, `scripts/update_market.py`, `data/market.json`, `.github/workflows/update.yml` を同じ階層構造で配置してください。

Actions > Market Data Auto Update > Run workflow で手動テストします。Actions がコミットを push できるよう Settings > Actions > General > Workflow permissions で Read and write permissions を選択してください（組織のポリシーで不可の場合があります）。GitHub Pages の公開元が main ブランチのルートになっていることを確認してください。

`yfinance` は非公式のYahoo Finance取得ライブラリで、遅延・欠測・取得制限があります。15分ごとの実行は予定であり保証ではありません。グラフは最後に取得できた15分区間の終値を表示し、時刻は区間開始時刻です。日本株の営業日でないときは直近営業日のチャートを表示します。

このバージョンでは架空の過去実績・予測確率を無効化しています。正式な過去統計を表示するには別途、検証可能な日次履歴データと集計ロジックが必要です。
