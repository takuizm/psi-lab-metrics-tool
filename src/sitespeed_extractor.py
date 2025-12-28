"""
sitespeed.io 結果抽出モジュール

sitespeed.ioの出力（HAR、browsertime.json等）から
Waterfallデータとメトリクスを抽出・整形します。
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SitespeedExtractionError(Exception):
    """sitespeed.io結果抽出関連のエラー"""
    pass


class SitespeedExtractor:
    """sitespeed.io結果からWaterfallデータを抽出"""

    def __init__(self):
        """SitespeedExtractor初期化"""
        self.extraction_stats = {
            'total_extractions': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'total_requests_processed': 0,
        }

    def extract_waterfall_from_har(
        self,
        har_path: str,
        target_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        HARファイルからWaterfallデータを抽出

        Args:
            har_path: HARファイルパス
            target_info: ターゲット情報（URL、名前など）

        Returns:
            Waterfall描画用データ
        """
        self.extraction_stats['total_extractions'] += 1
        target_info = target_info or {}

        try:
            har_path = Path(har_path)
            if not har_path.exists():
                raise SitespeedExtractionError(f"HARファイルが見つかりません: {har_path}")

            with open(har_path, 'r', encoding='utf-8') as f:
                har_data = json.load(f)

            log = har_data.get('log', {})
            entries = log.get('entries', [])

            if not entries:
                raise SitespeedExtractionError("HARファイルにエントリがありません")

            # ページ情報取得
            pages = log.get('pages', [])
            page_info = pages[0] if pages else {}

            # ページタイミング取得
            page_timings = page_info.get('pageTimings', {})

            # リクエストエントリ抽出
            waterfall_entries = self._extract_entries(entries)
            self.extraction_stats['total_requests_processed'] += len(waterfall_entries)

            # マイルストーン抽出
            milestones = self._extract_milestones_from_page(page_info, page_timings)

            # ページメトリクス計算
            page_metrics = self._calculate_page_metrics(entries, page_timings)

            # 統合データ作成
            waterfall_data = {
                'meta': {
                    'tool': 'sitespeed.io',
                    'extracted_at': datetime.now().isoformat() + 'Z',
                    'har_file': str(har_path),
                    'url': target_info.get('url', page_info.get('id', '')),
                    'site_name': target_info.get('name', ''),
                    'strategy': 'mobile' if target_info.get('mobile') else 'desktop',
                    'browser': target_info.get('browser', ''),
                },
                'page_metrics': page_metrics,
                'milestones': milestones,
                'entries': waterfall_entries,
                'summary': self._calculate_summary(waterfall_entries, page_metrics),
            }

            self.extraction_stats['successful_extractions'] += 1
            logger.debug(f"Waterfall抽出完了: {len(waterfall_entries)}リクエスト")

            return waterfall_data

        except Exception as e:
            self.extraction_stats['failed_extractions'] += 1
            if isinstance(e, SitespeedExtractionError):
                raise
            raise SitespeedExtractionError(f"Waterfall抽出エラー: {str(e)}")

    def _extract_entries(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """HARエントリからWaterfallエントリを抽出"""
        waterfall_entries = []

        # 基準時刻（最初のリクエスト開始時刻）
        if entries:
            base_time = self._parse_iso_time(entries[0].get('startedDateTime', ''))
        else:
            base_time = 0

        for idx, entry in enumerate(entries):
            converted = self._convert_har_entry(entry, idx, base_time)
            if converted:
                waterfall_entries.append(converted)

        return waterfall_entries

    def _convert_har_entry(
        self,
        entry: Dict[str, Any],
        index: int,
        base_time: float,
    ) -> Optional[Dict[str, Any]]:
        """HARエントリをWaterfallエントリに変換"""
        try:
            request = entry.get('request', {})
            response = entry.get('response', {})
            timings = entry.get('timings', {})

            url = request.get('url', '')
            if not url:
                return None

            # 開始時刻計算（ミリ秒）
            start_time_iso = entry.get('startedDateTime', '')
            start_time = self._parse_iso_time(start_time_iso) - base_time
            if start_time < 0:
                start_time = 0

            # 各フェーズのタイミング（HAR標準形式）
            blocked = max(0, timings.get('blocked', 0))
            dns = max(0, timings.get('dns', 0))
            connect = max(0, timings.get('connect', 0))
            ssl = max(0, timings.get('ssl', 0))
            send = max(0, timings.get('send', 0))
            wait = max(0, timings.get('wait', 0))  # TTFB
            receive = max(0, timings.get('receive', 0))

            # SSLはconnectに含まれる場合があるので調整
            if ssl > 0 and connect > ssl:
                connect = connect - ssl

            # 総時間
            duration = entry.get('time', 0)
            if duration <= 0:
                duration = blocked + dns + connect + ssl + send + wait + receive

            end_time = start_time + duration

            # コンテンツタイプ
            content_type = ''
            for header in response.get('headers', []):
                if header.get('name', '').lower() == 'content-type':
                    content_type = header.get('value', '')
                    break

            converted_entry = {
                'index': index,
                'url': url,
                'host': self._extract_host(url),
                'path': self._extract_path(url),
                'method': request.get('method', 'GET'),
                'status': response.get('status', 0),
                'status_text': response.get('statusText', ''),
                'content_type': content_type,
                'resource_type': self._determine_resource_type(url, content_type),
                'mime_type': response.get('content', {}).get('mimeType', content_type),
                'protocol': request.get('httpVersion', ''),
                'transfer_size': response.get('_transferSize', response.get('bodySize', 0)),
                'content_size': response.get('content', {}).get('size', 0),
                'header_size': response.get('headersSize', 0),

                # タイミング（ミリ秒）
                'start_time': start_time,
                'end_time': end_time,
                'duration': duration,

                # 詳細タイミング（HAR timings形式）
                'timings': {
                    'blocked': blocked if blocked > 0 else -1,
                    'dns': dns if dns > 0 else -1,
                    'connect': connect if connect > 0 else -1,
                    'ssl': ssl if ssl > 0 else -1,
                    'send': send if send > 0 else -1,
                    'wait': wait if wait > 0 else -1,
                    'receive': receive if receive > 0 else -1,
                },

                # 接続情報
                'connection_reused': dns == 0 and connect == 0,
                'server_ip': entry.get('serverIPAddress', ''),
                'is_secure': url.startswith('https://'),
                'from_cache': response.get('_fromCache', False),
            }

            return converted_entry

        except Exception as e:
            logger.debug(f"エントリ変換エラー (index={index}): {e}")
            return None

    def _extract_milestones_from_page(
        self,
        page_info: Dict[str, Any],
        page_timings: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """ページ情報からマイルストーンを抽出"""
        milestones = []

        # カスタムタイミング（sitespeed.ioが追加するもの）
        custom_timings = page_info.get('_timings', {})

        milestone_mapping = [
            ('ttfb', 'onContentLoad', page_timings, 'Time to First Byte', '#4CAF50'),
            ('dom_content_loaded', 'onContentLoad', page_timings, 'DOM Content Loaded', '#9C27B0'),
            ('load', 'onLoad', page_timings, 'Load Event', '#F44336'),
            ('fcp', 'firstContentfulPaint', custom_timings, 'First Contentful Paint', '#FF9800'),
            ('lcp', 'largestContentfulPaint', custom_timings, 'Largest Contentful Paint', '#E91E63'),
        ]

        for key, source_key, source_dict, label, color in milestone_mapping:
            value = source_dict.get(source_key, 0)
            if value and value > 0:
                milestones.append({
                    'key': key,
                    'time_ms': value,
                    'label': label,
                    'color': color,
                })

        milestones.sort(key=lambda x: x['time_ms'])
        return milestones

    def _calculate_page_metrics(
        self,
        entries: List[Dict[str, Any]],
        page_timings: Dict[str, Any],
    ) -> Dict[str, Any]:
        """ページメトリクスを計算"""
        metrics = {
            'total_requests': len(entries),
            'total_size': 0,
            'dom_content_loaded_ms': page_timings.get('onContentLoad', 0),
            'load_time_ms': page_timings.get('onLoad', 0),
        }

        # 最初のリクエスト（メインドキュメント）のタイミング
        if entries:
            first_entry = entries[0]
            timings = first_entry.get('timings', {})
            metrics['ttfb_ms'] = max(0, timings.get('wait', 0))
            metrics['dns_ms'] = max(0, timings.get('dns', 0))
            metrics['connect_ms'] = max(0, timings.get('connect', 0))
            metrics['ssl_ms'] = max(0, timings.get('ssl', 0))

        # 総サイズ計算
        for entry in entries:
            response = entry.get('response', {})
            size = response.get('_transferSize', response.get('bodySize', 0))
            if size > 0:
                metrics['total_size'] += size

        return metrics

    def _calculate_summary(
        self,
        entries: List[Dict[str, Any]],
        page_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """サマリー統計を計算"""
        if not entries:
            return {}

        # リソースタイプ別集計
        type_counts = {}
        type_sizes = {}

        for entry in entries:
            res_type = entry.get('resource_type', 'other')
            type_counts[res_type] = type_counts.get(res_type, 0) + 1
            type_sizes[res_type] = type_sizes.get(res_type, 0) + entry.get('transfer_size', 0)

        # タイミング統計
        dns_times = [e['timings']['dns'] for e in entries if e['timings']['dns'] > 0]
        connect_times = [e['timings']['connect'] for e in entries if e['timings']['connect'] > 0]
        ssl_times = [e['timings']['ssl'] for e in entries if e['timings']['ssl'] > 0]
        wait_times = [e['timings']['wait'] for e in entries if e['timings']['wait'] > 0]

        return {
            'total_entries': len(entries),
            'by_resource_type': {
                'counts': type_counts,
                'sizes': type_sizes,
            },
            'timing_stats': {
                'dns': {
                    'count': len(dns_times),
                    'total_ms': sum(dns_times) if dns_times else 0,
                    'avg_ms': sum(dns_times) / len(dns_times) if dns_times else 0,
                },
                'connect': {
                    'count': len(connect_times),
                    'total_ms': sum(connect_times) if connect_times else 0,
                    'avg_ms': sum(connect_times) / len(connect_times) if connect_times else 0,
                },
                'ssl': {
                    'count': len(ssl_times),
                    'total_ms': sum(ssl_times) if ssl_times else 0,
                    'avg_ms': sum(ssl_times) / len(ssl_times) if ssl_times else 0,
                },
                'wait': {
                    'count': len(wait_times),
                    'total_ms': sum(wait_times) if wait_times else 0,
                    'avg_ms': sum(wait_times) / len(wait_times) if wait_times else 0,
                },
            },
            'connection_stats': {
                'reused': sum(1 for e in entries if e.get('connection_reused')),
                'new': sum(1 for e in entries if not e.get('connection_reused')),
            },
        }

    def _parse_iso_time(self, iso_string: str) -> float:
        """ISO時刻文字列をミリ秒に変換"""
        try:
            if not iso_string:
                return 0
            # 2024-01-01T00:00:00.000Z 形式
            dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
            return dt.timestamp() * 1000
        except Exception:
            return 0

    def _extract_host(self, url: str) -> str:
        """URLからホスト名を抽出"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except Exception:
            return ''

    def _extract_path(self, url: str) -> str:
        """URLからパスを抽出"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.path + ('?' + parsed.query if parsed.query else '')
        except Exception:
            return ''

    def _determine_resource_type(self, url: str, content_type: str) -> str:
        """リソースタイプを判定"""
        content_type = content_type.lower()
        url = url.lower()

        if 'html' in content_type:
            return 'document'
        elif 'css' in content_type:
            return 'stylesheet'
        elif 'javascript' in content_type or 'script' in content_type:
            return 'script'
        elif 'image' in content_type:
            return 'image'
        elif 'font' in content_type or 'woff' in content_type:
            return 'font'
        elif 'json' in content_type:
            return 'fetch'
        elif 'xml' in content_type:
            return 'xhr'
        elif 'video' in content_type or 'audio' in content_type:
            return 'media'

        # URL拡張子で判定
        if '.css' in url:
            return 'stylesheet'
        elif '.js' in url:
            return 'script'
        elif any(ext in url for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico']):
            return 'image'
        elif any(ext in url for ext in ['.woff', '.woff2', '.ttf', '.eot', '.otf']):
            return 'font'

        return 'other'

    def get_stats(self) -> Dict[str, Any]:
        """統計情報を取得"""
        stats = self.extraction_stats.copy()
        if stats['total_extractions'] > 0:
            stats['success_rate'] = stats['successful_extractions'] / stats['total_extractions']
        else:
            stats['success_rate'] = 0.0
        return stats

    def reset_stats(self):
        """統計情報をリセット"""
        self.extraction_stats = {
            'total_extractions': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'total_requests_processed': 0,
        }
