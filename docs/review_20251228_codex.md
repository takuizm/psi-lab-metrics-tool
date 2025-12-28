# Codex レビュー記録 (2025-12-28)

## 1. レビュー概要
- レビュー日: 2025-12-28
- レビュアー: Codex (自動レビューエージェント)
- 対象範囲: PSI 計測 CLI (`src/cli/psi_main.py`) および Sitespeed 抽出ロジック (`src/extractors/sitespeed_extractor.py`)

## 2. 指摘内容
1. **PSI リクエスト数が失敗分を含まず過少計上される**
   - 並列・逐次処理ともに `processing_stats['total_requests']` の更新が成功経路に偏っており、API 呼び出しに失敗したターゲット分の試行がサマリーに反映されない。
2. **SitespeedExtractor の総転送量が常に 0 バイト**
   - `_calculate_page_metrics` がフラット化済みエントリの `response` ブロックにアクセスしており、実データを参照できないため `total_size` が集計されない。

## 3. 対応内容
1. **PSI リクエスト集計の修正**
   - 並列ワーカーが PSI 呼び出しを試行した時点で `request_attempted` フラグを立て、メインスレッド側で結果取得直後に `total_requests` をインクリメント。
   - `future.result()` が例外を投げた場合や逐次処理ルートでも `get_page_metrics` 実行前にカウンタを増分し、成功/失敗にかかわらず全試行を把握できるようにした。
2. **Sitespeed 総転送量集計の修正**
   - 変換済みエントリの `transfer_size` → `content_size` → 必要に応じて元 `response` の `_transferSize`/`bodySize` の順でフォールバックしてバイト数を積算。
   - ページメトリクステストに総転送量 96,000 bytes のアサーションを追加し、処理統計テストで失敗リクエストも `total_requests` に加算されることを検証。

## 4. 検証
```
PYTHONPATH=. PYTEST_ADDOPTS=--basetemp=./.pytest_tmp pytest tests/test_main_processor_parallel.py tests/test_sitespeed_extractor.py
```

上記により関連テスト 17 件がすべて成功し、修正が動作することを確認済み。最新の `pytest` 実行結果はローカルログも参照のこと。
