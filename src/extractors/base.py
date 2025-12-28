"""
Extractor 基底クラス

sitespeed_extractor と waterfall_extractor で共通使用される
統計管理・サマリー計算機能を提供。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ExtractionStats:
    """抽出統計情報"""
    total_extractions: int = 0
    successful_extractions: int = 0
    failed_extractions: int = 0
    total_requests_processed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式で取得（success_rate 計算付き）"""
        success_rate = 0.0
        if self.total_extractions > 0:
            success_rate = self.successful_extractions / self.total_extractions
        return {
            'total_extractions': self.total_extractions,
            'successful_extractions': self.successful_extractions,
            'failed_extractions': self.failed_extractions,
            'total_requests_processed': self.total_requests_processed,
            'success_rate': success_rate,
        }

    def reset(self):
        """統計情報をリセット"""
        self.total_extractions = 0
        self.successful_extractions = 0
        self.failed_extractions = 0
        self.total_requests_processed = 0


class BaseExtractor:
    """Extractor 基底クラス"""

    def __init__(self):
        """BaseExtractor 初期化"""
        self._stats = ExtractionStats()

    @property
    def stats(self) -> ExtractionStats:
        """統計情報オブジェクトを取得"""
        return self._stats

    def get_stats(self) -> Dict[str, Any]:
        """統計情報を辞書で取得"""
        return self._stats.to_dict()

    def reset_stats(self):
        """統計情報をリセット"""
        self._stats.reset()

    def calculate_summary(
        self,
        entries: List[Dict[str, Any]],
        page_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        サマリー統計を計算

        Args:
            entries: Waterfall エントリリスト
            page_metrics: ページメトリクス

        Returns:
            サマリー統計
        """
        if not entries:
            return {}

        # リソースタイプ別集計
        type_counts: Dict[str, int] = {}
        type_sizes: Dict[str, int] = {}

        for entry in entries:
            res_type = entry.get('resource_type', 'other')
            type_counts[res_type] = type_counts.get(res_type, 0) + 1
            type_sizes[res_type] = type_sizes.get(res_type, 0) + entry.get('transfer_size', 0)

        # タイミング統計
        timing_stats = self._calculate_timing_stats(entries)

        # 接続統計
        connection_stats = self._calculate_connection_stats(entries)

        return {
            'total_entries': len(entries),
            'by_resource_type': {
                'counts': type_counts,
                'sizes': type_sizes,
            },
            'timing_stats': timing_stats,
            'connection_stats': connection_stats,
        }

    def _calculate_timing_stats(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """タイミング統計を計算"""
        timing_keys = ['dns', 'connect', 'ssl', 'wait']
        result = {}

        for key in timing_keys:
            times = [
                e['timings'][key]
                for e in entries
                if e.get('timings', {}).get(key, 0) > 0
            ]
            result[key] = {
                'count': len(times),
                'total_ms': sum(times) if times else 0,
                'avg_ms': sum(times) / len(times) if times else 0,
            }

        return result

    def _calculate_connection_stats(self, entries: List[Dict[str, Any]]) -> Dict[str, int]:
        """接続統計を計算"""
        return {
            'reused': sum(1 for e in entries if e.get('connection_reused')),
            'new': sum(1 for e in entries if not e.get('connection_reused')),
        }
