# CLAUDE.md - PSI Lab Metrics Tool

## プロジェクト概要

PageSpeed Insights (PSI) API と sitespeed.io を使用して Web ページのパフォーマンスメトリクスを収集・分析する CLI ツールです。

**2つの計測エンジン:**
- **PSI**: Google のラボデータ、Core Web Vitals 対応（APIキー必要）
- **sitespeed.io**: 詳細な Waterfall 分析、ローカル計測（Docker で実行、APIキー不要）

## 技術スタック

- **言語**: Python 3.8+
- **CLI フレームワーク**: Click
- **HTTP クライアント**: requests
- **データ処理**: pandas
- **設定管理**: PyYAML, python-dotenv
- **ローカル計測**: sitespeed.io (Docker)

## ディレクトリ構造

```
psi-lab-metrics-tool/
├── scripts/                    # 実行スクリプト
│   ├── setup.sh / setup.bat    # 初期セットアップ
│   └── run.sh / run.bat        # 計測実行
├── config/                     # 設定ファイル
│   ├── config.yaml             # メイン設定
│   └── config.example.yaml     # 設定テンプレート
├── input/                      # 入力データ
│   └── targets.csv             # 計測対象URL一覧
├── output/                     # 結果出力先
│   ├── csv/                    # CSVメトリクス
│   ├── json/                   # PSI詳細データ
│   ├── sitespeed/              # sitespeed.io詳細レポート
│   └── waterfall/              # Waterfall JSON
├── logs/                       # 実行ログ
├── src/                        # ソースコード
│   ├── cli/                    # CLI エントリポイント
│   │   ├── psi_main.py         # PSI 計測 CLI
│   │   └── sitespeed_main.py   # sitespeed.io 計測 CLI
│   ├── clients/                # API/CLIクライアント
│   │   ├── psi_client.py       # PSI API 呼び出し
│   │   └── sitespeed_client.py # sitespeed.io 連携
│   ├── extractors/             # データ抽出
│   │   ├── metrics_extractor.py    # PSI レスポンス解析
│   │   ├── sitespeed_extractor.py  # sitespeed 結果解析
│   │   └── waterfall_extractor.py  # ウォーターフォール解析
│   ├── io/                     # 入出力
│   │   ├── config_manager.py   # YAML 設定と環境変数管理
│   │   ├── csv_loader.py       # targets.csv の検証・読込
│   │   └── output_manager.py   # CSV/JSON 出力
│   └── utils/                  # ユーティリティ
├── tests/                      # 自動テスト
└── docs/                       # 技術ドキュメント
```

## 開発コマンド

```bash
# 仮想環境の有効化
source venv/bin/activate

# PSI 計測の実行
python -m src.cli.psi_main --strategy both

# sitespeed.io 計測の実行（Docker モード）
python -m src.cli.sitespeed_main --docker

# ドライラン（API 消費なし）
python -m src.cli.psi_main --dry-run --strategy mobile

# 特定のターゲットCSVを指定
python -m src.cli.psi_main --targets-csv input/targets_test.csv

# テスト実行
pytest --maxfail=1 --disable-warnings

# カバレッジ付きテスト
pytest --cov=src --cov-report=term-missing

# コードフォーマット
black src tests
flake8 src tests
```

## 環境変数

`.env` ファイルで管理（`.gitignore` 対象）：

```
PSI_API_KEY=your_api_key_here
```

**注**: sitespeed.io は Docker コンテナ内で実行されるため、APIキー不要です。

## 設定ファイル

`config/config.yaml` で管理：

```yaml
input:
  targets_csv: "./input/targets.csv"

output:
  json_dir: "./output/json"
  csv_file: "./output/csv/psi_metrics.csv"

sitespeed:
  docker: false  # true にすると Docker モードで実行
  docker_image: "sitespeedio/sitespeed.io:latest"
```

## 注意事項

- `.env` は絶対にコミットしない
- `logs/execution.log` 共有時は URL をマスク
- API レート制限に注意（`config.yaml` で並列数調整）
- sitespeed.io 使用時は Docker が必要

## 参照

- [AGENTS.md](./AGENTS.md) - リポジトリガイドライン
- [Plans.md](./Plans.md) - タスク管理
- [README.md](./README.md) - ユーザー向けドキュメント
