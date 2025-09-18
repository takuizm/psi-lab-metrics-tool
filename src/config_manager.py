"""
設定管理モジュール

設定ファイルの読み込み、環境変数の処理、設定値の検証を行います。
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """設定関連のエラー"""
    pass


class ConfigManager:
    """設定ファイル管理クラス"""

    def __init__(self):
        self._config: Optional[Dict[str, Any]] = None
        self._config_path: Optional[Path] = None

    def load_config(self, config_path: str) -> Dict[str, Any]:
        """
        設定ファイルを読み込み、環境変数を適用

        Args:
            config_path: 設定ファイルのパス

        Returns:
            設定辞書

        Raises:
            ConfigError: 設定ファイルの読み込みまたは検証に失敗した場合
        """
        try:
            self._config_path = Path(config_path)

            # 環境変数読み込み
            self._load_env_variables()

            # 設定ファイル読み込み
            if not self._config_path.exists():
                raise ConfigError(f"設定ファイルが見つかりません: {config_path}")

            with open(self._config_path, 'r', encoding='utf-8') as file:
                self._config = yaml.safe_load(file)

            if not self._config:
                raise ConfigError("設定ファイルが空または無効です")

            # 環境変数置換
            self._config = self._replace_env_vars(self._config)

            # 設定検証
            self._validate_config()

            logger.info(f"設定ファイルを読み込みました: {config_path}")
            return self._config

        except yaml.YAMLError as e:
            raise ConfigError(f"YAML解析エラー: {str(e)}")
        except Exception as e:
            raise ConfigError(f"設定読み込みエラー: {str(e)}")

    def _load_env_variables(self):
        """環境変数を読み込み"""
        # .envファイルがある場合は読み込み
        env_file = self._config_path.parent / '.env' if self._config_path else Path('.env')
        if env_file.exists():
            load_dotenv(env_file)
            logger.debug(f".envファイルを読み込みました: {env_file}")

    def _replace_env_vars(self, obj: Any) -> Any:
        """
        設定値内の環境変数を置換

        ${ENV_VAR} 形式の変数を環境変数の値に置換します。
        """
        if isinstance(obj, dict):
            return {key: self._replace_env_vars(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            return self._replace_single_env_var(obj)
        else:
            return obj

    def _replace_single_env_var(self, value: str) -> str:
        """単一の文字列内の環境変数を置換"""
        if value.startswith('${') and value.endswith('}'):
            env_var_name = value[2:-1]
            env_value = os.getenv(env_var_name)
            if env_value is None:
                logger.warning(f"環境変数が設定されていません: {env_var_name}")
                return value
            return env_value
        return value

    def _validate_config(self):
        """設定値の検証"""
        if not self._config:
            raise ConfigError("設定が空です")

        # 必須セクションの確認
        required_sections = ['api', 'input', 'output']
        for section in required_sections:
            if section not in self._config:
                raise ConfigError(f"必須セクションが見つかりません: {section}")

        # API設定の検証
        api_config = self._config['api']
        if not api_config.get('key'):
            raise ConfigError("PSI APIキーが設定されていません")

        if api_config.get('key') == 'your_api_key_here':
            raise ConfigError("PSI APIキーがデフォルト値のままです。正しいAPIキーを設定してください")

        # タイムアウト値の検証
        timeout = api_config.get('timeout', 60)
        if not isinstance(timeout, int) or timeout <= 0:
            raise ConfigError("タイムアウト値は正の整数である必要があります")

        # リトライ回数の検証
        retry_count = api_config.get('retry_count', 3)
        if not isinstance(retry_count, int) or retry_count < 0:
            raise ConfigError("リトライ回数は0以上の整数である必要があります")

        # 入力設定の検証
        input_config = self._config['input']
        targets_csv = input_config.get('targets_csv')
        if not targets_csv:
            raise ConfigError("計測対象CSVファイルのパスが設定されていません")

        # CSVファイルの存在確認
        csv_path = Path(targets_csv)
        if not csv_path.is_absolute():
            csv_path = self._config_path.parent / targets_csv

        if not csv_path.exists():
            raise ConfigError(f"計測対象CSVファイルが見つかりません: {csv_path}")

        # 出力ディレクトリの作成
        self._ensure_output_directories()

        logger.info("設定検証が完了しました")

    def _ensure_output_directories(self):
        """出力ディレクトリの作成"""
        output_config = self._config['output']

        # JSONディレクトリ
        json_dir = Path(output_config.get('json_dir', './output/json'))
        if not json_dir.is_absolute():
            json_dir = self._config_path.parent / json_dir
        json_dir.mkdir(parents=True, exist_ok=True)

        # CSVファイルのディレクトリ
        csv_file = Path(output_config.get('csv_file', './output/csv/psi_metrics.csv'))
        if not csv_file.is_absolute():
            csv_file = self._config_path.parent / csv_file
        csv_file.parent.mkdir(parents=True, exist_ok=True)

        # ログファイルのディレクトリ
        log_file = Path(output_config.get('log_file', './logs/execution.log'))
        if not log_file.is_absolute():
            log_file = self._config_path.parent / log_file
        log_file.parent.mkdir(parents=True, exist_ok=True)

    def get_config(self) -> Dict[str, Any]:
        """現在の設定を取得"""
        if not self._config:
            raise ConfigError("設定が読み込まれていません")
        return self._config.copy()

    def get_api_config(self) -> Dict[str, Any]:
        """API設定を取得"""
        return self.get_config()['api']

    def get_input_config(self) -> Dict[str, Any]:
        """入力設定を取得"""
        return self.get_config()['input']

    def get_output_config(self) -> Dict[str, Any]:
        """出力設定を取得"""
        return self.get_config()['output']

    def get_execution_config(self) -> Dict[str, Any]:
        """実行設定を取得"""
        return self.get_config().get('execution', {})

    def get_logging_config(self) -> Dict[str, Any]:
        """ログ設定を取得"""
        return self.get_config().get('logging', {})
