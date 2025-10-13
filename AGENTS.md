# Repository Guidelines

## プロジェクト構成とモジュール配置
実行コードは `src/` に集約されています。`main.py` がCLIの入口となり、`config_manager.py` がYAML設定と環境変数の上書きを読み込み、`csv_loader.py` が `targets.csv` の検証・読込を担当します。`metrics_extractor.py` と `output_manager.py` はPSIレスポンスをCSV/JSONへ変換し、`psi_client.py` がPageSpeed Insights API呼び出しとリトライ制御を担います。初期設定は `config/` に保存され、編集可能なターゲット一覧はリポジトリ直下の `targets.csv` で管理します。`logs/`、`output/json`、`output/csv` は自動処理が追記するため削除せずに保持し、補足ドキュメントは `docs/`、起動スクリプトはルート直下 (`setup.*`, `run.*`) に配置されています。

## ビルド・テスト・開発コマンド
マシンごとに最初の一度は `./setup.sh`（または `setup.bat`）を実行し、`venv/` の作成・依存パッケージの導入・設定ファイルの初期化を行います。以降は `source venv/bin/activate` で仮想環境を有効化し、ランタイム依存は `pip install -r requirements.txt`、開発ツールは `pip install -r requirements-dev.txt` で更新します。計測は `python -m src.main --strategy both` で直接起動するか、対話メニュー付きの `./run.sh` を利用します。API枠を消費せず設定を確認したい場合は `--dry-run` を付与し、都度別CSVを使う場合は `--targets-csv config/custom.csv` のようにパスを指定してください。大量サイトを扱う際は `config/config.yaml` 内の `execution.parallel` と `execution.max_workers` を調整し、レート制限に注意しながら並列実行を活用します。

## コーディングスタイルと命名規則
Python 3.8 以上を前提に、インデントはスペース4つ、関数や変数はスネークケース、クラスはパスカルケース、設定キーは全て大文字で統一します。既存の簡潔な日英併記ドキュメンテーション文字列は維持し、運用ログは `logging` を用いて出力します。整形には `black src tests`（行幅88）を、静的チェックには `flake8 src tests` を推奨し、いずれも仮想環境にインストールして実行してください。インポートは標準ライブラリ・サードパーティ・ローカルの順にまとめます。

## テストガイドライン
テストは `pytest` を採用し、`src/` と同じ構成を `tests/` に再現します（例: `test_metrics_extractor.py`）。プッシュ前には `pytest --maxfail=1 --disable-warnings` を実行し、カバレッジが必要な変更では `pytest --cov=src --cov-report=term-missing` を追加してください。PSIレスポンスは `tests/fixtures/` 配下にモックJSONを用意して決定的にし、生成したCSVのスキーマは `output/csv` のサンプルと照合します。

## コミットおよびプルリクエストの指針
コミットサマリは命令形で72文字以内を目安とし（例: `Add retry jitter to PSI client`）、背景説明が必要な場合は本文を追記します。プルリクエストには変更概要、ローカル検証コマンド（CLI実行・pytest・lint）の列挙、関連するIssueやチケットのリンクを含めてください。ユーザー向けの出力に影響する変更ではスクリーンショットやCSV抜粋を添付し、自動チェックが通過してからレビューを依頼します。

## セキュリティと設定に関する注意
秘密情報はコミットしないでください。`.env` はローカル管理とし、`PSI_API_KEY` は定期的にローテーションします。`config/config.yaml` を変更した際は `python -m src.main --dry-run --strategy mobile` で必須キーを事前確認します。`logs/execution.log` を共有する場合はURLやメトリクスをマスクし、チーム外へ成果物を渡す前に `output/` 内の不要ファイルを整理してください。
