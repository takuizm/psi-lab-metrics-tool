"""
Waterfall データ抽出モジュール

WebPageTest結果からWaterfall描画用のデータを抽出・整形します。
HAR形式に近い構造で、DNS/Connect/SSL/TTFB/Downloadの詳細タイミングを提供。
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.utils.url_utils import extract_host, extract_path, determine_resource_type, get_status_text
from src.extractors.base import BaseExtractor

logger = logging.getLogger(__name__)


class WaterfallExtractionError(Exception):
    """Waterfall抽出関連のエラー"""
    pass


class WaterfallExtractor(BaseExtractor):
    """WebPageTest結果からWaterfallデータを抽出"""

    def __init__(self):
        """WaterfallExtractor初期化"""
        super().__init__()
        # 後方互換性のため extraction_stats プロパティを維持
        self.extraction_stats = self._stats

    def extract_waterfall_data(
        self,
        wpt_results: Dict[str, Any],
        target_info: Dict[str, Any],
        run: int = 1
    ) -> Dict[str, Any]:
        """
        WPT結果からWaterfallデータを抽出

        Args:
            wpt_results: WebPageTestのAPI結果
            target_info: ターゲット情報（URL、名前など）
            run: 取得するラン番号

        Returns:
            Waterfall描画用データ
        """
        self._stats.total_extractions += 1

        try:
            data = wpt_results.get('data', {})
            runs_data = data.get('runs', {})
            run_data = runs_data.get(str(run), {})
            first_view = run_data.get('firstView', {})

            if not first_view:
                raise WaterfallExtractionError("FirstViewデータが見つかりません")

            # ページメトリクス抽出
            page_metrics = self._extract_page_metrics(first_view, data)

            # リクエストタイミング抽出
            requests_list = first_view.get('requests', [])
            waterfall_entries = self._extract_waterfall_entries(requests_list)

            self._stats.total_requests_processed += len(waterfall_entries)

            # マイルストーン抽出
            milestones = self._extract_milestones(first_view)

            # 統合データ作成
            waterfall_data = {
                # メタ情報
                'meta': {
                    'tool': 'WebPageTest',
                    'extracted_at': datetime.now().isoformat() + 'Z',
                    'test_id': data.get('id', ''),
                    'run': run,
                    'url': data.get('url', target_info.get('url', '')),
                    'site_name': target_info.get('name', ''),
                    'strategy': 'mobile' if target_info.get('mobile') else 'desktop',
                    'location': data.get('location', ''),
                },

                # ページメトリクス
                'page_metrics': page_metrics,

                # マイルストーン（タイムライン上の重要ポイント）
                'milestones': milestones,

                # リクエストエントリ（Waterfall本体）
                'entries': waterfall_entries,

                # サマリー統計
                'summary': self.calculate_summary(waterfall_entries, page_metrics)
            }

            self._stats.successful_extractions += 1
            logger.debug(f"Waterfallデータ抽出完了: {len(waterfall_entries)}リクエスト")

            return waterfall_data

        except Exception as e:
            self._stats.failed_extractions += 1
            if isinstance(e, WaterfallExtractionError):
                raise
            raise WaterfallExtractionError(f"Waterfall抽出エラー: {str(e)}")

    def _extract_page_metrics(
        self,
        first_view: Dict[str, Any],
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """ページレベルメトリクスを抽出"""
        return {
            # 主要タイミング（ミリ秒）
            'ttfb_ms': first_view.get('TTFB', 0),
            'start_render_ms': first_view.get('render', 0),
            'dom_content_loaded_ms': first_view.get('domContentLoadedEventStart', 0),
            'dom_complete_ms': first_view.get('domComplete', 0),
            'load_time_ms': first_view.get('loadTime', 0),
            'fully_loaded_ms': first_view.get('fullyLoaded', 0),

            # Core Web Vitals
            'fcp_ms': first_view.get('firstContentfulPaint', 0),
            'lcp_ms': first_view.get('chromeUserTiming.LargestContentfulPaint',
                                      first_view.get('LargestContentfulPaint', 0)),
            'cls': first_view.get('chromeUserTiming.CumulativeLayoutShift',
                                   first_view.get('CumulativeLayoutShift', 0)),
            'tbt_ms': first_view.get('TotalBlockingTime', 0),

            # Speed Index
            'speed_index': first_view.get('SpeedIndex', 0),
            'visual_complete_ms': first_view.get('visualComplete', 0),

            # リクエスト/サイズ情報
            'total_requests': first_view.get('requestsFull', first_view.get('requests', 0)),
            'total_bytes': first_view.get('bytesIn', 0),
            'total_bytes_out': first_view.get('bytesOut', 0),

            # 接続情報
            'connections': first_view.get('connections', 0),
            'domains': len(first_view.get('domains', {})),
        }

    def _extract_milestones(self, first_view: Dict[str, Any]) -> List[Dict[str, Any]]:
        """タイムライン上のマイルストーンを抽出"""
        milestones = []

        milestone_mapping = [
            ('ttfb', 'TTFB', 'Time to First Byte', '#4CAF50'),
            ('start_render', 'render', 'Start Render', '#2196F3'),
            ('fcp', 'firstContentfulPaint', 'First Contentful Paint', '#FF9800'),
            ('lcp', 'LargestContentfulPaint', 'Largest Contentful Paint', '#E91E63'),
            ('dom_content_loaded', 'domContentLoadedEventStart', 'DOM Content Loaded', '#9C27B0'),
            ('dom_complete', 'domComplete', 'DOM Complete', '#673AB7'),
            ('load', 'loadTime', 'Load Event', '#F44336'),
            ('fully_loaded', 'fullyLoaded', 'Fully Loaded', '#607D8B'),
        ]

        for key, source_key, label, color in milestone_mapping:
            value = first_view.get(source_key, 0)
            if value and value > 0:
                milestones.append({
                    'key': key,
                    'time_ms': value,
                    'label': label,
                    'color': color
                })

        # 時間順にソート
        milestones.sort(key=lambda x: x['time_ms'])

        return milestones

    def _extract_waterfall_entries(
        self,
        requests: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """リクエストリストからWaterfallエントリを抽出"""
        entries = []

        for idx, req in enumerate(requests):
            entry = self._convert_request_to_entry(req, idx)
            if entry:
                entries.append(entry)

        return entries

    def _convert_request_to_entry(
        self,
        request: Dict[str, Any],
        index: int
    ) -> Optional[Dict[str, Any]]:
        """単一リクエストをWaterfallエントリに変換"""
        try:
            url = request.get('full_url', request.get('url', ''))
            if not url:
                return None

            # 基本タイミング
            start_time = request.get('load_start', 0)
            total_time = request.get('load_ms', 0)
            end_time = start_time + total_time

            # 詳細タイミング（HAR互換形式）
            timings = self._extract_detailed_timings(request)

            entry = {
                # 識別情報
                'index': index,
                'url': url,
                'host': request.get('host', extract_host(url)),
                'path': extract_path(url),

                # リクエスト情報
                'method': request.get('method', 'GET'),
                'status': request.get('responseCode', 0),
                'status_text': get_status_text(request.get('responseCode', 0)),

                # コンテンツ情報
                'content_type': request.get('contentType', ''),
                'resource_type': determine_resource_type(
                    request.get('full_url', request.get('url', '')),
                    request.get('contentType', '')
                ),
                'mime_type': request.get('mimeType', request.get('contentType', '')),

                # プロトコル情報
                'protocol': request.get('protocol', ''),
                'http_version': request.get('http2', 0) == 1 and 'h2' or 'http/1.1',
                'priority': request.get('priority', ''),

                # サイズ情報（バイト）
                'transfer_size': request.get('bytesIn', 0),
                'content_size': request.get('objectSize', 0),
                'header_size': request.get('bytesInHeaders', 0),

                # タイミング情報（ミリ秒） - Waterfall描画用
                'start_time': start_time,
                'end_time': end_time,
                'duration': total_time,

                # 詳細タイミング（HAR timings互換）
                'timings': timings,

                # 接続情報
                'connection_reused': request.get('socket', 0) != 0,
                'server_ip': request.get('ip_addr', ''),
                'server_port': request.get('server_port', 443),

                # セキュリティ情報
                'is_secure': url.startswith('https://'),
                'tls_version': request.get('tls_version', ''),
                'tls_cipher': request.get('tls_cipher', ''),

                # キャッシュ情報
                'from_cache': request.get('cacheControl', {}).get('max-age', 0) > 0,
                'cache_control': request.get('cacheControl', ''),
            }

            return entry

        except Exception as e:
            logger.debug(f"エントリ変換エラー (index={index}): {e}")
            return None

    def _extract_detailed_timings(self, request: Dict[str, Any]) -> Dict[str, float]:
        """
        HAR timings形式で詳細タイミングを抽出

        Returns:
            {
                'blocked': キュー待ち時間,
                'dns': DNS解決時間,
                'connect': TCP接続時間,
                'ssl': SSL/TLSハンドシェイク時間,
                'send': リクエスト送信時間,
                'wait': TTFB（サーバー処理時間）,
                'receive': レスポンス受信時間
            }
        """
        timings = {
            'blocked': -1,
            'dns': -1,
            'connect': -1,
            'ssl': -1,
            'send': -1,
            'wait': -1,
            'receive': -1
        }

        # DNS
        dns_start = request.get('dns_start', -1)
        dns_end = request.get('dns_end', -1)
        if dns_start >= 0 and dns_end >= 0:
            timings['dns'] = max(0, dns_end - dns_start)

        # Connect
        connect_start = request.get('connect_start', -1)
        connect_end = request.get('connect_end', -1)
        if connect_start >= 0 and connect_end >= 0:
            timings['connect'] = max(0, connect_end - connect_start)

        # SSL
        ssl_start = request.get('ssl_start', -1)
        ssl_end = request.get('ssl_end', -1)
        if ssl_start >= 0 and ssl_end >= 0:
            timings['ssl'] = max(0, ssl_end - ssl_start)
            # SSLはconnectに含まれるので、connectから差し引く
            if timings['connect'] > 0:
                timings['connect'] = max(0, timings['connect'] - timings['ssl'])

        # TTFB (wait)
        ttfb = request.get('ttfb_ms', 0)
        if ttfb > 0:
            timings['wait'] = ttfb

        # Download (receive)
        download = request.get('download_ms', 0)
        if download > 0:
            timings['receive'] = download

        return timings

    def calculate_summary(
        self,
        entries: List[Dict[str, Any]],
        page_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """サマリー統計を計算（cache_stats を追加）"""
        summary = super().calculate_summary(entries, page_metrics)
        if not entries:
            return summary

        # WaterfallExtractor 固有のキャッシュ統計を追加
        summary['cache_stats'] = {
            'from_cache': sum(1 for e in entries if e.get('from_cache')),
            'from_network': sum(1 for e in entries if not e.get('from_cache')),
        }
        return summary

