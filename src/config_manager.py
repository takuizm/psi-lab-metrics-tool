"""
設定管理モジュール

設定ファイルの読み込み、環境変数の処理、設定値の検証を行います。
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import find_dotenv, load_dotenv

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """設定関連のエラー"""
    pass


class ConfigManager:
    """設定ファイル管理クラス"""

    def __init__(self):
        self._config: Optional[Dict[str, Any]] = None
        self._config_path: Optional[Path] = None
        self._project_root: Path = Path.cwd()

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
            self._project_root = Path.cwd()

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

            # パスの正規化
            self._normalize_paths()

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
        # .envファイル検索（作業ディレクトリ優先）
        env_path = find_dotenv(usecwd=True)
        if not env_path and self._config_path:
            candidate = self._config_path.parent / '.env'
            if candidate.exists():
                env_path = str(candidate)

        if env_path:
            load_dotenv(env_path)
            logger.debug(f".envファイルを読み込みました: {env_path}")

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

        csv_path = Path(targets_csv)
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
        json_dir.mkdir(parents=True, exist_ok=True)

        # CSVファイルのディレクトリ
        csv_file = Path(output_config.get('csv_file', './output/csv/psi_metrics.csv'))
        csv_file.parent.mkdir(parents=True, exist_ok=True)

        # ログファイルのディレクトリ
        log_file = Path(output_config.get('log_file', './logs/execution.log'))
        log_file.parent.mkdir(parents=True, exist_ok=True)

    def _normalize_paths(self):
        """設定内のパスをプロジェクトルート基準で正規化"""
        if not self._config:
            return

        # 入力ファイル
        input_config = self._config.get('input', {})
        if 'targets_csv' in input_config:
            resolved_csv = self._resolve_existing_path(input_config['targets_csv'])
            input_config['targets_csv'] = str(resolved_csv)

        # 出力関連
        output_config = self._config.get('output', {})
        for key in ['json_dir', 'csv_file', 'log_file']:
            if key in output_config:
                output_config[key] = str(self._resolve_output_path(output_config[key]))

    def _resolve_existing_path(self, path_value: Any) -> Path:
        """既存ファイルのパスを解決"""
        candidate = Path(str(path_value))
        if candidate.is_absolute() and candidate.exists():
            return candidate

        # プロジェクトルート優先
        root_candidate = self._project_root / candidate
        if root_candidate.exists():
            return root_candidate

        # 設定ファイルディレクトリも許容（後方互換）
        if self._config_path:
            config_candidate = self._config_path.parent / candidate
            if config_candidate.exists():
                return config_candidate

        # 存在しない場合はプロジェクトルートに配置予定として返却
        return (self._project_root / candidate).resolve(strict=False)

    def _resolve_output_path(self, path_value: Any) -> Path:
        """出力系パスを解決（存在しなくても良い）"""
        candidate = Path(str(path_value))
        if candidate.is_absolute():
            return candidate

        # プロジェクトルート基準で絶対パス化
        resolved = (self._project_root / candidate).resolve(strict=False)

        # 後方互換: 既存ファイルが config 側にある場合はそちらを使用
        if not resolved.exists() and self._config_path:
            legacy_candidate = (self._config_path.parent / candidate).resolve(strict=False)
            if legacy_candidate.exists():
                logger.warning(
                    f"出力パス {candidate} はプロジェクトルートに存在しません。"
                    f"既存ファイルが見つかったため {legacy_candidate} を使用します"
                )
                return legacy_candidate

        return resolved

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
