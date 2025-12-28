"""
sitespeed.io メインプロセッサ

sitespeed.ioを使用してWaterfall詳細データを取得するCLIツール。
PSI Lab Metrics Toolと同じtargets.csvを使用可能。
"""

import json
import logging
import shutil
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from .config_manager import ConfigManager, ConfigError
from .csv_loader import CSVLoader, CSVError
from .sitespeed_client import (
    SitespeedClient,
    SitespeedError,
    SitespeedNotFoundError,
    check_sitespeed_installation,
)
from .sitespeed_extractor import SitespeedExtractor, SitespeedExtractionError

logger = logging.getLogger(__name__)


class SitespeedProcessor:
    """sitespeed.io処理クラス"""

    def __init__(self, config: Dict[str, Any]):
        """
        SitespeedProcessor初期化

        Args:
            config: 設定辞書
        """
        self.config = config
        self.sitespeed_config = config.get('sitespeed', {})
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
        }

        self.logger = logging.getLogger(__name__)
        self.logger.info("SitespeedProcessorを初期化しました")

    def _signal_handler(self, signum, frame):
        """シグナルハンドラー"""
        self.interrupted = True
        self.logger.warning(f"処理中断シグナルを受信しました: {signum}")

    def _setup_logging(self):
        """ログ設定"""
        log_config = self.config.get('logging', {})
        log_file = self.config['output']['log_file'].replace(
            'execution.log', 'sitespeed_execution.log'
        )

        Path(log_file).parent.mkdir(parents=True, exist_ok=True)

        log_level = getattr(logging, log_config.get('level', 'INFO').upper())
        log_format = log_config.get(
            'format', '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )

        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(console_handler)

        logging.getLogger('urllib3').setLevel(logging.WARNING)

    def _initialize_components(self):
        """コンポーネント初期化"""
        try:
            ss_config = self.sitespeed_config

            # sitespeed.ioクライアント
            self.sitespeed_client = SitespeedClient(
                output_base_dir=ss_config.get('output_dir', './output/sitespeed'),
                browser=ss_config.get('browser', 'chrome'),
                iterations=ss_config.get('iterations', 1),
                connectivity=ss_config.get('connectivity', 'native'),
                mobile=ss_config.get('mobile', False),
                docker=ss_config.get('docker', False),
                docker_image=ss_config.get('docker_image', 'sitespeedio/sitespeed.io:latest'),
                timeout=ss_config.get('timeout', 300),
            )

            # CSV読み込み
            input_config = self.config['input']
            self.csv_loader = CSVLoader(
                csv_path=input_config['targets_csv'],
                encoding=input_config.get('csv_encoding', 'utf-8-sig'),
            )

            # Waterfall抽出
            self.extractor = SitespeedExtractor()

            # Waterfall出力ディレクトリ
            self.waterfall_dir = Path(ss_config.get('waterfall_dir', './output/waterfall'))
            self.waterfall_dir.mkdir(parents=True, exist_ok=True)

        except SitespeedNotFoundError as e:
            raise ConfigError(str(e))
        except Exception as e:
            raise RuntimeError(f"コンポーネント初期化エラー: {str(e)}")

    def process_all_targets(
        self,
        mobile: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        全ターゲットの処理

        Args:
            mobile: モバイルテスト
            dry_run: ドライラン実行

        Returns:
            処理結果辞書
        """
        self.processing_stats['start_time'] = datetime.now()

        try:
            # ターゲット読み込み
            targets = self._load_targets()
            if not targets:
                return self._create_result_summary(
                    success=False, message="有効なターゲットがありません"
                )

            self.processing_stats['total_targets'] = len(targets)

            # ドライラン
            if dry_run:
                return self._process_dry_run(targets, mobile)

            # 実際の処理
            return self._process_targets(targets, mobile)

        except Exception as e:
            self.logger.error(f"処理中に致命的エラー: {str(e)}")
            return self._create_result_summary(success=False, message=str(e))

        finally:
            self.processing_stats['end_time'] = datetime.now()

    def _load_targets(self) -> List[Dict[str, Any]]:
        """ターゲット読み込み"""
        validation_result = self.csv_loader.validate_csv_format()

        if not validation_result['valid']:
            raise CSVError("CSV検証失敗: " + "; ".join(validation_result['errors']))

        all_targets = self.csv_loader.load_targets()
        enabled_targets = [t for t in all_targets if t.get('enabled', True)]

        self.logger.info(f"処理対象: {len(enabled_targets)}件のターゲット")
        return enabled_targets

    def _process_dry_run(
        self,
        targets: List[Dict[str, Any]],
        mobile: bool,
    ) -> Dict[str, Any]:
        """ドライラン処理"""
        self.logger.info("=== ドライラン実行 ===")

        strategy = 'mobile' if mobile else 'desktop'
        self.logger.info(f"テスト戦略: {strategy}")
        self.logger.info(f"ターゲット数: {len(targets)}")
        self.logger.info(f"ブラウザ: {self.sitespeed_config.get('browser', 'chrome')}")
        self.logger.info(f"繰り返し: {self.sitespeed_config.get('iterations', 1)}回")

        for i, target in enumerate(targets[:5], 1):
            self.logger.info(f"  {i}. {target['name']}: {target['url']}")

        if len(targets) > 5:
            self.logger.info(f"  ... 他 {len(targets) - 5} 件")

        # 推定時間（1テストあたり約1-2分）
        iterations = self.sitespeed_config.get('iterations', 1)
        estimated_minutes = len(targets) * iterations * 1.5

        return {
            'success': True,
            'dry_run': True,
            'targets_count': len(targets),
            'strategy': strategy,
            'estimated_time_minutes': estimated_minutes,
            'message': f"ドライラン完了: {len(targets)}ターゲット（推定{estimated_minutes:.0f}分）",
        }

    def _process_targets(
        self,
        targets: List[Dict[str, Any]],
        mobile: bool,
    ) -> Dict[str, Any]:
        """ターゲット処理"""
        strategy = 'mobile' if mobile else 'desktop'
        self.logger.info(f"=== sitespeed.io計測開始 ({strategy}) ===")

        results = []
        failed_items = []

        for idx, target in enumerate(targets, 1):
            if self.interrupted:
                self.logger.warning("処理が中断されました")
                break

            progress = (idx / len(targets)) * 100
            self.logger.info(f"進捗 {idx}/{len(targets)} ({progress:.1f}%) - {target['name']}")

            try:
                result = self._process_single_target(target, mobile)
                results.append(result)
                self.processing_stats['successful_targets'] += 1

            except Exception as e:
                self.logger.error(f"処理失敗: {target['name']} - {str(e)}")
                failed_items.append({
                    'target': target['name'],
                    'url': target['url'],
                    'error': str(e),
                })
                self.processing_stats['failed_targets'] += 1

            self.processing_stats['processed_targets'] += 1

        success = len(failed_items) == 0 and not self.interrupted
        return self._create_result_summary(
            success=success, results=results, failed_items=failed_items
        )

    def _process_single_target(
        self,
        target: Dict[str, Any],
        mobile: bool,
    ) -> Dict[str, Any]:
        """単一ターゲット処理"""
        site_name = target['name']
        url = target['url']

        self.logger.info(f"sitespeed.ioテスト実行中: {site_name}")

        # モバイル設定を一時的に上書き
        original_mobile = self.sitespeed_client.mobile
        self.sitespeed_client.mobile = mobile

        try:
            # sitespeed.io実行
            test_result = self.sitespeed_client.run_test(
                url=url,
                site_name=site_name,
            )

            # HARからWaterfallデータ抽出
            waterfall_data = None
            if test_result.get('har_files'):
                har_file = test_result['har_files'][0]
                target_info = {
                    'name': site_name,
                    'url': url,
                    'mobile': mobile,
                    'browser': self.sitespeed_client.browser,
                }
                waterfall_data = self.extractor.extract_waterfall_from_har(
                    har_file, target_info
                )

                # Waterfallデータ保存
                waterfall_file = self._save_waterfall_data(waterfall_data, site_name, mobile)
                test_result['waterfall_file'] = str(waterfall_file)

            # 結果ログ
            metrics = test_result.get('metrics', {})
            self.logger.info(
                f"計測完了: {site_name} - "
                f"TTFB: {metrics.get('ttfb_ms', 'N/A')}ms, "
                f"Load: {metrics.get('load_event_ms', 'N/A')}ms, "
                f"Requests: {metrics.get('total_requests', 'N/A')}"
            )

            return test_result

        finally:
            self.sitespeed_client.mobile = original_mobile

    def _save_waterfall_data(
        self,
        waterfall_data: Dict[str, Any],
        site_name: str,
        mobile: bool,
    ) -> Path:
        """Waterfallデータをファイルに保存"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        strategy = 'mobile' if mobile else 'desktop'

        safe_name = "".join(c if c.isalnum() or c in '-_' else '_' for c in site_name)
        filename = f"{safe_name}_{strategy}_{timestamp}_waterfall.json"
        output_path = self.waterfall_dir / filename

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(waterfall_data, f, ensure_ascii=False, indent=2)

        self.logger.debug(f"Waterfallデータ保存: {output_path}")
        return output_path

    def _create_result_summary(
        self,
        success: bool,
        message: str = None,
        results: List[Dict[str, Any]] = None,
        failed_items: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
            'waterfall_dir': str(self.waterfall_dir),
        }

        if message:
            result['message'] = message

        if results:
            result['results'] = results
            result['results_count'] = len(results)

        if failed_items:
            result['failed_items'] = failed_items
            result['failure_count'] = len(failed_items)

        return result


@click.command()
@click.option(
    '--config', '-c',
    default='config/config.yaml',
    help='設定ファイルパス',
    type=click.Path(exists=True),
)
@click.option('--mobile', '-m', is_flag=True, help='モバイルテスト実行')
@click.option('--dry-run', is_flag=True, help='ドライラン実行')
@click.option('--targets-csv', help='計測対象CSVファイルパス')
@click.option('--docker', is_flag=True, help='Dockerモードで実行')
@click.option('--verbose', '-v', is_flag=True, help='詳細ログ出力')
@click.option('--check', is_flag=True, help='sitespeed.ioインストール状況確認')
def cli(
    config: str,
    mobile: bool,
    dry_run: bool,
    targets_csv: str,
    docker: bool,
    verbose: bool,
    check: bool,
):
    """sitespeed.io Waterfall Tool - 詳細タイミングデータ取得ツール"""

    # インストール確認モード
    if check:
        result = check_sitespeed_installation()
        click.echo("=== sitespeed.io インストール状況 ===")
        click.echo(f"sitespeed.io (ローカル): {'✓ ' + (result['sitespeed_version'] or '') if result['sitespeed_local'] else '✗ 未インストール'}")
        click.echo(f"Docker: {'✓ ' + (result['docker_version'] or '') if result['docker'] else '✗ 未インストール'}")
        click.echo("")

        if result['recommended_method']:
            click.echo(f"推奨実行方法: {result['recommended_method']}")
        else:
            click.echo("sitespeed.ioをインストールしてください:")
            click.echo("  npm install -g sitespeed.io")
            click.echo("または Docker をインストール:")
            click.echo("  https://docs.docker.com/get-docker/")

        sys.exit(0)

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

        # sitespeed設定がない場合はデフォルト作成
        if 'sitespeed' not in config_data:
            config_data['sitespeed'] = {}

        # Dockerモード上書き
        if docker:
            config_data['sitespeed']['docker'] = True

        # メイン処理実行
        processor = SitespeedProcessor(config_data)
        results = processor.process_all_targets(mobile=mobile, dry_run=dry_run)

        # 結果出力
        if results['success']:
            if dry_run:
                click.echo(f"ドライラン完了: {results.get('message', '')}")
            else:
                stats = results.get('stats', {})
                click.echo(
                    f"処理完了: {stats.get('successful_targets', 0)}件成功 / "
                    f"{stats.get('processed_targets', 0)}件処理"
                )
                click.echo(f"Waterfall出力: {results.get('waterfall_dir', '')}")

            sys.exit(0)
        else:
            stats = results.get('stats', {})
            failed_count = results.get('failure_count', 0)
            click.echo(
                f"処理完了（エラーあり）: {stats.get('successful_targets', 0)}件成功, "
                f"{failed_count}件失敗"
            )

            failed_items = results.get('failed_items', [])
            if failed_items:
                click.echo("\n失敗詳細:")
                for item in failed_items[:5]:
                    click.echo(f"  - {item['target']}: {item['error']}")

            sys.exit(1)

    except ConfigError as e:
        click.echo(f"設定エラー: {str(e)}")
        sys.exit(1)
    except CSVError as e:
        click.echo(f"CSVエラー: {str(e)}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"予期しないエラー: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    cli()
