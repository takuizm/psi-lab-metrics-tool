"""
PSI APIクライアントモジュール

Google PageSpeed Insights APIとの通信を行います。
レート制限、リトライ機能、エラーハンドリングを含む堅牢な実装。
"""

import time
import random
import requests
import logging
from typing import Dict, Optional, Any
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class PSIAPIError(Exception):
    """PSI API関連のエラー"""

    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class PSIRateLimitError(PSIAPIError):
    """レート制限エラー"""

    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class PSIClient:
    """PageSpeed Insights API クライアント"""

    # PSI APIエンドポイント
    BASE_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

    # デフォルト設定
    DEFAULT_TIMEOUT = 60
    DEFAULT_RETRY_COUNT = 3
    DEFAULT_BASE_DELAY = 1
    DEFAULT_MAX_DELAY = 60

    # HTTPステータスコード
    STATUS_OK = 200
    STATUS_BAD_REQUEST = 400
    STATUS_FORBIDDEN = 403
    STATUS_TOO_MANY_REQUESTS = 429
    STATUS_SERVER_ERROR_START = 500

    def __init__(self,
                 api_key: str,
                 timeout: int = DEFAULT_TIMEOUT,
                 retry_count: int = DEFAULT_RETRY_COUNT,
                 base_delay: float = DEFAULT_BASE_DELAY,
                 max_delay: float = DEFAULT_MAX_DELAY):
        """
        PSIClient初期化

        Args:
            api_key: PSI APIキー
            timeout: リクエストタイムアウト（秒）
            retry_count: リトライ回数
            base_delay: 基本遅延時間（秒）
            max_delay: 最大遅延時間（秒）
        """
        if not api_key or api_key.strip() == '':
            raise ValueError("PSI APIキーが設定されていません")

        self.api_key = api_key.strip()
        self.timeout = max(10, timeout)  # 最小10秒
        self.retry_count = max(0, retry_count)
        self.base_delay = max(0.1, base_delay)
        self.max_delay = max(base_delay, max_delay)

        # HTTPセッション設定
        self.session = self._create_session()

        # 統計情報
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'rate_limit_hits': 0,
            'retries_performed': 0
        }

        logger.info(f"PSIClientを初期化しました（タイムアウト: {self.timeout}秒, リトライ: {self.retry_count}回）")

    def _create_session(self) -> requests.Session:
        """HTTPセッションを作成"""
        session = requests.Session()

        # リトライ戦略（接続エラーのみ）
        retry_strategy = Retry(
            total=2,  # 接続レベルのリトライ
            connect=2,
            read=1,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # ユーザーエージェント設定
        session.headers.update({
            'User-Agent': 'PSI-Lab-Metrics-Tool/1.0'
        })

        return session

    def get_page_metrics(self, url: str, strategy: str = "mobile") -> Dict[str, Any]:
        """
        指定URLのPSIメトリクスを取得

        Args:
            url: 計測対象URL
            strategy: 'mobile' または 'desktop'

        Returns:
            PSI APIレスポンス（JSON）

        Raises:
            PSIAPIError: API呼び出し失敗時
            PSIRateLimitError: レート制限時
        """
        if not self._is_valid_url(url):
            raise PSIAPIError(f"無効なURL形式です: {url}")

        if strategy not in ('mobile', 'desktop'):
            raise PSIAPIError(f"無効なstrategy値です: {strategy}")

        self.stats['total_requests'] += 1

        params = {
            'url': url,
            'key': self.api_key,
            'strategy': strategy,
            'category': 'performance',
            'locale': 'ja'
        }

        logger.info(f"PSI計測開始: {url} ({strategy})")
        start_time = time.time()

        try:
            response_data = self._make_request_with_retry(params)

            # 成功統計更新
            self.stats['successful_requests'] += 1
            elapsed_time = time.time() - start_time

            logger.info(f"PSI計測完了: {url} ({strategy}) - {elapsed_time:.2f}秒")
            return response_data

        except Exception as e:
            self.stats['failed_requests'] += 1
            elapsed_time = time.time() - start_time

            logger.error(f"PSI計測失敗: {url} ({strategy}) - {elapsed_time:.2f}秒 - {str(e)}")
            raise

    def _make_request_with_retry(self, params: Dict[str, str]) -> Dict[str, Any]:
        """リトライ機能付きリクエスト実行"""
        last_exception = None

        for attempt in range(self.retry_count + 1):
            try:
                response = self.session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=self.timeout
                )

                return self._handle_response(response)

            except PSIRateLimitError as e:
                last_exception = e
                self.stats['rate_limit_hits'] += 1

                if attempt < self.retry_count:
                    delay = e.retry_after + random.uniform(0, 5)  # ジッター追加
                    self.stats['retries_performed'] += 1

                    logger.warning(f"レート制限（試行 {attempt + 1}/{self.retry_count + 1}）"
                                 f"- {delay:.1f}秒後にリトライします")
                    time.sleep(delay)
                    continue
                else:
                    raise

            except PSIAPIError as e:
                last_exception = e

                # サーバーエラーの場合のみリトライ
                if (e.status_code and e.status_code >= self.STATUS_SERVER_ERROR_START
                    and attempt < self.retry_count):

                    delay = self._calculate_backoff_delay(attempt)
                    self.stats['retries_performed'] += 1

                    logger.warning(f"サーバーエラー（試行 {attempt + 1}/{self.retry_count + 1}）"
                                 f"- {delay:.1f}秒後にリトライします: {str(e)}")
                    time.sleep(delay)
                    continue
                else:
                    raise

            except requests.RequestException as e:
                last_exception = PSIAPIError(f"リクエストエラー: {str(e)}")

                if attempt < self.retry_count:
                    delay = self._calculate_backoff_delay(attempt)
                    self.stats['retries_performed'] += 1

                    logger.warning(f"接続エラー（試行 {attempt + 1}/{self.retry_count + 1}）"
                                 f"- {delay:.1f}秒後にリトライします: {str(e)}")
                    time.sleep(delay)
                    continue
                else:
                    raise last_exception

        # ここに到達することはないが、安全のため
        raise last_exception or PSIAPIError("リトライ回数を超過しました")

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        """レスポンス処理とエラーハンドリング"""
        if response.status_code == self.STATUS_OK:
            try:
                return response.json()
            except ValueError as e:
                raise PSIAPIError(f"JSONパースエラー: {str(e)}", response.status_code)

        # エラーレスポンスの詳細取得
        error_data = None
        try:
            error_data = response.json()
        except ValueError:
            pass

        if response.status_code == self.STATUS_BAD_REQUEST:
            error_msg = "不正なリクエスト"
            if error_data and 'error' in error_data:
                error_msg += f": {error_data['error'].get('message', '')}"
            raise PSIAPIError(error_msg, response.status_code, error_data)

        elif response.status_code == self.STATUS_FORBIDDEN:
            error_msg = "APIキーが無効またはAPIが無効化されています"
            if error_data and 'error' in error_data:
                error_msg += f": {error_data['error'].get('message', '')}"
            raise PSIAPIError(error_msg, response.status_code, error_data)

        elif response.status_code == self.STATUS_TOO_MANY_REQUESTS:
            retry_after = int(response.headers.get('Retry-After', 60))
            error_msg = f"レート制限に達しました（{retry_after}秒後にリトライ可能）"
            raise PSIRateLimitError(error_msg, retry_after)

        elif response.status_code >= self.STATUS_SERVER_ERROR_START:
            error_msg = f"サーバーエラー（{response.status_code}）"
            if error_data and 'error' in error_data:
                error_msg += f": {error_data['error'].get('message', '')}"
            raise PSIAPIError(error_msg, response.status_code, error_data)

        else:
            error_msg = f"予期しないエラー（{response.status_code}）"
            raise PSIAPIError(error_msg, response.status_code, error_data)

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """指数バックオフ遅延時間計算"""
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        jitter = random.uniform(0, delay * 0.1)  # 10%のジッター
        return delay + jitter

    def _is_valid_url(self, url: str) -> bool:
        """URL形式の基本検証"""
        return (isinstance(url, str) and
                url.strip() and
                (url.startswith('http://') or url.startswith('https://')) and
                len(url) <= 2000)

    def get_stats(self) -> Dict[str, Any]:
        """統計情報を取得"""
        stats = self.stats.copy()
        if stats['total_requests'] > 0:
            stats['success_rate'] = stats['successful_requests'] / stats['total_requests']
        else:
            stats['success_rate'] = 0.0
        return stats

    def reset_stats(self):
        """統計情報をリセット"""
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'rate_limit_hits': 0,
            'retries_performed': 0
        }
        logger.debug("PSI統計情報をリセットしました")

    def __del__(self):
        """デストラクタ - セッションを閉じる"""
        if hasattr(self, 'session'):
            try:
                self.session.close()
            except Exception:
                pass
