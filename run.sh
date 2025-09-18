#!/bin/bash

echo "=========================================="
echo "  PSI Lab Metrics Tool - 実行"
echo "=========================================="
echo

# 仮想環境確認
if [ ! -f "venv/bin/activate" ]; then
    echo "セットアップが完了していません"
    echo
    echo "./setup.sh を先に実行してください"
    read -p "何かキーを押すと終了します..."
    exit 1
fi

# 仮想環境有効化
echo "環境を準備しています..."
source venv/bin/activate

# 環境変数読み込み
if [ -f ".env" ]; then
    export $(cat .env | xargs)
fi

# APIキー確認
if [ "$PSI_API_KEY" = "your_api_key_here" ] || [ -z "$PSI_API_KEY" ]; then
    echo "PSI APIキーが設定されていません"
    echo
    echo ".env ファイルを開いて正しいAPIキーを設定してください"
    echo "PSI_API_KEY=あなたのAPIキー"
    echo
    read -p "何かキーを押すと終了します..."
    exit 1
fi

# 設定ファイル確認
if [ ! -f "config/config.yaml" ]; then
    echo "設定ファイルが見つかりません"
    echo
    echo "./setup.sh を実行してセットアップを完了してください"
    read -p "何かキーを押すと終了します..."
    exit 1
fi

if [ ! -f "targets.csv" ]; then
    echo "計測対象ファイルが見つかりません"
    echo
    echo "targets.csv を作成して計測対象URLを設定してください"
    read -p "何かキーを押すと終了します..."
    exit 1
fi

echo "設定確認完了"
echo

# 実行オプション選択
echo "実行方法を選択してください："
echo
echo "[1] モバイル + デスクトップ両方を計測（推奨）"
echo "[2] モバイルのみ計測"
echo "[3] デスクトップのみ計測"
echo "[4] ドライラン（設定確認のみ）"
echo "[5] 終了"
echo
read -p "選択してください (1-5): " choice

case $choice in
    1)
        strategy="both"
        echo
        echo "モバイル・デスクトップ両方を計測します"
        ;;
    2)
        strategy="mobile"
        echo
        echo "モバイルのみ計測します"
        ;;
    3)
        strategy="desktop"
        echo
        echo "デスクトップのみ計測します"
        ;;
    4)
        strategy="both"
        dryrun="--dry-run"
        echo
        echo "ドライラン（設定確認）を実行します"
        ;;
    5)
        echo
        echo "終了します"
        exit 0
        ;;
    *)
        echo
        echo "無効な選択です"
        read -p "何かキーを押すと終了します..."
        exit 1
        ;;
esac

echo
echo "=========================================="
echo "  計測開始"
echo "=========================================="
echo

# Python実行
python -m src.main --strategy $strategy $dryrun

if [ $? -eq 0 ]; then
    echo
    echo "=========================================="
    echo "  計測完了！"
    echo "=========================================="
    echo
    echo "結果ファイル："
    echo "  - JSON: output/json/"
    echo "  - CSV:  output/csv/psi_metrics.csv"
    echo
    echo "ログファイル："
    echo "  - logs/execution.log"
    echo
else
    echo
    echo "=========================================="
    echo "  エラーが発生しました"
    echo "=========================================="
    echo
    echo "詳細はログファイルを確認してください："
    echo "  - logs/execution.log"
    echo
fi

read -p "何かキーを押すと終了します..."
