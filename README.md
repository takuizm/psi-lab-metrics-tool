# PSI Lab Metrics Tool - ウェブサイト速度計測ツール

**簡単操作でウェブサイトの表示速度を自動計測！**

Google PageSpeed Insights を使って、複数のウェブサイトの表示速度を一括で計測し、結果をCSVファイルで保存するツールです。

## 特徴

- **ダブルクリックで実行** - 複雑なコマンド操作は不要
- **一括計測** - 複数サイトをまとめて計測
- **モバイル・デスクトップ対応** - 両方の速度を測定
- **Excel対応** - 結果はCSVファイルで保存
- **定期実行** - 自動で継続監視が可能

## 取得できるデータ
- **Onload**: ページの読み込み完了時間
- **TTFB**: サーバーからの最初の応答時間
- **LCP**: 最大コンテンツの表示時間
- **CLS**: レイアウトのずれ具合
- **Speed Index**: 表示速度の総合指標

---

## セットアップ（初回のみ）

### 事前準備チェック
- パソコンに **Python 3.8 以上** が入っている（入っていなければ以下の手順で準備）
- Google Cloud Console にアクセスできる Google アカウントがある
- 計測したいサイト一覧を Excel で編集できる

### 1. Python を準備する

#### Windows
1. [Python公式サイト](https://www.python.org/downloads/) を開きます。
2. 「Download Python ○○」をクリックしてインストーラーを保存します。
3. インストーラーを起動し、**必ず** 「Add Python to PATH」にチェックをつけてからインストールします。

#### macOS
- Homebrew がある場合：ターミナルで `brew install python` を実行します。
- Homebrew がない場合：[Python公式サイト](https://www.python.org/downloads/) から `.pkg` ファイルをダウンロードしてインストールします。

### 2. ツールを初期化する

1. ダウンロードしたフォルダを任意の場所に置きます（例：`Documents/psi-lab-metrics-tool/`）。
2. Windows の方は `setup.bat`、macOS の方は `setup.sh` をダブルクリックしてツールを準備します。
   - 数分かかることがあります。黒いウィンドウが閉じたら完了です。

### 3. Google PSI API キーを取得する
1. [Google Cloud Console](https://console.cloud.google.com/) にログインします。
2. 画面左上のプロジェクトセレクタで「新しいプロジェクト」を作成します。
3. メニューから **APIとサービス → ライブラリ** を開き、「PageSpeed Insights API」を検索して有効化します。
4. 次に **APIとサービス → 認証情報** を開き、「認証情報を作成」→「API キー」を選択します。
5. 表示された API キーをコピーし、失くさないようメモ帳などに控えておきます。

### 4. 設定ファイルを整える

#### API キーを登録する
1. フォルダ内の `.env` ファイルをメモ帳（macOS はテキストエディット）で開きます。
2. `PSI_API_KEY=your_api_key_here` の `your_api_key_here` を、控えておいた API キーに置き換えて保存します。

#### 計測対象サイトを登録する
`targets.csv` を Excel で開いて計測したいサイトを入力します：
```csv
url,name,enabled,category
https://www.example.com,サンプルサイト,true,企業サイト
https://www.google.com,Google,true,検索エンジン
```

**各項目の説明:**
- `url`: 計測したいウェブサイトのURL
- `name`: サイトの名前（結果ファイルで使用）
- `enabled`: 計測するかどうか（`true`=する、`false`=しない）
- `category`: サイトの分類（任意）

必要に応じて `priority` 列（例：`high` / `medium` / `low`）を追加すると、結果の並べ替えに使えます。

---

## 実行方法

#### Windows の場合
`run.bat` をダブルクリック

#### Mac の場合
`run.sh` をダブルクリック

メニューから実行方法を選択：
- **[1]** モバイル + デスクトップ両方（推奨）
- **[2]** モバイルのみ
- **[3]** デスクトップのみ
- **[4]** ドライラン（設定確認のみ）

**ヒント:** ドライランは API の利用回数を消費せず、設定や対象リストの確認だけ行えます。初回はドライランでエラーが出ないかチェックすると安心です。

### 実行時間の目安
- 1サイト: 約30秒〜1分
- 10サイト: 約5分〜10分

### 並列実行オプション
`config/config.yaml` の `execution` セクションで `parallel: true` に設定すると、ターゲットと戦略の組み合わせをワーカースレッドで並列処理できます。`max_workers` を指定すると上限を制御できます（未設定時はCPUコア数に応じて最大4ワーカー）。レート制限の影響を受けやすいので、まずは小さな値（2〜3）で試してAPIクォータの消費量を確認してください。サーバーやネットワーク負荷が高い場合は `parallel: false` に戻すと安全です。

> **注意**: 並列設定を有効にすると Google API の無料枠を早く使い切る可能性があります。定期運用前に少数のサイトで挙動を確認してください。

---

## 結果の確認

### 出力ファイル
```
psi-lab-metrics-tool/
  output/
    csv/
      psi_metrics.csv        ← メインの結果ファイル
    json/
      サイト名_mobile_日時.json   ← 詳細データ
      サイト名_desktop_日時.json
  logs/
    execution.log          ← 実行ログ
```

### CSV結果の見方

Excelで `output/csv/psi_metrics.csv` を開くと以下のような表になります：

| site_name | strategy | onload_ms | ttfb_ms | lcp_ms | cls | speed_index_ms |
|-----------|----------|-----------|---------|---------|-----|----------------|
| Google | mobile | 1500 | 200 | 2000 | 0.05 | 1800 |
| Google | desktop | 800 | 150 | 1000 | 0.02 | 900 |

**各列の意味:**
- `site_name`: サイト名
- `strategy`: mobile（モバイル）またはdesktop（デスクトップ）
- `onload_ms`: ページ読み込み完了時間（ミリ秒）
- `ttfb_ms`: サーバー応答時間（ミリ秒）
- `lcp_ms`: 最大コンテンツ表示時間（ミリ秒）
- `cls`: レイアウトシフト（小さいほど良い）
- `speed_index_ms`: 速度指標（小さいほど良い）

### 数値の目安
- **Onload**: 2秒未満が良い、4秒以上は改善要
- **LCP**: 2.5秒未満が良い、4秒以上は改善要
- **CLS**: 0.1未満が良い、0.25以上は改善要

---

## よくある質問・トラブルシューティング

### セットアップ時

#### 「Python が見つかりません」
**原因**: Python がインストールされていない、またはPATHが通っていない
**解決方法**:
1. Python を再インストール
2. インストール時に「Add Python to PATH」にチェック
3. コンピューターを再起動

#### 「ライブラリのインストールに失敗」
**原因**: ネットワーク接続の問題、または権限不足
**解決方法**:
1. インターネット接続を確認
2. Windows: 管理者権限で実行
3. Mac: `sudo` を使用

### 実行時

#### 「PSI APIキーが設定されていません」
**原因**: `.env` ファイルのAPIキーが正しく設定されていない
**解決方法**:
1. `.env` ファイルを開く
2. `PSI_API_KEY=` の後に正しいAPIキーを入力
3. ファイルを保存

#### 「Rate limit exceeded」（レート制限）
**原因**: Google APIの利用制限に達した
**解決方法**:
1. しばらく時間をおいてから再実行
2. 計測対象を減らす
3. 実行頻度を下げる

#### 「計測対象ファイルが見つかりません」
**原因**: `targets.csv` が存在しない、または形式が間違っている
**解決方法**:
1. `targets.csv` ファイルが存在するか確認
2. CSV形式が正しいか確認（最低限 `url,name` の列が必要）

#### 「数値が他のツールと違う」
**原因**: 計測条件（ネットワーク、地域）が異なるため、差が出るのは正常です

---

## 定期実行の設定

### Windows（タスクスケジューラ）
1. タスクスケジューラを開く
2. 基本タスクの作成
3. 毎日・毎週などのスケジュールを設定
4. プログラム: `C:\path\to\run.bat` を指定

### Mac（cron）
```bash
# ターミナルで実行
crontab -e

# 毎日午前2時に実行する場合
0 2 * * * /path/to/run.sh
```

---

## Excel でのデータ分析

### 基本的な分析
1. `output/csv/psi_metrics.csv` をExcelで開く
2. **データ** → **テーブルとして書式設定** でテーブル化
3. **挿入** → **グラフ** でパフォーマンストレンドを可視化
4. **データ** → **フィルター** で特定サイトや期間に絞り込み

### 複数回実行での精度向上
1. 朝・昼・夜など時間を変えて3回実行
2. 結果をExcelで開いて平均値を計算
3. 異常値（極端に大きい・小さい値）を除外

### カテゴリ別分析
`targets.csv` の `category` 列を活用：
```csv
url,name,enabled,category
https://www.company-a.com,A社,true,企業サイト
https://www.company-b.com,B社,true,企業サイト
https://www.shop-x.com,X店,true,ECサイト
```
Excelのピボットテーブルでカテゴリ別の平均値を算出できます。

---

## プロジェクト構成

```
psi-lab-metrics-tool/
├── setup.bat / setup.sh     # セットアップスクリプト
├── run.bat / run.sh         # 実行スクリプト
├── targets.csv              # 計測対象URL一覧
├── README.md                # このファイル（使用方法）
├── requirements.txt         # Python依存関係
├── requirements-dev.txt     # 開発用ツール（pytest, black など）
├── config.example.yaml      # 設定テンプレート
├── .env.example             # 環境変数テンプレート
├── src/                     # ソースコード
├── config/                  # 設定ファイル
├── output/                  # 結果出力先
├── logs/                    # 実行ログ
├── tests/                   # 自動テスト
└── docs/                    # 技術ドキュメント
```

---

## 今すぐ始める

1. `setup.bat` (Windows) または `setup.sh` (Mac) をダブルクリック
2. Google Cloud Console でPSI APIキーを取得
3. `.env` ファイルにAPIキーを設定
4. `targets.csv` で計測対象URLを設定
5. `run.bat` または `run.sh` で実行

開発者は仮想環境を有効化した上で `pip install -r requirements-dev.txt` を実行し、`pytest --maxfail=1 --disable-warnings` や `black src tests` で品質を維持してください。

## サポート

- **ログ確認**: `logs/execution.log`
- **技術仕様**: [docs/](./docs/) フォルダ内のドキュメント

---

**最終更新**: 2025年10月13日
**作成者**: Takuya Koizumi
