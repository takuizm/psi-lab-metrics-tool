import os
from pathlib import Path

import pytest

from src.io.config_manager import ConfigManager, ConfigError


def _write_config(path: Path):
    path.write_text(
        """
api:
  key: "${PSI_API_KEY}"
  timeout: 30
  retry_count: 1
  base_delay: 1
  max_delay: 60
input:
  targets_csv: "./targets.csv"
  csv_encoding: "utf-8-sig"
execution:
  parallel: false
output:
  json_dir: "./output/json"
  csv_file: "./output/csv/psi_metrics.csv"
  log_file: "./logs/execution.log"
logging:
  level: "INFO"
  format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        """.strip()
        + "\n",
        encoding="utf-8",
    )


def test_load_config_prefers_project_root(monkeypatch, tmp_path):
    project_root = tmp_path
    config_dir = project_root / "config"
    config_dir.mkdir()

    targets_root = project_root / "targets.csv"
    targets_root.write_text("url,name\nhttps://example.com,Example\n", encoding="utf-8")

    config_path = config_dir / "config.yaml"
    _write_config(config_path)

    env_path = project_root / ".env"
    env_path.write_text("PSI_API_KEY=dummy-key\n", encoding="utf-8")

    # 環境変数をクリア
    monkeypatch.delenv("PSI_API_KEY", raising=False)

    # プロジェクトルートをカレントディレクトリとして読み込み
    monkeypatch.chdir(project_root)
    manager = ConfigManager()
    config = manager.load_config(str(config_path))

    resolved_targets = Path(config["input"]["targets_csv"])
    assert resolved_targets == targets_root.resolve()

    json_dir = Path(config["output"]["json_dir"])
    assert json_dir == (project_root / "output" / "json").resolve()

    log_file = Path(config["output"]["log_file"])
    assert log_file == (project_root / "logs" / "execution.log").resolve()

    # APIキーが .env から展開されているか
    assert config["api"]["key"] == "dummy-key"


def test_load_config_missing_targets_raises(monkeypatch, tmp_path):
    project_root = tmp_path
    config_dir = project_root / "config"
    config_dir.mkdir()
    config_path = config_dir / "config.yaml"
    _write_config(config_path)

    env_path = project_root / ".env"
    env_path.write_text("PSI_API_KEY=dummy-key\n", encoding="utf-8")

    monkeypatch.chdir(project_root)
    manager = ConfigManager()
    with pytest.raises(ConfigError):
        manager.load_config(str(config_path))
