"""
sitespeed.io クライアントモジュール

sitespeed.ioをサブプロセスとして実行し、
HAR/Waterfall/メトリクスを取得します。
"""

import json
import logging
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SitespeedError(Exception):
    """sitespeed.io関連のエラー"""

    def __init__(self, message: str, return_code: Optional[int] = None):
        super().__init__(message)
        self.return_code = return_code


class SitespeedNotFoundError(SitespeedError):
    """sitespeed.ioがインストールされていない"""
    pass


class SitespeedClient:
    """sitespeed.io CLIラッパー"""

    # デフォルト設定
    DEFAULT_ITERATIONS = 1
    DEFAULT_BROWSER = "chrome"
    DEFAULT_CONNECTIVITY = "native"  # ネットワーク制限なし

    # 接続プロファイル
    CONNECTIVITY_PROFILES = {
        "native": None,  # 制限なし
        "cable": {"down": 5000, "up": 1000, "rtt": 28},
        "4g": {"down": 9000, "up": 9000, "rtt": 170},
        "3g": {"down": 1600, "up": 768, "rtt": 300},
        "3gfast": {"down": 1600, "up": 768, "rtt": 150},
    }

    def __init__(
        self,
        output_base_dir: str = "./output/sitespeed",
        browser: str = DEFAULT_BROWSER,
        iterations: int = DEFAULT_ITERATIONS,
        connectivity: str = DEFAULT_CONNECTIVITY,
        mobile: bool = False,
        docker: bool = False,
        docker_image: str = "sitespeedio/sitespeed.io:latest",
        timeout: int = 300,
    ):
        """
        SitespeedClient初期化

        Args:
            output_base_dir: 結果出力ベースディレクトリ
            browser: ブラウザ (chrome, firefox)
            iterations: 計測繰り返し回数
            connectivity: 接続プロファイル (native, cable, 4g, 3g, 3gfast)
            mobile: モバイルエミュレーション
            docker: Dockerで実行するか
            docker_image: 使用するDockerイメージ
            timeout: 実行タイムアウト（秒）
        """
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)

        self.browser = browser
        self.iterations = max(1, iterations)
        self.connectivity = connectivity
        self.mobile = mobile
        self.docker = docker
        self.docker_image = docker_image
        self.timeout = timeout

        # sitespeed.ioの存在確認
        self._verify_installation()

        # 統計情報
        self.stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
        }

        logger.info(
            f"SitespeedClientを初期化しました "
            f"(browser={browser}, iterations={iterations}, docker={docker})"
        )

    def _verify_installation(self):
        """sitespeed.ioのインストール確認"""
        if self.docker:
            # Dockerの確認
            if not shutil.which("docker"):
                raise SitespeedNotFoundError(
                    "Dockerがインストールされていません。"
                    "https://docs.docker.com/get-docker/ からインストールしてください。"
                )
            logger.debug("Docker実行モードで動作します")
        else:
            # ローカルインストールの確認
            if not shutil.which("sitespeed.io"):
                raise SitespeedNotFoundError(
                    "sitespeed.ioがインストールされていません。\n"
                    "インストール方法:\n"
                    "  npm install -g sitespeed.io\n"
                    "または Docker モードを使用:\n"
                    "  --docker オプションを指定"
                )
            logger.debug("ローカルsitespeed.ioで動作します")

    def run_test(
        self,
        url: str,
        site_name: Optional[str] = None,
        extra_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        sitespeed.ioテストを実行

        Args:
            url: テスト対象URL
            site_name: サイト名（出力フォルダ名に使用）
            extra_options: 追加オプション

        Returns:
            テスト結果（出力パス、メトリクス等）
        """
        self.stats['total_runs'] += 1

        # 出力フォルダ作成
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = self._sanitize_name(site_name or self._extract_domain(url))
        output_dir = self.output_base_dir / f"{safe_name}_{timestamp}"

        logger.info(f"sitespeed.ioテスト開始: {url}")

        try:
            # コマンド構築
            cmd = self._build_command(url, output_dir, extra_options)
            logger.debug(f"実行コマンド: {' '.join(cmd)}")

            # 実行
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            if result.returncode != 0:
                logger.error(f"sitespeed.io実行エラー: {result.stderr}")
                raise SitespeedError(
                    f"sitespeed.io実行失敗: {result.stderr[:500]}",
                    result.returncode
                )

            # 結果解析
            test_result = self._parse_results(output_dir, url, site_name)
            self.stats['successful_runs'] += 1

            logger.info(
                f"テスト完了: {site_name or url} - "
                f"TTFB: {test_result.get('metrics', {}).get('ttfb_ms', 'N/A')}ms"
            )

            return test_result

        except subprocess.TimeoutExpired:
            self.stats['failed_runs'] += 1
            raise SitespeedError(f"タイムアウト ({self.timeout}秒)")

        except Exception as e:
            self.stats['failed_runs'] += 1
            if isinstance(e, SitespeedError):
                raise
            raise SitespeedError(f"テスト実行エラー: {str(e)}")

    def _build_command(
        self,
        url: str,
        output_dir: Path,
        extra_options: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """sitespeed.ioコマンドを構築"""

        if self.docker:
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{output_dir.absolute()}:/sitespeed.io",
                self.docker_image,
            ]
        else:
            cmd = ["sitespeed.io"]

        # 基本オプション
        cmd.extend([
            url,
            "--outputFolder", str(output_dir) if not self.docker else "/sitespeed.io",
            "-b", self.browser,
            "-n", str(self.iterations),
        ])

        # 接続プロファイル
        if self.connectivity != "native":
            cmd.extend(["-c", self.connectivity])

        # モバイル
        if self.mobile:
            cmd.append("--mobile")

        # ビジュアルメトリクス有効化
        cmd.append("--visualMetrics")

        # スクリーンショット
        cmd.extend(["--screenshot.type", "png"])

        # 追加オプション
        if extra_options:
            for key, value in extra_options.items():
                if value is True:
                    cmd.append(f"--{key}")
                elif value is not False and value is not None:
                    cmd.extend([f"--{key}", str(value)])

        return cmd

    def _parse_results(
        self,
        output_dir: Path,
        url: str,
        site_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """結果を解析"""
        result = {
            'url': url,
            'site_name': site_name or self._extract_domain(url),
            'output_dir': str(output_dir),
            'timestamp': datetime.now().isoformat(),
            'browser': self.browser,
            'iterations': self.iterations,
            'mobile': self.mobile,
            'metrics': {},
            'har_files': [],
            'screenshot_files': [],
            'waterfall_files': [],
        }

        # HAR ファイル検索
        har_files = list(output_dir.rglob("*.har"))
        result['har_files'] = [str(f) for f in har_files]

        if har_files:
            # 最初のHARからメトリクス抽出
            result['metrics'] = self._extract_metrics_from_har(har_files[0])

        # browsertime結果JSON検索
        browsertime_files = list(output_dir.rglob("browsertime.json"))
        if browsertime_files:
            metrics = self._extract_metrics_from_browsertime(browsertime_files[0])
            result['metrics'].update(metrics)

        # スクリーンショット検索
        screenshot_files = list(output_dir.rglob("*.png"))
        result['screenshot_files'] = [str(f) for f in screenshot_files]

        # Waterfall HTML検索
        waterfall_files = list(output_dir.rglob("*waterfall*"))
        result['waterfall_files'] = [str(f) for f in waterfall_files]

        return result

    def _extract_metrics_from_har(self, har_path: Path) -> Dict[str, Any]:
        """HARファイルからメトリクスを抽出"""
        metrics = {}

        try:
            with open(har_path, 'r', encoding='utf-8') as f:
                har_data = json.load(f)

            entries = har_data.get('log', {}).get('entries', [])

            if entries:
                # 最初のリクエスト（メインドキュメント）のタイミング
                first_entry = entries[0]
                timings = first_entry.get('timings', {})

                metrics['dns_ms'] = max(0, timings.get('dns', 0))
                metrics['connect_ms'] = max(0, timings.get('connect', 0))
                metrics['ssl_ms'] = max(0, timings.get('ssl', 0))
                metrics['ttfb_ms'] = max(0, timings.get('wait', 0))
                metrics['download_ms'] = max(0, timings.get('receive', 0))

                # 総リクエスト数とサイズ
                metrics['total_requests'] = len(entries)
                metrics['total_size'] = sum(
                    e.get('response', {}).get('bodySize', 0)
                    for e in entries
                )

        except Exception as e:
            logger.warning(f"HARメトリクス抽出エラー: {e}")

        return metrics

    def _extract_metrics_from_browsertime(self, bt_path: Path) -> Dict[str, Any]:
        """browsertime.jsonからメトリクスを抽出"""
        metrics = {}

        try:
            with open(bt_path, 'r', encoding='utf-8') as f:
                bt_data = json.load(f)

            # 最初のURLの結果
            if bt_data and len(bt_data) > 0:
                first_result = bt_data[0]

                # browserScripts からタイミング取得
                browser_scripts = first_result.get('browserScripts', [])
                if browser_scripts and len(browser_scripts) > 0:
                    scripts = browser_scripts[0]
                    timings = scripts.get('timings', {})

                    # Navigation Timing
                    nav_timing = timings.get('navigationTiming', {})
                    if nav_timing:
                        metrics['dom_content_loaded_ms'] = nav_timing.get(
                            'domContentLoadedEventStart', 0
                        )
                        metrics['load_event_ms'] = nav_timing.get(
                            'loadEventStart', 0
                        )

                    # Paint Timing
                    paint_timing = timings.get('paintTiming', {})
                    if paint_timing:
                        metrics['fcp_ms'] = paint_timing.get(
                            'first-contentful-paint', 0
                        )

                    # LCP
                    lcp = timings.get('largestContentfulPaint', {})
                    if lcp:
                        metrics['lcp_ms'] = lcp.get('renderTime', 0)

                # visualMetrics
                visual_metrics = first_result.get('visualMetrics', [])
                if visual_metrics and len(visual_metrics) > 0:
                    vm = visual_metrics[0]
                    metrics['speed_index'] = vm.get('SpeedIndex', 0)
                    metrics['first_visual_change_ms'] = vm.get('FirstVisualChange', 0)
                    metrics['last_visual_change_ms'] = vm.get('LastVisualChange', 0)
                    metrics['visual_complete_85_ms'] = vm.get('VisualComplete85', 0)
                    metrics['visual_complete_99_ms'] = vm.get('VisualComplete99', 0)

        except Exception as e:
            logger.warning(f"browsertimeメトリクス抽出エラー: {e}")

        return metrics

    def _sanitize_name(self, name: str) -> str:
        """ファイル名として使用可能な文字列に変換"""
        return "".join(c if c.isalnum() or c in '-_' else '_' for c in name)

    def _extract_domain(self, url: str) -> str:
        """URLからドメインを抽出"""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc.replace(':', '_')
        except Exception:
            return "unknown"

    def get_stats(self) -> Dict[str, Any]:
        """統計情報を取得"""
        stats = self.stats.copy()
        if stats['total_runs'] > 0:
            stats['success_rate'] = stats['successful_runs'] / stats['total_runs']
        else:
            stats['success_rate'] = 0.0
        return stats

    def reset_stats(self):
        """統計情報をリセット"""
        self.stats = {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
        }


def check_sitespeed_installation() -> Dict[str, Any]:
    """sitespeed.ioのインストール状況をチェック"""
    result = {
        'sitespeed_local': False,
        'sitespeed_version': None,
        'docker': False,
        'docker_version': None,
        'recommended_method': None,
    }

    # ローカルsitespeed.io確認
    if shutil.which("sitespeed.io"):
        result['sitespeed_local'] = True
        try:
            version_result = subprocess.run(
                ["sitespeed.io", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            result['sitespeed_version'] = version_result.stdout.strip()
        except Exception:
            pass

    # Docker確認
    if shutil.which("docker"):
        result['docker'] = True
        try:
            version_result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            result['docker_version'] = version_result.stdout.strip()
        except Exception:
            pass

    # 推奨方法判定
    if result['sitespeed_local']:
        result['recommended_method'] = 'local'
    elif result['docker']:
        result['recommended_method'] = 'docker'
    else:
        result['recommended_method'] = None

    return result
