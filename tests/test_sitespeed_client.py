"""
sitespeed_client.py のユニットテスト
"""

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.clients.sitespeed_client import (
    SitespeedClient,
    SitespeedError,
    SitespeedNotFoundError,
    check_sitespeed_installation,
)


class TestSitespeedClientInit:
    """SitespeedClient 初期化のテスト"""

    def test_init_local_not_found(self, monkeypatch):
        """sitespeed.ioがインストールされていない場合にエラーになること"""
        monkeypatch.setattr(shutil, "which", lambda x: None)

        with pytest.raises(SitespeedNotFoundError) as exc_info:
            SitespeedClient()

        assert "sitespeed.ioがインストールされていません" in str(exc_info.value)

    def test_init_docker_not_found(self, monkeypatch):
        """Dockerモードでdockerがない場合にエラーになること"""
        monkeypatch.setattr(shutil, "which", lambda x: None)

        with pytest.raises(SitespeedNotFoundError) as exc_info:
            SitespeedClient(docker=True)

        assert "Dockerがインストールされていません" in str(exc_info.value)

    def test_init_local_success(self, monkeypatch, tmp_path):
        """sitespeed.ioがインストールされている場合に正常初期化されること"""
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/local/bin/sitespeed.io")

        client = SitespeedClient(output_base_dir=str(tmp_path / "output"))

        assert client.browser == "chrome"
        assert client.iterations == 1
        assert client.mobile is False
        assert client.docker is False

    def test_init_docker_success(self, monkeypatch, tmp_path):
        """Dockerモードで正常初期化されること"""
        monkeypatch.setattr(
            shutil, "which", lambda x: "/usr/local/bin/docker" if x == "docker" else None
        )

        client = SitespeedClient(docker=True, output_base_dir=str(tmp_path / "output"))

        assert client.docker is True

    def test_init_custom_options(self, monkeypatch, tmp_path):
        """カスタムオプションが正しく設定されること"""
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/local/bin/sitespeed.io")

        client = SitespeedClient(
            output_base_dir=str(tmp_path / "output"),
            browser="firefox",
            iterations=3,
            connectivity="4g",
            mobile=True,
            timeout=600,
        )

        assert client.browser == "firefox"
        assert client.iterations == 3
        assert client.connectivity == "4g"
        assert client.mobile is True
        assert client.timeout == 600


class TestSitespeedClientBuildCommand:
    """コマンド構築のテスト"""

    @pytest.fixture
    def client(self, monkeypatch, tmp_path):
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/local/bin/sitespeed.io")
        return SitespeedClient(output_base_dir=str(tmp_path / "output"))

    def test_build_command_basic(self, client, tmp_path):
        """基本コマンドが正しく構築されること"""
        output_dir = tmp_path / "output" / "test"
        cmd = client._build_command("https://example.com/", output_dir)

        assert cmd[0] == "sitespeed.io"
        assert "https://example.com/" in cmd
        assert "--outputFolder" in cmd
        assert "-b" in cmd
        assert "chrome" in cmd
        assert "-n" in cmd
        assert "1" in cmd
        assert "--visualMetrics" in cmd

    def test_build_command_mobile(self, monkeypatch, tmp_path):
        """モバイルオプションが正しく追加されること"""
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/local/bin/sitespeed.io")
        client = SitespeedClient(
            output_base_dir=str(tmp_path / "output"),
            mobile=True,
        )
        output_dir = tmp_path / "output" / "test"
        cmd = client._build_command("https://example.com/", output_dir)

        assert "--mobile" in cmd

    def test_build_command_connectivity(self, monkeypatch, tmp_path):
        """接続プロファイルが正しく追加されること"""
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/local/bin/sitespeed.io")
        client = SitespeedClient(
            output_base_dir=str(tmp_path / "output"),
            connectivity="4g",
        )
        output_dir = tmp_path / "output" / "test"
        cmd = client._build_command("https://example.com/", output_dir)

        assert "-c" in cmd
        assert "4g" in cmd

    def test_build_command_docker(self, monkeypatch, tmp_path):
        """Dockerコマンドが正しく構築されること"""
        monkeypatch.setattr(
            shutil, "which", lambda x: "/usr/local/bin/docker" if x == "docker" else None
        )
        client = SitespeedClient(
            docker=True,
            output_base_dir=str(tmp_path / "output"),
        )
        output_dir = tmp_path / "output" / "test"
        cmd = client._build_command("https://example.com/", output_dir)

        assert cmd[0] == "docker"
        assert "run" in cmd
        assert "--rm" in cmd
        assert "-v" in cmd
        assert "sitespeedio/sitespeed.io:latest" in cmd

    def test_build_command_extra_options(self, client, tmp_path):
        """追加オプションが正しく追加されること"""
        output_dir = tmp_path / "output" / "test"
        extra_options = {
            "headless": True,
            "cpu.slowdown": 4,
        }
        cmd = client._build_command("https://example.com/", output_dir, extra_options)

        assert "--headless" in cmd
        assert "--cpu.slowdown" in cmd
        assert "4" in cmd


class TestSitespeedClientRunTest:
    """テスト実行のテスト"""

    @pytest.fixture
    def client(self, monkeypatch, tmp_path):
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/local/bin/sitespeed.io")
        return SitespeedClient(output_base_dir=str(tmp_path / "output"))

    @pytest.fixture
    def mock_har_file(self, tmp_path):
        """モックHARファイルを作成"""
        fixtures_dir = Path(__file__).parent / "fixtures"
        har_content = (fixtures_dir / "sample_har.json").read_text(encoding="utf-8")

        output_dir = tmp_path / "output" / "test_site_20241217_100000"
        output_dir.mkdir(parents=True)
        har_path = output_dir / "test.har"
        har_path.write_text(har_content, encoding="utf-8")

        return output_dir, har_path

    def test_run_test_success(self, client, monkeypatch, mock_har_file):
        """テストが正常に実行されること"""
        output_dir, har_path = mock_har_file

        # subprocess.run をモック
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            # _build_command で作成される出力ディレクトリを上書き
            with patch.object(
                client, "_parse_results", return_value={
                    "url": "https://example.com/",
                    "site_name": "test_site",
                    "output_dir": str(output_dir),
                    "metrics": {"ttfb_ms": 50},
                    "har_files": [str(har_path)],
                }
            ):
                result = client.run_test("https://example.com/", site_name="test_site")

        assert result["url"] == "https://example.com/"
        assert result["site_name"] == "test_site"
        assert client.stats["successful_runs"] == 1

    def test_run_test_failure(self, client, monkeypatch):
        """テスト失敗時にエラーが発生すること"""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Chrome failed to start"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(SitespeedError) as exc_info:
                client.run_test("https://example.com/")

        assert "sitespeed.io実行失敗" in str(exc_info.value)
        assert client.stats["failed_runs"] == 1

    def test_run_test_timeout(self, client, monkeypatch):
        """タイムアウト時にエラーが発生すること"""
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 300)):
            with pytest.raises(SitespeedError) as exc_info:
                client.run_test("https://example.com/")

        assert "タイムアウト" in str(exc_info.value)
        assert client.stats["failed_runs"] == 1


class TestSitespeedClientStats:
    """統計情報のテスト"""

    @pytest.fixture
    def client(self, monkeypatch, tmp_path):
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/local/bin/sitespeed.io")
        return SitespeedClient(output_base_dir=str(tmp_path / "output"))

    def test_get_stats_initial(self, client):
        """初期統計情報が正しいこと"""
        stats = client.get_stats()

        assert stats["total_runs"] == 0
        assert stats["successful_runs"] == 0
        assert stats["failed_runs"] == 0
        assert stats["success_rate"] == 0.0

    def test_reset_stats(self, client):
        """統計情報がリセットできること"""
        client.stats["total_runs"] = 5
        client.stats["successful_runs"] = 4
        client.stats["failed_runs"] = 1

        client.reset_stats()

        stats = client.get_stats()
        assert stats["total_runs"] == 0
        assert stats["successful_runs"] == 0
        assert stats["failed_runs"] == 0


class TestSitespeedClientHelpers:
    """ヘルパーメソッドのテスト"""

    @pytest.fixture
    def client(self, monkeypatch, tmp_path):
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/local/bin/sitespeed.io")
        return SitespeedClient(output_base_dir=str(tmp_path / "output"))

    def test_sanitize_name(self, client):
        """ファイル名サニタイズが正しく動作すること"""
        assert client._sanitize_name("example.com") == "example_com"
        assert client._sanitize_name("test site") == "test_site"
        assert client._sanitize_name("my-site_123") == "my-site_123"
        # Python の isalnum() は日本語文字も許可する
        assert client._sanitize_name("日本語サイト") == "日本語サイト"
        # 特殊文字はアンダースコアに変換
        assert client._sanitize_name("test@site#123") == "test_site_123"

    def test_extract_domain(self, client):
        """ドメイン抽出が正しく動作すること"""
        assert client._extract_domain("https://example.com/path") == "example.com"
        assert client._extract_domain("https://www.example.com:8080/") == "www.example.com_8080"
        assert client._extract_domain("invalid") == ""


class TestCheckSitespeedInstallation:
    """インストール状況確認のテスト"""

    def test_both_installed(self, monkeypatch):
        """両方インストールされている場合"""
        monkeypatch.setattr(
            shutil, "which",
            lambda x: "/path/to/" + x if x in ["sitespeed.io", "docker"] else None
        )

        mock_result = MagicMock()
        mock_result.stdout = "30.0.0"

        with patch("subprocess.run", return_value=mock_result):
            result = check_sitespeed_installation()

        assert result["sitespeed_local"] is True
        assert result["docker"] is True
        assert result["recommended_method"] == "local"

    def test_docker_only(self, monkeypatch):
        """Dockerのみインストールされている場合"""
        monkeypatch.setattr(
            shutil, "which",
            lambda x: "/path/to/docker" if x == "docker" else None
        )

        mock_result = MagicMock()
        mock_result.stdout = "Docker version 24.0.0"

        with patch("subprocess.run", return_value=mock_result):
            result = check_sitespeed_installation()

        assert result["sitespeed_local"] is False
        assert result["docker"] is True
        assert result["recommended_method"] == "docker"

    def test_nothing_installed(self, monkeypatch):
        """何もインストールされていない場合"""
        monkeypatch.setattr(shutil, "which", lambda x: None)

        result = check_sitespeed_installation()

        assert result["sitespeed_local"] is False
        assert result["docker"] is False
        assert result["recommended_method"] is None
