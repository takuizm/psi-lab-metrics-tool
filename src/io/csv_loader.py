"""
CSV読み込みモジュール

計測対象URLのCSVファイルを読み込み、検証、変換を行います。
大量データ（1000件程度）の効率的な処理に対応。
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import pandas as pd

logger = logging.getLogger(__name__)


class CSVError(Exception):
    """CSV関連のエラー"""
    pass


class CSVLoader:
    """CSV ファイルからターゲット情報を読み込み"""

    # 必須カラム
    REQUIRED_COLUMNS = {'url', 'name'}

    # オプションカラム
    OPTIONAL_COLUMNS = {'enabled', 'category', 'priority', 'description'}

    # サポートするエンコーディング
    SUPPORTED_ENCODINGS = ['utf-8-sig', 'utf-8', 'shift_jis', 'cp932']

    def __init__(self, csv_path: str, encoding: str = "utf-8-sig"):
        """
        CSVLoader初期化

        Args:
            csv_path: CSVファイルのパス
            encoding: ファイルエンコーディング
        """
        self.csv_path = Path(csv_path)
        self.encoding = encoding
        self._targets_cache: Optional[List[Dict[str, Any]]] = None
        self._last_modified: Optional[float] = None

    def load_targets(self, force_reload: bool = False) -> List[Dict[str, Any]]:
        """
        CSVファイルからターゲット一覧を読み込み

        Args:
            force_reload: キャッシュを無視して強制再読み込み

        Returns:
            ターゲット情報のリスト

        Raises:
            CSVError: CSV読み込みまたは検証に失敗した場合
        """
        try:
            # ファイル存在確認
            if not self.csv_path.exists():
                raise CSVError(f"CSVファイルが見つかりません: {self.csv_path}")

            # キャッシュチェック
            current_modified = self.csv_path.stat().st_mtime
            if (not force_reload and
                self._targets_cache is not None and
                self._last_modified == current_modified):
                logger.debug("CSVキャッシュを使用します")
                return self._targets_cache

            # CSV読み込み
            df = self._read_csv_with_encoding()

            # データ検証・変換
            targets = self._process_dataframe(df)

            # キャッシュ更新
            self._targets_cache = targets
            self._last_modified = current_modified

            enabled_count = sum(1 for t in targets if t.get('enabled', True))
            logger.info(f"CSVから {len(targets)} 件のターゲットを読み込みました "
                       f"({enabled_count} 件が有効)")

            return targets

        except Exception as e:
            if isinstance(e, CSVError):
                raise
            logger.error(f"CSV読み込み中にエラーが発生しました: {str(e)}")
            raise CSVError(f"CSV読み込みエラー: {str(e)}")

    def _read_csv_with_encoding(self) -> pd.DataFrame:
        """エンコーディングを考慮したCSV読み込み"""
        encodings_to_try = [self.encoding] + [
            enc for enc in self.SUPPORTED_ENCODINGS if enc != self.encoding
        ]

        last_error = None
        for encoding in encodings_to_try:
            try:
                logger.debug(f"エンコーディング {encoding} でCSV読み込みを試行")
                df = pd.read_csv(
                    self.csv_path,
                    encoding=encoding,
                    dtype=str,  # 全て文字列として読み込み
                    na_filter=False  # 空文字をNaNにしない
                )
                logger.debug(f"エンコーディング {encoding} で読み込み成功")
                return df
            except UnicodeDecodeError as e:
                last_error = e
                logger.debug(f"エンコーディング {encoding} で読み込み失敗: {e}")
                continue

        raise CSVError(f"サポートされているエンコーディングでCSVを読み込めませんでした。"
                      f"最後のエラー: {last_error}")

    def _process_dataframe(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """DataFrameを処理してターゲットリストに変換"""
        # カラム名の正規化（大文字小文字、空白を統一）
        df.columns = df.columns.str.strip().str.lower()

        # 必須カラムの確認
        missing_columns = self.REQUIRED_COLUMNS - set(df.columns)
        if missing_columns:
            raise CSVError(f"必須カラムが見つかりません: {missing_columns}")

        # 空行の削除
        df = df.dropna(subset=['url', 'name'], how='any')
        df = df[df['url'].str.strip() != '']
        df = df[df['name'].str.strip() != '']

        if len(df) == 0:
            raise CSVError("有効なデータが見つかりません")

        # 大量データ処理のための最適化
        if len(df) > 1000:
            logger.warning(f"大量データ（{len(df)}件）を処理します。時間がかかる場合があります。")

        targets = []
        duplicate_urls: Set[str] = set()
        seen_urls: Set[str] = set()

        for index, row in df.iterrows():
            try:
                target = self._process_single_row(row, index)

                # URL重複チェック
                url_lower = target['url'].lower()
                if url_lower in seen_urls:
                    duplicate_urls.add(target['url'])
                    logger.warning(f"重複URL（行{index + 2}）: {target['url']}")
                else:
                    seen_urls.add(url_lower)

                targets.append(target)

            except Exception as e:
                logger.error(f"行{index + 2}の処理中にエラー: {e}")
                # 個別行のエラーは警告として処理を継続
                continue

        if duplicate_urls:
            logger.warning(f"{len(duplicate_urls)} 件の重複URLが見つかりました")

        if not targets:
            raise CSVError("処理可能なデータが見つかりませんでした")

        return targets

    def _process_single_row(self, row: pd.Series, index: int) -> Dict[str, Any]:
        """単一行を処理してターゲット辞書に変換"""
        # URL処理
        url = str(row['url']).strip()
        if not self._is_valid_url(url):
            raise ValueError(f"無効なURL: {url}")

        # 名前処理
        name = str(row['name']).strip()
        if not name:
            raise ValueError("サイト名が空です")

        # 基本情報
        target = {
            'url': url,
            'name': name,
            'row_number': index + 2,  # Excelの行番号（ヘッダー考慮）
        }

        # オプション情報
        target['enabled'] = self._parse_boolean(row.get('enabled', True))
        target['category'] = str(row.get('category', '')).strip()
        target['priority'] = self._parse_priority(row.get('priority', 'medium'))
        target['description'] = str(row.get('description', '')).strip()

        return target

    def _is_valid_url(self, url: str) -> bool:
        """URL形式の検証"""
        try:
            result = urlparse(url)
            return all([
                result.scheme in ('http', 'https'),
                result.netloc,
                len(url) <= 2000  # URL長制限
            ])
        except Exception:
            return False

    def _parse_boolean(self, value: Any) -> bool:
        """文字列からboolean値に変換"""
        if pd.isna(value) or value == '':
            return True  # デフォルトは有効

        if isinstance(value, bool):
            return value

        str_value = str(value).lower().strip()
        return str_value in ('true', '1', 'yes', 'on', 'enabled', 'enable', 'y')

    def _parse_priority(self, value: Any) -> str:
        """優先度の解析"""
        if pd.isna(value) or value == '':
            return 'medium'

        str_value = str(value).lower().strip()
        valid_priorities = {'high', 'medium', 'low'}

        return str_value if str_value in valid_priorities else 'medium'

    def validate_csv_format(self) -> Dict[str, Any]:
        """
        CSV形式の検証

        Returns:
            検証結果辞書
        """
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'stats': {
                'total_rows': 0,
                'valid_rows': 0,
                'enabled_rows': 0,
                'duplicate_urls': 0,
                'invalid_urls': 0
            }
        }

        try:
            # ファイル存在確認
            if not self.csv_path.exists():
                validation_result['valid'] = False
                validation_result['errors'].append(f"ファイルが見つかりません: {self.csv_path}")
                return validation_result

            # CSV読み込み試行
            targets = self.load_targets(force_reload=True)

            # 統計情報更新
            stats = validation_result['stats']
            stats['total_rows'] = len(targets)
            stats['valid_rows'] = len(targets)
            stats['enabled_rows'] = sum(1 for t in targets if t.get('enabled', True))

            # URL重複チェック
            urls = [t['url'].lower() for t in targets]
            unique_urls = set(urls)
            stats['duplicate_urls'] = len(urls) - len(unique_urls)

            if stats['duplicate_urls'] > 0:
                validation_result['warnings'].append(
                    f"{stats['duplicate_urls']} 件の重複URLが見つかりました"
                )

            # 大量データ警告
            if stats['total_rows'] > 500:
                validation_result['warnings'].append(
                    f"大量データ（{stats['total_rows']}件）です。処理に時間がかかる場合があります"
                )

            # 有効データが少ない場合の警告
            if stats['enabled_rows'] == 0:
                validation_result['warnings'].append("有効なターゲットがありません")
            elif stats['enabled_rows'] < stats['total_rows'] * 0.5:
                validation_result['warnings'].append(
                    f"有効なターゲットが少なめです（{stats['enabled_rows']}/{stats['total_rows']}）"
                )

        except Exception as e:
            validation_result['valid'] = False
            validation_result['errors'].append(str(e))

        return validation_result

    def get_enabled_targets(self, force_reload: bool = False) -> List[Dict[str, Any]]:
        """有効なターゲットのみを取得"""
        all_targets = self.load_targets(force_reload)
        return [t for t in all_targets if t.get('enabled', True)]

    def get_targets_by_category(self, category: str, force_reload: bool = False) -> List[Dict[str, Any]]:
        """カテゴリ別ターゲット取得"""
        all_targets = self.load_targets(force_reload)
        return [t for t in all_targets if t.get('category', '').lower() == category.lower()]

    def get_targets_by_priority(self, priority: str, force_reload: bool = False) -> List[Dict[str, Any]]:
        """優先度別ターゲット取得"""
        all_targets = self.load_targets(force_reload)
        return [t for t in all_targets if t.get('priority', 'medium') == priority.lower()]
