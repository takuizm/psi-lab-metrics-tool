"""
メトリクス抽出モジュール

PSI APIレスポンスから必要なメトリクスを抽出・変換します。
Splunk Syntheticとの比較に必要なデータを正確に取得。
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricsExtractionError(Exception):
    """メトリクス抽出関連のエラー"""
    pass


class MetricsExtractor:
    """PSIレスポンスからメトリクスを抽出"""

    # 抽出対象メトリクス定義
    LAB_METRICS_MAPPING = {
        'onload_ms': 'observedLoad',
        'ttfb_ms': 'timeToFirstByte',
        'observed_lcp_ms': 'observedLargestContentfulPaint',
        'observed_cls': 'observedCumulativeLayoutShift',
        'observed_dom_content_loaded_ms': 'observedDomContentLoaded',
        'observed_fcp_ms': 'observedFirstContentfulPaint',
        'observed_fmp_ms': 'observedFirstMeaningfulPaint'
    }

    AUDIT_METRICS_MAPPING = {
        'lcp_ms': 'largest-contentful-paint',
        'cls': 'cumulative-layout-shift',
        'speed_index_ms': 'speed-index',
        'fcp_ms': 'first-contentful-paint',
        'tbt_ms': 'total-blocking-time',
        'interactive_ms': 'interactive',
        'server_response_time_ms': 'server-response-time'
    }

    def __init__(self):
        """MetricsExtractor初期化"""
        self.extraction_stats = {
            'total_extractions': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'missing_metrics_count': 0
        }

    def extract_all_metrics(self, psi_response: Dict[str, Any],
                          target_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        PSIレスポンスから全メトリクスを抽出

        Args:
            psi_response: PSI APIレスポンス
            target_info: ターゲット情報（URL、名前など）

        Returns:
            抽出されたメトリクス辞書

        Raises:
            MetricsExtractionError: メトリクス抽出に失敗した場合
        """
        self.extraction_stats['total_extractions'] += 1

        try:
            # 基本情報の検証
            if not psi_response or 'lighthouseResult' not in psi_response:
                raise MetricsExtractionError("PSIレスポンスが無効です")

            lighthouse_result = psi_response['lighthouseResult']

            # メトリクス抽出
            lab_metrics = self._extract_lab_metrics(lighthouse_result)
            audit_metrics = self._extract_audit_metrics(lighthouse_result)
            field_data = self._extract_field_data(psi_response)
            metadata = self._extract_metadata(lighthouse_result, psi_response)

            # 全データを統合
            all_metrics = {
                **target_info,
                **lab_metrics,
                **audit_metrics,
                **metadata
            }

            # フィールドデータがある場合は追加
            if field_data:
                all_metrics.update(field_data)

            # データ品質チェック
            self._validate_extracted_metrics(all_metrics)

            self.extraction_stats['successful_extractions'] += 1
            logger.debug(f"メトリクス抽出完了: {target_info.get('url', 'unknown')}")

            return all_metrics

        except Exception as e:
            self.extraction_stats['failed_extractions'] += 1
            if isinstance(e, MetricsExtractionError):
                raise
            logger.error(f"メトリクス抽出中にエラー: {str(e)}")
            raise MetricsExtractionError(f"メトリクス抽出エラー: {str(e)}")

    def _extract_lab_metrics(self, lighthouse_result: Dict[str, Any]) -> Dict[str, Any]:
        """ラボデータメトリクスを抽出"""
        lab_metrics = {}
        missing_metrics = []

        try:
            audits = lighthouse_result.get('audits', {})
            metrics_audit = audits.get('metrics', {})
            metrics_details = metrics_audit.get('details', {})
            metrics_items = metrics_details.get('items', [])

            if not metrics_items:
                logger.warning("メトリクス詳細データが見つかりません")
                return self._get_default_lab_metrics()

            metrics_data = metrics_items[0]

            # 各メトリクスを抽出
            for output_key, source_key in self.LAB_METRICS_MAPPING.items():
                value = metrics_data.get(source_key)
                if value is not None:
                    # 数値型に変換（ミリ秒単位）
                    try:
                        lab_metrics[output_key] = float(value)
                    except (ValueError, TypeError):
                        lab_metrics[output_key] = 0.0
                        missing_metrics.append(source_key)
                else:
                    lab_metrics[output_key] = 0.0
                    missing_metrics.append(source_key)

            if missing_metrics:
                logger.debug(f"不足しているラボメトリクス: {missing_metrics}")
                self.extraction_stats['missing_metrics_count'] += len(missing_metrics)

        except Exception as e:
            logger.warning(f"ラボメトリクス抽出中にエラー: {e}")
            return self._get_default_lab_metrics()

        return lab_metrics

    def _extract_audit_metrics(self, lighthouse_result: Dict[str, Any]) -> Dict[str, Any]:
        """監査メトリクスを抽出"""
        audit_metrics = {}
        missing_metrics = []

        try:
            audits = lighthouse_result.get('audits', {})

            # 各監査メトリクスを抽出
            for output_key, audit_key in self.AUDIT_METRICS_MAPPING.items():
                audit_data = audits.get(audit_key, {})
                numeric_value = audit_data.get('numericValue')

                if numeric_value is not None:
                    try:
                        audit_metrics[output_key] = float(numeric_value)
                    except (ValueError, TypeError):
                        audit_metrics[output_key] = 0.0
                        missing_metrics.append(audit_key)
                else:
                    audit_metrics[output_key] = 0.0
                    missing_metrics.append(audit_key)

            if missing_metrics:
                logger.debug(f"不足している監査メトリクス: {missing_metrics}")
                self.extraction_stats['missing_metrics_count'] += len(missing_metrics)

        except Exception as e:
            logger.warning(f"監査メトリクス抽出中にエラー: {e}")
            return self._get_default_audit_metrics()

        return audit_metrics

    def _extract_field_data(self, psi_response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """フィールドデータ（実ユーザーデータ）を抽出"""
        try:
            loading_experience = psi_response.get('loadingExperience')
            if not loading_experience:
                return None

            metrics = loading_experience.get('metrics', {})
            field_data = {}

            # Core Web Vitalsのフィールドデータ
            field_metrics_mapping = {
                'field_fcp_ms': 'FIRST_CONTENTFUL_PAINT_MS',
                'field_lcp_ms': 'LARGEST_CONTENTFUL_PAINT_MS',
                'field_cls': 'CUMULATIVE_LAYOUT_SHIFT_SCORE',
                'field_fid_ms': 'FIRST_INPUT_DELAY_MS',
                'field_inp_ms': 'INTERACTION_TO_NEXT_PAINT'
            }

            for output_key, metric_key in field_metrics_mapping.items():
                metric_data = metrics.get(metric_key, {})
                percentile = metric_data.get('percentile')
                if percentile is not None:
                    try:
                        field_data[output_key] = float(percentile)
                    except (ValueError, TypeError):
                        field_data[output_key] = 0.0

            # 全体カテゴリ
            field_data['field_overall_category'] = loading_experience.get('overall_category', '')

            return field_data if field_data else None

        except Exception as e:
            logger.debug(f"フィールドデータ抽出中にエラー: {e}")
            return None

    def _extract_metadata(self, lighthouse_result: Dict[str, Any],
                         psi_response: Dict[str, Any]) -> Dict[str, Any]:
        """メタデータを抽出"""
        try:
            # 基本メタデータ
            metadata = {
                'timestamp': lighthouse_result.get('fetchTime', datetime.now().isoformat() + 'Z'),
                'lighthouse_version': lighthouse_result.get('lighthouseVersion', ''),
                'user_agent': lighthouse_result.get('userAgent', ''),
                'api_response_id': psi_response.get('id', ''),
                'captcha_result': psi_response.get('captchaResult', '')
            }

            # 設定情報
            config_settings = lighthouse_result.get('configSettings', {})
            metadata.update({
                'form_factor': config_settings.get('formFactor', ''),
                'locale': config_settings.get('locale', ''),
                'throttling_method': config_settings.get('throttlingMethod', '')
            })

            # 環境情報
            environment = lighthouse_result.get('environment', {})
            metadata.update({
                'network_user_agent': environment.get('networkUserAgent', ''),
                'host_user_agent': environment.get('hostUserAgent', ''),
                'benchmark_index': environment.get('benchmarkIndex', 0)
            })

            # 実行時警告
            run_warnings = lighthouse_result.get('runWarnings', [])
            metadata['run_warnings_count'] = len(run_warnings)
            if run_warnings:
                # 最初の3つの警告のみ記録（長すぎる場合の対策）
                metadata['run_warnings'] = '; '.join(run_warnings[:3])

            return metadata

        except Exception as e:
            logger.warning(f"メタデータ抽出中にエラー: {e}")
            return {
                'timestamp': datetime.now().isoformat() + 'Z',
                'lighthouse_version': '',
                'form_factor': '',
                'user_agent': '',
                'api_response_id': ''
            }

    def _validate_extracted_metrics(self, metrics: Dict[str, Any]):
        """抽出されたメトリクスの検証"""
        # 必須フィールドの確認
        required_fields = ['url', 'name', 'strategy', 'timestamp']
        missing_fields = [field for field in required_fields if field not in metrics]

        if missing_fields:
            raise MetricsExtractionError(f"必須フィールドが不足しています: {missing_fields}")

        # 数値メトリクスの妥当性チェック
        numeric_metrics = [key for key in metrics.keys() if key.endswith('_ms') or key == 'cls']

        for metric_key in numeric_metrics:
            value = metrics.get(metric_key, 0)
            if not isinstance(value, (int, float)) or value < 0:
                logger.warning(f"異常な値が検出されました {metric_key}: {value}")
                metrics[metric_key] = 0.0

            # 極端に大きな値のチェック（30分以上は異常）
            if metric_key.endswith('_ms') and value > 1800000:  # 30分
                logger.warning(f"極端に大きな値が検出されました {metric_key}: {value}ms")

    def _get_default_lab_metrics(self) -> Dict[str, Any]:
        """デフォルトラボメトリクス"""
        return {key: 0.0 for key in self.LAB_METRICS_MAPPING.keys()}

    def _get_default_audit_metrics(self) -> Dict[str, Any]:
        """デフォルト監査メトリクス"""
        return {key: 0.0 for key in self.AUDIT_METRICS_MAPPING.keys()}

    def create_summary_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        サマリー用の主要メトリクスを作成

        Splunk Syntheticとの比較用に重要なメトリクスのみを抽出
        """
        summary = {
            # 基本情報
            'site_name': metrics.get('name', ''),
            'url': metrics.get('url', ''),
            'strategy': metrics.get('strategy', ''),
            'timestamp': metrics.get('timestamp', ''),

            # 主要パフォーマンスメトリクス
            'onload_ms': metrics.get('onload_ms', 0),
            'ttfb_ms': metrics.get('ttfb_ms', 0),
            'lcp_ms': metrics.get('lcp_ms', 0),
            'cls': metrics.get('cls', 0),
            'speed_index_ms': metrics.get('speed_index_ms', 0),

            # 観測値（参考）
            'observed_lcp_ms': metrics.get('observed_lcp_ms', 0),
            'observed_cls': metrics.get('observed_cls', 0),

            # その他重要メトリクス
            'fcp_ms': metrics.get('fcp_ms', 0),
            'tbt_ms': metrics.get('tbt_ms', 0),

            # メタデータ
            'lighthouse_version': metrics.get('lighthouse_version', ''),
            'form_factor': metrics.get('form_factor', ''),

            # 分類情報
            'category': metrics.get('category', ''),
            'priority': metrics.get('priority', 'medium')
        }

        return summary

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
            'missing_metrics_count': 0
        }
        logger.debug("メトリクス抽出統計情報をリセットしました")
