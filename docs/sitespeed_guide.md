# sitespeed.io Waterfall ツール ガイド

sitespeed.ioを使用して、Splunk Syntheticと同等のWaterfall詳細データを取得するツールです。

## 概要

### Splunk Syntheticとの比較

| 項目 | Splunk Synthetic | sitespeed.io |
|------|-----------------|--------------|
| ブラウザ | Chrome | Chrome / Firefox |
| DNS時間 | ✅ | ✅ |
| Connect時間 | ✅ | ✅ |
| SSL/TLS時間 | ✅ | ✅ |
| TTFB | ✅ | ✅ |
| Download時間 | ✅ | ✅ |
| HAR出力 | ✅ | ✅ |
| Waterfall画像 | ✅ | ✅ (HTML/SVG) |
| Core Web Vitals | ✅ | ✅ |
| コスト | 有料 | **無料** |

**計測値の取得元**: 両方とも同じ **Navigation Timing API / Resource Timing API** を使用

## セットアップ

### 方法1: npm（推奨）

```bash
# Node.js 18以上が必要
npm install -g sitespeed.io

# インストール確認
sitespeed.io --version
```

### 方法2: Docker

```bash
# Dockerがインストールされていれば追加インストール不要
docker pull sitespeedio/sitespeed.io

# 実行時は --docker オプションを使用
python -m src.sitespeed_main --docker
```

### インストール確認

```bash
python -m src.sitespeed_main --check
```

出力例:
```
=== sitespeed.io インストール状況 ===
sitespeed.io (ローカル): ✓ 30.0.0
Docker: ✓ Docker version 24.0.0
推奨実行方法: local
```

## 使用方法

### 基本実行

```bash
# デスクトップテスト
python -m src.sitespeed_main -c config/config.yaml

# モバイルテスト
python -m src.sitespeed_main -c config/config.yaml --mobile

# Dockerモード
python -m src.sitespeed_main -c config/config.yaml --docker
```

### ドライラン

```bash
python -m src.sitespeed_main -c config/config.yaml --dry-run
```

### 詳細オプション

```bash
# 詳細ログ
python -m src.sitespeed_main -c config/config.yaml --verbose

# 別のCSVファイルを使用
python -m src.sitespeed_main -c config/config.yaml --targets-csv ./my_targets.csv
```

## 設定 (config.yaml)

```yaml
sitespeed:
  output_dir: "./output/sitespeed"   # sitespeed.io出力ディレクトリ
  waterfall_dir: "./output/waterfall" # Waterfall JSONデータ出力先
  browser: "chrome"                   # ブラウザ (chrome, firefox)
  iterations: 1                       # 計測繰り返し回数（推奨: 3-5）
  connectivity: "native"              # 接続プロファイル
  mobile: false                       # モバイルエミュレーション
  docker: false                       # Dockerモードで実行
  timeout: 300                        # 実行タイムアウト（秒）
```

### 接続プロファイル

| プロファイル | 下り | 上り | RTT |
|-------------|------|------|-----|
| native | 制限なし | 制限なし | - |
| cable | 5 Mbps | 1 Mbps | 28ms |
| 4g | 9 Mbps | 9 Mbps | 170ms |
| 3g | 1.6 Mbps | 768 Kbps | 300ms |
| 3gfast | 1.6 Mbps | 768 Kbps | 150ms |

## 出力ファイル

### ディレクトリ構造

```
output/
├── sitespeed/           # sitespeed.io生のレポート
│   └── example_com_20241217_123456/
│       ├── pages/
│       │   └── example_com/
│       │       ├── index.html      # HTMLレポート
│       │       ├── *.har           # HARファイル
│       │       └── *.png           # スクリーンショット
│       └── ...
│
└── waterfall/           # Waterfall JSON（本ツールで生成）
    └── example_com_desktop_20241217_123456_waterfall.json
```

### Waterfall JSON形式

```json
{
  "meta": {
    "tool": "sitespeed.io",
    "url": "https://example.com/",
    "site_name": "Example",
    "strategy": "desktop",
    "browser": "chrome"
  },
  "page_metrics": {
    "ttfb_ms": 150,
    "dns_ms": 25,
    "connect_ms": 35,
    "ssl_ms": 45,
    "load_time_ms": 3000,
    "total_requests": 85
  },
  "entries": [
    {
      "url": "https://example.com/",
      "status": 200,
      "resource_type": "document",
      "start_time": 0,
      "duration": 180,
      "timings": {
        "dns": 25,
        "connect": 35,
        "ssl": 45,
        "wait": 50,
        "receive": 25
      }
    }
  ],
  "summary": {
    "total_entries": 85,
    "by_resource_type": {
      "counts": {"document": 1, "script": 25, "image": 40},
      "sizes": {"document": 45000, "script": 800000, "image": 1500000}
    }
  }
}
```

## Waterfall画像の取得

sitespeed.ioは自動的にWaterfallをHTMLレポートとして生成します。

### HTMLレポートを開く

```bash
# 生成されたレポートを開く
open output/sitespeed/example_com_*/index.html
```

### 画像として保存

1. HTMLレポートを開く
2. WaterfallセクションをスクリーンショットまたはPDF保存

または、PerfCascade（sitespeed.io内部で使用）を使ってHARから直接描画:
- https://micmro.github.io/PerfCascade/

## PSI計測との併用

```bash
# 1. PSI計測（基本メトリクス）
python -m src.main -c config/config.yaml

# 2. sitespeed.io計測（Waterfall詳細）
python -m src.sitespeed_main -c config/config.yaml
```

## トラブルシューティング

### sitespeed.ioが見つからない

```
エラー: sitespeed.ioがインストールされていません
```

**解決策:**
```bash
npm install -g sitespeed.io
# または
python -m src.sitespeed_main --docker
```

### Chromeが起動しない

**解決策:**
```bash
# Dockerモードを使用
python -m src.sitespeed_main --docker
```

### タイムアウト

```yaml
# config.yamlでタイムアウトを延長
sitespeed:
  timeout: 600  # 10分
```

## 参考リンク

- [sitespeed.io公式ドキュメント](https://www.sitespeed.io/documentation/sitespeed.io/)
- [sitespeed.io メトリクス一覧](https://www.sitespeed.io/documentation/sitespeed.io/metrics/)
- [PerfCascade (Waterfall描画)](https://github.com/micmro/PerfCascade)
- [HAR仕様](http://www.softwareishard.com/blog/har-12-spec/)
