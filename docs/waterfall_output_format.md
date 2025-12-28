# Waterfall出力フォーマット仕様

WebPageTest APIから取得したデータを、Waterfall描画ツールで利用しやすい形式に変換して出力します。

## 出力ファイル

- 場所: `output/waterfall/`
- 形式: JSON
- ファイル名: `{サイト名}_{strategy}_{timestamp}.json`

## JSONスキーマ

```json
{
  "meta": {
    "tool": "WebPageTest",
    "extracted_at": "2025-12-17T10:30:00Z",
    "test_id": "251217_ABC123",
    "run": 1,
    "url": "https://example.com/",
    "site_name": "Example Site",
    "strategy": "desktop",
    "location": "Dulles:Chrome"
  },

  "page_metrics": {
    "ttfb_ms": 150,
    "start_render_ms": 500,
    "dom_content_loaded_ms": 1200,
    "dom_complete_ms": 2500,
    "load_time_ms": 3000,
    "fully_loaded_ms": 5000,
    "fcp_ms": 600,
    "lcp_ms": 1500,
    "cls": 0.05,
    "tbt_ms": 200,
    "speed_index": 1800,
    "visual_complete_ms": 4000,
    "total_requests": 85,
    "total_bytes": 2500000,
    "connections": 12,
    "domains": 8
  },

  "milestones": [
    {"key": "ttfb", "time_ms": 150, "label": "Time to First Byte", "color": "#4CAF50"},
    {"key": "fcp", "time_ms": 600, "label": "First Contentful Paint", "color": "#FF9800"},
    {"key": "lcp", "time_ms": 1500, "label": "Largest Contentful Paint", "color": "#E91E63"},
    {"key": "dom_content_loaded", "time_ms": 1200, "label": "DOM Content Loaded", "color": "#9C27B0"},
    {"key": "load", "time_ms": 3000, "label": "Load Event", "color": "#F44336"}
  ],

  "entries": [
    {
      "index": 0,
      "url": "https://example.com/",
      "host": "example.com",
      "path": "/",
      "method": "GET",
      "status": 200,
      "status_text": "OK",
      "content_type": "text/html",
      "resource_type": "document",
      "mime_type": "text/html; charset=utf-8",
      "protocol": "h2",
      "http_version": "h2",
      "priority": "VeryHigh",

      "transfer_size": 15000,
      "content_size": 45000,
      "header_size": 500,

      "start_time": 0,
      "end_time": 180,
      "duration": 180,

      "timings": {
        "blocked": -1,
        "dns": 25,
        "connect": 35,
        "ssl": 45,
        "send": 2,
        "wait": 50,
        "receive": 23
      },

      "connection_reused": false,
      "server_ip": "93.184.216.34",
      "server_port": 443,

      "is_secure": true,
      "tls_version": "TLSv1.3",
      "tls_cipher": "TLS_AES_128_GCM_SHA256",

      "from_cache": false,
      "cache_control": "max-age=3600"
    }
  ],

  "summary": {
    "total_entries": 85,
    "by_resource_type": {
      "counts": {
        "document": 1,
        "stylesheet": 5,
        "script": 25,
        "image": 40,
        "font": 8,
        "fetch": 6
      },
      "sizes": {
        "document": 45000,
        "stylesheet": 120000,
        "script": 800000,
        "image": 1500000,
        "font": 150000,
        "fetch": 25000
      }
    },
    "timing_stats": {
      "dns": {"count": 8, "total_ms": 200, "avg_ms": 25},
      "connect": {"count": 8, "total_ms": 280, "avg_ms": 35},
      "ssl": {"count": 8, "total_ms": 360, "avg_ms": 45},
      "wait": {"count": 85, "total_ms": 4250, "avg_ms": 50}
    },
    "connection_stats": {
      "reused": 77,
      "new": 8
    },
    "cache_stats": {
      "from_cache": 0,
      "from_network": 85
    }
  }
}
```

## timingsフィールド（HAR互換）

| フィールド | 説明 | 単位 |
|-----------|------|------|
| `blocked` | キュー待ち時間 | ms |
| `dns` | DNS解決時間 | ms |
| `connect` | TCP接続時間（SSL除く） | ms |
| `ssl` | SSL/TLSハンドシェイク時間 | ms |
| `send` | リクエスト送信時間 | ms |
| `wait` | TTFB（サーバー処理時間） | ms |
| `receive` | レスポンス受信時間 | ms |

**注意**: 値が `-1` の場合は、そのフェーズが発生していない（接続再利用など）ことを示します。

## resource_type一覧

| タイプ | 説明 |
|--------|------|
| `document` | HTML文書 |
| `stylesheet` | CSSファイル |
| `script` | JavaScriptファイル |
| `image` | 画像ファイル |
| `font` | Webフォント |
| `fetch` | Fetch API/XHR (JSON) |
| `xhr` | XMLHttpRequest (XML) |
| `media` | 動画/音声 |
| `other` | その他 |

## Waterfall描画での使用方法

```javascript
// 例: 各リクエストをWaterfallバーとして描画
entries.forEach(entry => {
  const bar = {
    x: entry.start_time,
    width: entry.duration,
    segments: [
      { phase: 'dns', duration: entry.timings.dns, color: '#1abc9c' },
      { phase: 'connect', duration: entry.timings.connect, color: '#e67e22' },
      { phase: 'ssl', duration: entry.timings.ssl, color: '#9b59b6' },
      { phase: 'wait', duration: entry.timings.wait, color: '#2ecc71' },
      { phase: 'receive', duration: entry.timings.receive, color: '#3498db' }
    ]
  };
  drawWaterfallBar(bar);
});

// マイルストーン線を描画
milestones.forEach(m => {
  drawVerticalLine(m.time_ms, m.color, m.label);
});
```

## PSI vs WebPageTest 比較

| データ | PSI | WebPageTest |
|--------|-----|-------------|
| リクエスト一覧 | ✅ | ✅ |
| 開始/終了時間 | ✅ | ✅ |
| DNS時間 | ❌ | ✅ |
| TCP接続時間 | ❌ | ✅ |
| SSL/TLS時間 | ❌ | ✅ |
| TTFB（個別） | ❌ | ✅ |
| Download時間 | ❌ | ✅ |
| 接続再利用情報 | ❌ | ✅ |
| TLSバージョン | ❌ | ✅ |

## 使用例

### CLIからの実行

```bash
# デスクトップテスト
python -m src.wpt_main --config config/config.yaml

# モバイルテスト
python -m src.wpt_main --config config/config.yaml --mobile

# ドライラン
python -m src.wpt_main --config config/config.yaml --dry-run
```

### 必要な環境変数

`.env`ファイルにAPIキーを設定してください：

```bash
# .env.example を .env にコピー
cp .env.example .env

# .env を編集してAPIキーを設定
WPT_API_KEY=your_webpagetest_api_key
```

APIキーは https://www.webpagetest.org/getkey.php から取得できます。
