"""
出力管理モジュール

計測結果のJSON・CSV出力、ファイル管理を行います。
大量データ処理と効率的なファイル操作に対応。
"""

import os
import json
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import shutil

logger = logging.getLogger(__name__)


class OutputError(Exception):
    """出力関連のエラー"""
    pass


class OutputManager:
    """出力ファイル管理"""

    # デフォルト設定
    DEFAULT_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
    DEFAULT_CSV_ENCODING = "utf-8-sig"  # Excel対応
    DEFAULT_JSON_INDENT = 2

    # ファイルサイズ制限（MB）
    MAX_JSON_FILE_SIZE_MB = 50
    MAX_CSV_FILE_SIZE_MB = 100

    def __init__(self,
                 json_dir: str,
                 csv_file: str,
                 timestamp_format: str = DEFAULT_TIMESTAMP_FORMAT):
        """
        OutputManager初期化

        Args:
            json_dir: JSON出力ディレクトリ
            csv_file: CSV出力ファイルパス
            timestamp_format: タイムスタンプフォーマット
        """
        self.json_dir = Path(json_dir)
        self.csv_file = Path(csv_file)
        self.timestamp_format = timestamp_format

        # ディレクトリ作成
        self._ensure_directories()

        # 統計情報
        self.stats = {
            'json_files_created': 0,
            'csv_rows_written': 0,
            'total_data_size_bytes': 0,
            'cleanup_operations': 0
        }

        logger.info(f"OutputManagerを初期化しました")
        logger.info(f"JSON出力先: {self.json_dir}")
        logger.info(f"CSV出力先: {self.csv_file}")

    def _ensure_directories(self):
        """必要なディレクトリを作成"""
        try:
            self.json_dir.mkdir(parents=True, exist_ok=True)
            self.csv_file.parent.mkdir(parents=True, exist_ok=True)
            logger.debug("出力ディレクトリを準備しました")
        except Exception as e:
            raise OutputError(f"ディレクトリ作成エラー: {str(e)}")

    def save_json(self, data: Dict[str, Any], site_name: str, strategy: str) -> str:
        """
        JSON形式でデータを保存

        Args:
            data: 保存するデータ
            site_name: サイト名
            strategy: 計測戦略

        Returns:
            保存されたファイルパス

        Raises:
            OutputError: ファイル保存に失敗した場合
        """
        try:
            # ファイル名生成（安全な文字のみ使用）
            safe_site_name = self._sanitize_filename(site_name)
            timestamp = datetime.now().strftime(self.timestamp_format)
            filename = f"{safe_site_name}_{strategy}_{timestamp}.json"
            filepath = self.json_dir / filename

            # データサイズチェック
            json_str = json.dumps(data, ensure_ascii=False, indent=self.DEFAULT_JSON_INDENT)
            data_size_mb = len(json_str.encode('utf-8')) / (1024 * 1024)

            if data_size_mb > self.MAX_JSON_FILE_SIZE_MB:
                logger.warning(f"大きなJSONファイル ({data_size_mb:.1f}MB): {filename}")

            # ファイル書き込み
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(json_str)

            # 統計更新
            self.stats['json_files_created'] += 1
            self.stats['total_data_size_bytes'] += len(json_str.encode('utf-8'))

            logger.debug(f"JSON保存完了: {filename} ({data_size_mb:.2f}MB)")
            return str(filepath)

        except Exception as e:
            logger.error(f"JSON保存エラー {filename}: {str(e)}")
            raise OutputError(f"JSON保存エラー: {str(e)}")

    def append_csv(self, metrics: Dict[str, Any]) -> None:
        """
        CSV形式でメトリクスを追記

        Args:
            metrics: 追記するメトリクス

        Raises:
            OutputError: CSV追記に失敗した場合
        """
        try:
            df = pd.DataFrame([metrics])

            # ファイルが存在しない場合はヘッダー付きで新規作成
            if not self.csv_file.exists():
                df.to_csv(
                    self.csv_file,
                    index=False,
                    encoding=self.DEFAULT_CSV_ENCODING,
                    float_format='%.3f'  # 小数点3桁まで
                )
                logger.info(f"CSV新規作成: {self.csv_file}")
            else:
                # 既存ファイルに追記
                df.to_csv(
                    self.csv_file,
                    mode='a',
                    header=False,
                    index=False,
                    encoding=self.DEFAULT_CSV_ENCODING,
                    float_format='%.3f'
                )
                logger.debug(f"CSV追記: {self.csv_file}")

            # 統計更新
            self.stats['csv_rows_written'] += 1

            # ファイルサイズチェック
            self._check_csv_file_size()

        except Exception as e:
            logger.error(f"CSV追記エラー: {str(e)}")
            raise OutputError(f"CSV追記エラー: {str(e)}")

    def save_summary_csv(self, all_metrics: List[Dict[str, Any]],
                        filename: Optional[str] = None) -> str:
        """
        全メトリクスをサマリーCSVとして保存

        Args:
            all_metrics: 全メトリクスのリスト
            filename: ファイル名（Noneの場合は自動生成）

        Returns:
            保存されたファイルパス

        Raises:
            OutputError: ファイル保存に失敗した場合
        """
        try:
            if not all_metrics:
                raise OutputError("保存するデータがありません")

            # ファイル名生成
            if not filename:
                timestamp = datetime.now().strftime(self.timestamp_format)
                filename = f"psi_summary_{timestamp}.csv"

            filepath = self.csv_file.parent / filename

            # DataFrameに変換
            df = pd.DataFrame(all_metrics)

            # カラム順序の最適化
            ordered_columns = self._get_optimal_column_order(df.columns.tolist())
            available_columns = [col for col in ordered_columns if col in df.columns]

            # 未定義カラムを末尾に追加
            remaining_columns = [col for col in df.columns if col not in available_columns]
            final_columns = available_columns + sorted(remaining_columns)

            df = df[final_columns]

            # 大量データ処理の最適化
            if len(df) > 1000:
                logger.info(f"大量データ（{len(df)}行）をCSV保存中...")
                # チャンク単位で保存（メモリ効率化）
                chunk_size = 500
                df.iloc[:chunk_size].to_csv(
                    filepath,
                    index=False,
                    encoding=self.DEFAULT_CSV_ENCODING,
                    float_format='%.3f'
                )

                for i in range(chunk_size, len(df), chunk_size):
                    chunk = df.iloc[i:i+chunk_size]
                    chunk.to_csv(
                        filepath,
                        mode='a',
                        header=False,
                        index=False,
                        encoding=self.DEFAULT_CSV_ENCODING,
                        float_format='%.3f'
                    )
            else:
                df.to_csv(
                    filepath,
                    index=False,
                    encoding=self.DEFAULT_CSV_ENCODING,
                    float_format='%.3f'
                )

            file_size_mb = filepath.stat().st_size / (1024 * 1024)
            logger.info(f"サマリーCSV保存完了: {filename} ({len(df)}行, {file_size_mb:.2f}MB)")

            return str(filepath)

        except Exception as e:
            logger.error(f"サマリーCSV保存エラー: {str(e)}")
            raise OutputError(f"サマリーCSV保存エラー: {str(e)}")

    def _get_optimal_column_order(self, columns: List[str]) -> List[str]:
        """最適なカラム順序を取得"""
        # 重要度順にカラムを配置
        priority_columns = [
            # 基本情報
            'site_name', 'name', 'url', 'strategy', 'category', 'priority',
            'timestamp', 'row_number',

            # 主要パフォーマンスメトリクス
            'onload_ms', 'ttfb_ms', 'lcp_ms', 'cls', 'speed_index_ms',
            'fcp_ms', 'tbt_ms', 'interactive_ms',

            # 観測値
            'observed_lcp_ms', 'observed_cls', 'observed_fcp_ms',
            'observed_dom_content_loaded_ms',

            # フィールドデータ
            'field_lcp_ms', 'field_fcp_ms', 'field_cls', 'field_fid_ms',
            'field_overall_category',

            # メタデータ
            'lighthouse_version', 'form_factor', 'user_agent',
            'api_response_id', 'run_warnings_count'
        ]

        return priority_columns

    def _check_csv_file_size(self):
        """CSVファイルサイズをチェック"""
        try:
            if self.csv_file.exists():
                size_mb = self.csv_file.stat().st_size / (1024 * 1024)
                if size_mb > self.MAX_CSV_FILE_SIZE_MB:
                    logger.warning(f"CSVファイルが大きくなっています: {size_mb:.1f}MB")
                    # 必要に応じてローテーション処理を実装
                    self._rotate_csv_file()
        except Exception as e:
            logger.debug(f"CSVファイルサイズチェックエラー: {e}")

    def _rotate_csv_file(self):
        """CSVファイルのローテーション"""
        try:
            timestamp = datetime.now().strftime(self.timestamp_format)
            backup_name = f"{self.csv_file.stem}_backup_{timestamp}{self.csv_file.suffix}"
            backup_path = self.csv_file.parent / backup_name

            shutil.move(str(self.csv_file), str(backup_path))
            logger.info(f"CSVファイルをバックアップしました: {backup_name}")

        except Exception as e:
            logger.error(f"CSVファイルローテーションエラー: {e}")

    def cleanup_old_files(self, days: int = 30) -> int:
        """
        古いファイルをクリーンアップ

        Args:
            days: 保持日数

        Returns:
            削除したファイル数
        """
        deleted_count = 0
        cutoff_time = datetime.now() - timedelta(days=days)
        cutoff_timestamp = cutoff_time.timestamp()

        try:
            # JSONファイルのクリーンアップ
            for json_file in self.json_dir.glob("*.json"):
                try:
                    if json_file.stat().st_mtime < cutoff_timestamp:
                        file_size = json_file.stat().st_size
                        json_file.unlink()
                        deleted_count += 1
                        self.stats['total_data_size_bytes'] -= file_size
                        logger.debug(f"古いJSONファイルを削除: {json_file.name}")
                except Exception as e:
                    logger.warning(f"ファイル削除エラー {json_file.name}: {e}")

            # CSVバックアップファイルのクリーンアップ
            csv_backup_pattern = f"{self.csv_file.stem}_backup_*{self.csv_file.suffix}"
            for backup_file in self.csv_file.parent.glob(csv_backup_pattern):
                try:
                    if backup_file.stat().st_mtime < cutoff_timestamp:
                        backup_file.unlink()
                        deleted_count += 1
                        logger.debug(f"古いCSVバックアップを削除: {backup_file.name}")
                except Exception as e:
                    logger.warning(f"バックアップ削除エラー {backup_file.name}: {e}")

            if deleted_count > 0:
                self.stats['cleanup_operations'] += 1
                logger.info(f"クリーンアップ完了: {deleted_count}ファイルを削除")

        except Exception as e:
            logger.error(f"クリーンアップエラー: {e}")

        return deleted_count

    def _sanitize_filename(self, filename: str) -> str:
        """ファイル名を安全な文字に変換"""
        # 危険な文字を置換
        unsafe_chars = '<>:"/\\|?*'
        safe_filename = filename

        for char in unsafe_chars:
            safe_filename = safe_filename.replace(char, '_')

        # 長さ制限
        if len(safe_filename) > 100:
            safe_filename = safe_filename[:100]

        # 空白をアンダースコアに
        safe_filename = safe_filename.replace(' ', '_')

        return safe_filename

    def get_output_summary(self) -> Dict[str, Any]:
        """出力状況のサマリーを取得"""
        try:
            # JSONファイル統計
            json_files = list(self.json_dir.glob("*.json"))
            json_total_size = sum(f.stat().st_size for f in json_files if f.exists())

            # CSVファイル統計
            csv_size = self.csv_file.stat().st_size if self.csv_file.exists() else 0
            csv_rows = 0
            if self.csv_file.exists():
                try:
                    with open(self.csv_file, 'r', encoding=self.DEFAULT_CSV_ENCODING) as f:
                        csv_rows = sum(1 for _ in f) - 1  # ヘッダー除く
                except Exception:
                    csv_rows = -1  # 読み込み失敗

            return {
                'json_files_count': len(json_files),
                'json_total_size_mb': json_total_size / (1024 * 1024),
                'csv_file_exists': self.csv_file.exists(),
                'csv_file_size_mb': csv_size / (1024 * 1024),
                'csv_rows_count': csv_rows,
                'total_size_mb': (json_total_size + csv_size) / (1024 * 1024),
                'stats': self.stats.copy()
            }

        except Exception as e:
            logger.error(f"出力サマリー取得エラー: {e}")
            return {'error': str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """統計情報を取得"""
        return self.stats.copy()

    def reset_stats(self):
        """統計情報をリセット"""
        self.stats = {
            'json_files_created': 0,
            'csv_rows_written': 0,
            'total_data_size_bytes': 0,
            'cleanup_operations': 0
        }
        logger.debug("出力統計情報をリセットしました")
