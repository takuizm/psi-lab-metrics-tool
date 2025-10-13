"""
メインプロセッサ

PSI Lab Metrics Toolのメイン実行モジュール
大量データ処理、エラーハンドリング、進捗表示を含む統合処理
"""

import logging
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from .config_manager import ConfigManager, ConfigError
from .csv_loader import CSVLoader, CSVError
from .psi_client import PSIClient, PSIAPIError, PSIRateLimitError
from .metrics_extractor import MetricsExtractor, MetricsExtractionError
from .output_manager import OutputManager, OutputError

logger = logging.getLogger(__name__)


class ProcessingInterrupted(Exception):
    """処理中断例外"""
    pass


class MainProcessor:
    """メイン処理クラス"""

    def __init__(self, config: Dict[str, Any]):
        """
        MainProcessor初期化

        Args:
            config: 設定辞書
        """
        self.config = config
        self.execution_config = self.config.get('execution', {})
        self.interrupted = False

        # シグナルハンドラー設定
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # ログ設定
        self._setup_logging()

        # コンポーネント初期化
        self._initialize_components()

        # 処理統計
        self.processing_stats = {
            'start_time': None,
            'end_time': None,
            'total_targets': 0,
            'processed_targets': 0,
            'successful_targets': 0,
            'failed_targets': 0,
            'skipped_targets': 0,
            'total_requests': 0,
            'rate_limit_hits': 0
        }

        self.logger = logging.getLogger(__name__)
        self.logger.info("MainProcessorを初期化しました")

    def _signal_handler(self, signum, frame):
        """シグナルハンドラー"""
        self.interrupted = True
        self.logger.warning(f"処理中断シグナルを受信しました: {signum}")

    def _setup_logging(self):
        """ログ設定"""
        log_config = self.config.get('logging', {})
        log_file = self.config['output']['log_file']

        # ログディレクトリ作成
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        # ログレベル設定
        log_level = getattr(logging, log_config.get('level', 'INFO').upper())
        log_format = log_config.get('format', '%(asctime)s [%(levelname)s] %(name)s: %(message)s')

        # ロガー設定
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # 既存ハンドラーをクリア
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # ファイルハンドラー
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(file_handler)

        # コンソールハンドラー
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(console_handler)

        # 外部ライブラリのログレベル調整
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)

    def _initialize_components(self):
        """コンポーネント初期化"""
        try:
            # PSI APIクライアント
            api_config = self.config['api']
            self.psi_client = self._build_psi_client(api_config)

            # CSV読み込み
            input_config = self.config['input']
            self.csv_loader = CSVLoader(
                csv_path=input_config['targets_csv'],
                encoding=input_config.get('csv_encoding', 'utf-8-sig')
            )

            # メトリクス抽出
            self.metrics_extractor = MetricsExtractor()

            # 出力管理
            output_config = self.config['output']
            self.output_manager = OutputManager(
                json_dir=output_config['json_dir'],
                csv_file=output_config['csv_file'],
                timestamp_format=output_config.get('timestamp_format', '%Y%m%d_%H%M%S')
            )

        except Exception as e:
            raise RuntimeError(f"コンポーネント初期化エラー: {str(e)}")

    def process_all_targets(self, strategies: List[str], dry_run: bool = False) -> Dict[str, Any]:
        """
        全ターゲットの処理

        Args:
            strategies: 計測戦略リスト
            dry_run: ドライラン実行

        Returns:
            処理結果辞書
        """
        self.processing_stats['start_time'] = datetime.now()

        try:
            # CSV検証・読み込み
            targets = self._load_and_validate_targets(dry_run)
            if not targets:
                return self._create_result_summary(success=False, message="有効なターゲットがありません")

            # ドライラン処理
            if dry_run:
                return self._process_dry_run(targets, strategies)

            # 実際の処理
            if self._should_use_parallel(len(targets), len(strategies)):
                return self._process_targets_parallel(targets, strategies)

            return self._process_targets(targets, strategies)

        except Exception as e:
            self.logger.error(f"処理中に致命的エラー: {str(e)}")
            return self._create_result_summary(success=False, message=str(e))

        finally:
            self.processing_stats['end_time'] = datetime.now()

    def _load_and_validate_targets(self, dry_run: bool = False) -> List[Dict[str, Any]]:
        """ターゲット読み込み・検証"""
        try:
            # CSV検証
            validation_result = self.csv_loader.validate_csv_format()

            if not validation_result['valid']:
                error_msg = "CSV検証失敗: " + "; ".join(validation_result['errors'])
                raise CSVError(error_msg)

            # 警告表示
            for warning in validation_result['warnings']:
                self.logger.warning(f"CSV警告: {warning}")

            # ターゲット読み込み
            all_targets = self.csv_loader.load_targets()
            enabled_targets = [t for t in all_targets if t.get('enabled', True)]

            self.processing_stats['total_targets'] = len(enabled_targets)

            if dry_run:
                self.logger.info(f"ドライラン: {len(enabled_targets)}件の有効ターゲットを確認")
            else:
                self.logger.info(f"処理開始: {len(enabled_targets)}件のターゲットを処理します")

            return enabled_targets

        except Exception as e:
            self.logger.error(f"ターゲット読み込みエラー: {str(e)}")
            raise

    def _process_dry_run(self, targets: List[Dict[str, Any]],
                        strategies: List[str]) -> Dict[str, Any]:
        """ドライラン処理"""
        self.logger.info("=== ドライラン実行 ===")

        # 設定情報表示
        self._display_configuration_info(targets, strategies)

        # ターゲット一覧表示
        self._display_target_list(targets)

        # 推定処理時間計算
        estimated_time = self._calculate_estimated_time(len(targets), len(strategies))

        result = {
            'success': True,
            'dry_run': True,
            'targets_count': len(targets),
            'strategies': strategies,
            'estimated_time_minutes': estimated_time,
            'message': f"ドライラン完了: {len(targets)}ターゲット × {len(strategies)}戦略 = {len(targets) * len(strategies)}回の計測予定"
        }

        self.logger.info(f"推定処理時間: {estimated_time:.1f}分")
        return result

    def _process_targets(self, targets: List[Dict[str, Any]],
                        strategies: List[str]) -> Dict[str, Any]:
        """実際のターゲット処理"""
        self.logger.info(f"=== 計測開始: {len(strategies)}戦略 ===")

        all_metrics = []
        failed_items = []

        total_operations = len(targets) * len(strategies)
        current_operation = 0

        for target in targets:
            if self.interrupted:
                self.logger.warning("処理が中断されました")
                break

            for strategy in strategies:
                current_operation += 1

                # 進捗表示
                progress = (current_operation / total_operations) * 100
                self.logger.info(f"進捗 {current_operation}/{total_operations} ({progress:.1f}%) - "
                               f"{target['name']} ({strategy})")

                try:
                    # 単一ターゲット処理
                    metrics = self._process_single_target(target, strategy)
                    all_metrics.append(metrics)

                    self.processing_stats['successful_targets'] += 1

                except PSIRateLimitError as e:
                    self.logger.error(f"レート制限: {target['name']} ({strategy}) - {str(e)}")
                    failed_items.append({
                        'target': target['name'],
                        'url': target['url'],
                        'strategy': strategy,
                        'error': f"レート制限: {str(e)}"
                    })
                    self.processing_stats['failed_targets'] += 1
                    self.processing_stats['rate_limit_hits'] += 1

                    # レート制限の場合は長めに待機
                    if hasattr(e, 'retry_after'):
                        wait_time = min(e.retry_after + 10, 300)  # 最大5分
                        self.logger.info(f"レート制限回復待機: {wait_time}秒")
                        time.sleep(wait_time)

                except Exception as e:
                    self.logger.error(f"処理失敗: {target['name']} ({strategy}) - {str(e)}")
                    failed_items.append({
                        'target': target['name'],
                        'url': target['url'],
                        'strategy': strategy,
                        'error': str(e)
                    })
                    self.processing_stats['failed_targets'] += 1

                self.processing_stats['processed_targets'] += 1

                # 中断チェック
                if self.interrupted:
                    break

        # 結果保存
        summary_file = None
        if all_metrics:
            try:
                summary_file = self.output_manager.save_summary_csv(all_metrics)
                self.logger.info(f"サマリーファイル保存: {summary_file}")
            except Exception as e:
                self.logger.error(f"サマリーファイル保存エラー: {e}")

        # 結果サマリー作成
        success = len(failed_items) == 0 and not self.interrupted
        return self._create_result_summary(
            success=success,
            all_metrics=all_metrics,
            failed_items=failed_items,
            summary_file=summary_file
        )

    def _process_targets_parallel(self, targets: List[Dict[str, Any]],
                                  strategies: List[str]) -> Dict[str, Any]:
        """並列実行でターゲットを処理"""
        total_operations = len(targets) * len(strategies)
        max_workers = self._determine_max_workers(total_operations)

        self.logger.info(f"=== 並列計測開始: workers={max_workers} ===")

        all_metrics: List[Dict[str, Any]] = []
        failed_items: List[Dict[str, Any]] = []

        futures = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for target in targets:
                if self.interrupted:
                    break
                for strategy in strategies:
                    future = executor.submit(self._parallel_worker_task, target, strategy)
                    futures[future] = (target, strategy)

            completed = 0
            total_futures = len(futures)

            for future in as_completed(futures):
                target, strategy = futures[future]
                completed += 1

                if self.interrupted:
                    self.logger.warning("中断シグナルを検知しました。残処理を収束させています。")

                try:
                    result = future.result()
                except Exception as exc:
                    self.logger.error(f"並列タスクエラー: {target['name']} ({strategy}) - {exc}")
                    failed_items.append({
                        'target': target['name'],
                        'url': target['url'],
                        'strategy': strategy,
                        'error': str(exc)
                    })
                    self.processing_stats['failed_targets'] += 1
                    continue

                worker_stats = result.get('psi_stats', {})
                self._merge_psi_stats(worker_stats)
                self.processing_stats['processed_targets'] += 1

                progress = (completed / max(1, total_futures)) * 100
                self.logger.info(f"進捗 {completed}/{total_futures} ({progress:.1f}%) - "
                                 f"{target['name']} ({strategy})")

                status = result.get('status')
                if status == 'success':
                    metrics = result['metrics']
                    self.processing_stats['total_requests'] += 1
                    all_metrics.append(metrics)

                    try:
                        self.output_manager.save_json(result['psi_data'], target['name'], strategy)
                        self.output_manager.append_csv(result['summary'])
                    except Exception as output_error:
                        self.logger.error(f"出力処理エラー: {target['name']} ({strategy}) - {output_error}")
                        failed_items.append({
                            'target': target['name'],
                            'url': target['url'],
                            'strategy': strategy,
                            'error': f"出力処理エラー: {output_error}"
                        })
                        self.processing_stats['failed_targets'] += 1
                        continue

                    self.processing_stats['successful_targets'] += 1

                    self.logger.info(
                        f"計測完了: {target['name']} ({strategy}) - "
                        f"Onload: {metrics.get('onload_ms', 0):.0f}ms, "
                        f"TTFB: {metrics.get('ttfb_ms', 0):.0f}ms, "
                        f"LCP: {metrics.get('lcp_ms', 0):.0f}ms"
                    )
                else:
                    error_message = result.get('error_message', '不明なエラー')
                    if status == 'rate_limit':
                        self.processing_stats['rate_limit_hits'] += 1
                    failed_items.append({
                        'target': target['name'],
                        'url': target['url'],
                        'strategy': strategy,
                        'error': error_message
                    })
                    self.processing_stats['failed_targets'] += 1

        summary_file = None
        if all_metrics:
            try:
                summary_file = self.output_manager.save_summary_csv(all_metrics)
                self.logger.info(f"サマリーファイル保存: {summary_file}")
            except Exception as e:
                self.logger.error(f"サマリーファイル保存エラー: {e}")

        success = len(failed_items) == 0 and not self.interrupted
        return self._create_result_summary(
            success=success,
            all_metrics=all_metrics,
            failed_items=failed_items,
            summary_file=summary_file
        )

    def _parallel_worker_task(self, target: Dict[str, Any], strategy: str) -> Dict[str, Any]:
        worker_client = self._build_psi_client(self.config['api'])
        metrics_extractor = MetricsExtractor()

        response: Dict[str, Any] = {
            'status': 'success',
            'psi_data': None,
            'metrics': None,
            'summary': None,
            'psi_stats': {},
            'error_message': ''
        }

        try:
            psi_data = worker_client.get_page_metrics(target['url'], strategy)
            target_info = {
                'name': target['name'],
                'url': target['url'],
                'strategy': strategy,
                'category': target.get('category', ''),
                'priority': target.get('priority', 'medium'),
                'row_number': target.get('row_number', 0)
            }
            metrics = metrics_extractor.extract_all_metrics(psi_data, target_info)
            response['psi_data'] = psi_data
            response['metrics'] = metrics
            response['summary'] = metrics_extractor.create_summary_metrics(metrics)
        except PSIRateLimitError as e:
            response['status'] = 'rate_limit'
            response['error_message'] = str(e)
        except Exception as e:
            response['status'] = 'error'
            response['error_message'] = str(e)
        finally:
            response['psi_stats'] = worker_client.get_stats(include_success_rate=False)

        return response

    def _should_use_parallel(self, target_count: int, strategy_count: int) -> bool:
        if not self.execution_config.get('parallel'):
            return False

        if self.interrupted:
            return False

        return (target_count * strategy_count) > 1

    def _determine_max_workers(self, total_operations: int) -> int:
        configured = self.execution_config.get('max_workers')
        if isinstance(configured, int) and configured > 0:
            return max(1, min(configured, total_operations))

        cpu_count = os.cpu_count() or 2
        default_workers = max(1, min(4, cpu_count))
        return max(1, min(default_workers, total_operations))

    def _build_psi_client(self, api_config: Dict[str, Any]) -> PSIClient:
        return PSIClient(
            api_key=api_config['key'],
            timeout=api_config.get('timeout', 60),
            retry_count=api_config.get('retry_count', 3),
            base_delay=api_config.get('base_delay', 1),
            max_delay=api_config.get('max_delay', 60)
        )

    def _merge_psi_stats(self, worker_stats: Dict[str, Any]):
        if not worker_stats:
            return

        if hasattr(self.psi_client, 'merge_external_stats'):
            self.psi_client.merge_external_stats(worker_stats)

    def _process_single_target(self, target: Dict[str, Any], strategy: str) -> Dict[str, Any]:
        """単一ターゲットの処理"""
        site_name = target['name']
        url = target['url']

        # PSIデータ取得
        psi_data = self.psi_client.get_page_metrics(url, strategy)
        self.processing_stats['total_requests'] += 1

        # ターゲット情報準備
        target_info = {
            'name': site_name,
            'url': url,
            'strategy': strategy,
            'category': target.get('category', ''),
            'priority': target.get('priority', 'medium'),
            'row_number': target.get('row_number', 0)
        }

        # メトリクス抽出
        metrics = self.metrics_extractor.extract_all_metrics(psi_data, target_info)

        # JSON保存
        json_file = self.output_manager.save_json(psi_data, site_name, strategy)

        # CSV追記
        summary_metrics = self.metrics_extractor.create_summary_metrics(metrics)
        self.output_manager.append_csv(summary_metrics)

        # ログ出力
        self.logger.info(f"計測完了: {site_name} ({strategy}) - "
                        f"Onload: {metrics.get('onload_ms', 0):.0f}ms, "
                        f"TTFB: {metrics.get('ttfb_ms', 0):.0f}ms, "
                        f"LCP: {metrics.get('lcp_ms', 0):.0f}ms")

        return metrics

    def _display_configuration_info(self, targets: List[Dict[str, Any]],
                                   strategies: List[str]):
        """設定情報表示"""
        self.logger.info("=== 設定情報 ===")
        self.logger.info(f"ターゲット数: {len(targets)}")
        self.logger.info(f"計測戦略: {', '.join(strategies)}")
        self.logger.info(f"総計測回数: {len(targets) * len(strategies)}")

        # カテゴリ別集計
        categories = {}
        for target in targets:
            category = target.get('category', '未分類')
            categories[category] = categories.get(category, 0) + 1

        if len(categories) > 1:
            self.logger.info("カテゴリ別内訳:")
            for category, count in sorted(categories.items()):
                self.logger.info(f"  - {category}: {count}件")

    def _display_target_list(self, targets: List[Dict[str, Any]]):
        """ターゲット一覧表示"""
        self.logger.info("=== 計測対象一覧 ===")

        for i, target in enumerate(targets[:10], 1):  # 最初の10件のみ表示
            category = target.get('category', '')
            category_str = f" [{category}]" if category else ""
            self.logger.info(f"{i:2d}. {target['name']}{category_str}: {target['url']}")

        if len(targets) > 10:
            self.logger.info(f"... 他 {len(targets) - 10} 件")

    def _calculate_estimated_time(self, target_count: int, strategy_count: int) -> float:
        """推定処理時間計算（分）"""
        # 1回の計測あたり平均30秒と仮定
        avg_seconds_per_request = 30
        total_requests = target_count * strategy_count
        total_seconds = total_requests * avg_seconds_per_request

        # レート制限による追加時間を考慮（10%増し）
        total_seconds *= 1.1

        return total_seconds / 60

    def _create_result_summary(self, success: bool, message: str = None,
                              all_metrics: List[Dict[str, Any]] = None,
                              failed_items: List[Dict[str, Any]] = None,
                              summary_file: str = None) -> Dict[str, Any]:
        """結果サマリー作成"""
        end_time = datetime.now()
        start_time = self.processing_stats['start_time'] or end_time
        duration = end_time - start_time

        result = {
            'success': success,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration.total_seconds(),
            'stats': self.processing_stats.copy(),
            'component_stats': {
                'psi_client': self.psi_client.get_stats(),
                'metrics_extractor': self.metrics_extractor.get_stats(),
                'output_manager': self.output_manager.get_stats()
            }
        }

        if message:
            result['message'] = message

        if all_metrics:
            result['metrics_count'] = len(all_metrics)
            result['summary_file'] = summary_file

        if failed_items:
            result['failed_items'] = failed_items
            result['failure_count'] = len(failed_items)

        return result


# CLI インターフェース
@click.command()
@click.option('--config', '-c', default='config/config.yaml',
              help='設定ファイルパス', type=click.Path(exists=True))
@click.option('--strategy', '-s',
              type=click.Choice(['mobile', 'desktop', 'both']),
              default='both', help='計測戦略')
@click.option('--dry-run', is_flag=True, help='ドライラン実行（実際の計測は行わない）')
@click.option('--targets-csv', help='計測対象CSVファイルパス（設定ファイルを上書き）')
@click.option('--verbose', '-v', is_flag=True, help='詳細ログ出力')
def cli(config: str, strategy: str, dry_run: bool, targets_csv: str, verbose: bool):
    """PSI Lab Metrics Tool - ウェブサイト速度計測ツール"""

    try:
        # 設定読み込み
        config_manager = ConfigManager()
        config_data = config_manager.load_config(config)

        # CSVファイルパス上書き
        if targets_csv:
            config_data['input']['targets_csv'] = targets_csv

        # 詳細ログ設定
        if verbose:
            config_data['logging']['level'] = 'DEBUG'

        # 戦略設定
        if strategy == 'both':
            strategies = ['mobile', 'desktop']
        else:
            strategies = [strategy]

        # メイン処理実行
        processor = MainProcessor(config_data)
        results = processor.process_all_targets(strategies, dry_run)

        # 結果出力
        if results['success']:
            if dry_run:
                click.echo(f" ドライラン完了: {results.get('message', '')}")
            else:
                stats = results.get('stats', {})
                click.echo(f" 処理完了: {stats.get('successful_targets', 0)}件成功 / "
                          f"{stats.get('processed_targets', 0)}件処理")

                if results.get('summary_file'):
                    click.echo(f"結果ファイル: {results['summary_file']}")

            sys.exit(0)
        else:
            if dry_run:
                click.echo(f" ドライラン失敗: {results.get('message', '')}")
            else:
                stats = results.get('stats', {})
                failed_count = results.get('failure_count', 0)
                click.echo(f" 処理完了（エラーあり）: {stats.get('successful_targets', 0)}件成功, "
                          f"{failed_count}件失敗")

                # 失敗詳細表示
                failed_items = results.get('failed_items', [])
                if failed_items:
                    click.echo("\n失敗詳細:")
                    for item in failed_items[:5]:  # 最初の5件のみ表示
                        click.echo(f"  - {item['target']} ({item['strategy']}): {item['error']}")

                    if len(failed_items) > 5:
                        click.echo(f"  ... 他 {len(failed_items) - 5} 件")

            sys.exit(1)

    except ConfigError as e:
        click.echo(f" 設定エラー: {str(e)}")
        sys.exit(1)
    except CSVError as e:
        click.echo(f" CSV エラー: {str(e)}")
        sys.exit(1)
    except Exception as e:
        click.echo(f" 予期しないエラー: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    cli()
