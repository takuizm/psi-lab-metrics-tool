#!/bin/bash

echo "=========================================="
echo "  PSI Lab Metrics Tool - Setup (Mac/Linux)"
echo "=========================================="
echo

# Python インストール確認
if ! command -v python3 &> /dev/null; then
    echo "Python3 が見つかりません"
    echo
    echo "Python 3.8以上をインストールしてください："
    echo "Mac: brew install python"
    echo "または https://www.python.org/downloads/"
    echo
    exit 1
fi

echo "Python が見つかりました"
python3 --version

# 仮想環境作成
echo
echo "仮想環境を作成しています..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "仮想環境の作成に失敗しました"
    exit 1
fi

# 仮想環境有効化
echo
echo "仮想環境を有効化しています..."
source venv/bin/activate

# pip アップグレード
echo
echo "pip をアップグレードしています..."
python -m pip install --upgrade pip

# 依存関係インストール
echo
echo "必要なライブラリをインストールしています..."
pip install requests>=2.28.0 PyYAML>=6.0 pandas>=1.5.0 click>=8.1.0 python-dotenv>=0.19.0

if [ $? -ne 0 ]; then
    echo "ライブラリのインストールに失敗しました"
    exit 1
fi

# ディレクトリ作成
echo
echo "必要なディレクトリを作成しています..."
mkdir -p config output/json output/csv logs src

# 設定ファイルコピー
echo
echo "設定ファイルを準備しています..."
if [ ! -f "config/config.yaml" ]; then
    cp config.example.yaml config/config.yaml
    echo "config.yaml を作成しました"
fi

if [ ! -f "config/targets.csv" ]; then
    cp targets.csv config/targets.csv
    echo "targets.csv を作成しました"
fi

# 環境ファイル作成
echo
echo "環境設定ファイルを作成しています..."
if [ ! -f ".env" ]; then
    echo "PSI_API_KEY=your_api_key_here" > .env
    echo ".env ファイルを作成しました"
fi

# 実行権限付与
chmod +x run.sh

echo
echo "=========================================="
echo "  セットアップ完了！"
echo "=========================================="
echo
echo "次のステップ："
echo
echo "1. Google Cloud Console でPSI APIキーを取得"
echo "   https://console.cloud.google.com/"
echo
echo "2. .env ファイルを開いてAPIキーを設定"
echo "   PSI_API_KEY=あなたのAPIキー"
echo
echo "3. targets.csv を開いて計測対象URLを設定"
echo
echo "4. ./run.sh を実行"
echo "   または run.sh をダブルクリック"
echo
echo "=========================================="
