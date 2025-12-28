"""
セキュリティバリデーションのユニットテスト

コマンドインジェクション/SSRF対策のテスト。
"""

import pytest

from src.clients.sitespeed_client import (
    validate_url,
    validate_option_key,
    validate_option_value,
    URLValidationError,
    OptionValidationError,
)


class TestURLValidation:
    """URLバリデーションのテスト"""

    def test_valid_https_url(self):
        """有効なHTTPS URLが通ること"""
        url = "https://example.com/path?query=value"
        assert validate_url(url) == url

    def test_valid_http_url(self):
        """有効なHTTP URLが通ること"""
        url = "http://example.com"
        assert validate_url(url) == url

    def test_valid_url_with_port(self):
        """ポート番号付きURLが通ること"""
        url = "https://example.com:8080/path"
        assert validate_url(url) == url

    def test_invalid_scheme_file(self):
        """fileスキームが拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("file:///etc/passwd")
        assert "無効なスキーム" in str(exc_info.value)

    def test_invalid_scheme_javascript(self):
        """javascriptスキームが拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("javascript:alert(1)")
        assert "無効なスキーム" in str(exc_info.value)

    def test_empty_url(self):
        """空URLが拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("")
        assert "空" in str(exc_info.value)

    def test_none_url(self):
        """None URLが拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url(None)
        assert "無効" in str(exc_info.value)

    def test_missing_host(self):
        """ホストなしURLが拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("https:///path")
        assert "ホスト名" in str(exc_info.value)

    # コマンドインジェクション対策テスト
    def test_command_injection_semicolon(self):
        """セミコロンを含むURLが拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("https://example.com; rm -rf /")
        assert "危険な文字" in str(exc_info.value)

    def test_command_injection_pipe(self):
        """パイプを含むURLが拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("https://example.com | cat /etc/passwd")
        assert "危険な文字" in str(exc_info.value)

    def test_command_injection_ampersand(self):
        """&を含むURLが拒否されること（クエリパラメータ以外）"""
        # 注: 通常のクエリパラメータ&はURLエンコードされるべき
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("https://example.com && echo hacked")
        assert "危険な文字" in str(exc_info.value)

    def test_command_injection_backtick(self):
        """バッククォートを含むURLが拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("https://example.com/`whoami`")
        assert "危険な文字" in str(exc_info.value)

    def test_command_injection_dollar(self):
        """$を含むURLが拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("https://example.com/$(whoami)")
        assert "危険な文字" in str(exc_info.value)

    def test_command_injection_newline(self):
        """改行を含むURLが拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("https://example.com\n; rm -rf /")
        assert "危険な文字" in str(exc_info.value)

    # SSRF対策テスト
    def test_ssrf_localhost(self):
        """localhostが拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("https://localhost/admin")
        assert "ローカルホスト" in str(exc_info.value)

    def test_ssrf_127_0_0_1(self):
        """127.0.0.1が拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("https://127.0.0.1/admin")
        assert "ローカルホスト" in str(exc_info.value)

    def test_ssrf_0_0_0_0(self):
        """0.0.0.0が拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("https://0.0.0.0/admin")
        assert "ローカルホスト" in str(exc_info.value)

    def test_ssrf_private_ip_10(self):
        """10.x.x.xプライベートIPが拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("https://10.0.0.1/internal")
        assert "プライベートIP" in str(exc_info.value)

    def test_ssrf_private_ip_172(self):
        """172.16.x.xプライベートIPが拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("https://172.16.0.1/internal")
        assert "プライベートIP" in str(exc_info.value)

    def test_ssrf_private_ip_192(self):
        """192.168.x.xプライベートIPが拒否されること"""
        with pytest.raises(URLValidationError) as exc_info:
            validate_url("https://192.168.1.1/admin")
        assert "プライベートIP" in str(exc_info.value)


class TestOptionKeyValidation:
    """オプションキーバリデーションのテスト"""

    def test_valid_simple_key(self):
        """シンプルなキーが通ること"""
        assert validate_option_key("mobile") == "mobile"

    def test_valid_key_with_hyphen(self):
        """ハイフン付きキーが通ること"""
        assert validate_option_key("visual-metrics") == "visual-metrics"

    def test_valid_key_with_dot(self):
        """ドット付きキーが通ること"""
        assert validate_option_key("screenshot.type") == "screenshot.type"

    def test_valid_key_with_underscore(self):
        """アンダースコア付きキーが通ること"""
        assert validate_option_key("max_retries") == "max_retries"

    def test_valid_key_with_number(self):
        """数字を含むキーが通ること"""
        assert validate_option_key("option123") == "option123"

    def test_invalid_key_starts_with_number(self):
        """数字で始まるキーが拒否されること"""
        with pytest.raises(OptionValidationError) as exc_info:
            validate_option_key("123option")
        assert "無効なオプションキー" in str(exc_info.value)

    def test_invalid_key_with_semicolon(self):
        """セミコロンを含むキーが拒否されること"""
        with pytest.raises(OptionValidationError) as exc_info:
            validate_option_key("option;rm")
        assert "無効なオプションキー" in str(exc_info.value)

    def test_invalid_key_with_space(self):
        """スペースを含むキーが拒否されること"""
        with pytest.raises(OptionValidationError) as exc_info:
            validate_option_key("option name")
        assert "無効なオプションキー" in str(exc_info.value)

    def test_empty_key(self):
        """空キーが拒否されること"""
        with pytest.raises(OptionValidationError) as exc_info:
            validate_option_key("")
        assert "空" in str(exc_info.value)


class TestOptionValueValidation:
    """オプション値バリデーションのテスト"""

    def test_valid_simple_value(self):
        """シンプルな値が通ること"""
        assert validate_option_value("chrome") == "chrome"

    def test_valid_numeric_value(self):
        """数値が通ること"""
        assert validate_option_value(123) == "123"

    def test_valid_path_value(self):
        """パス値が通ること"""
        assert validate_option_value("/path/to/file") == "/path/to/file"

    def test_invalid_value_with_semicolon(self):
        """セミコロンを含む値が拒否されること"""
        with pytest.raises(OptionValidationError) as exc_info:
            validate_option_value("value; rm -rf /")
        assert "危険な文字" in str(exc_info.value)

    def test_invalid_value_with_pipe(self):
        """パイプを含む値が拒否されること"""
        with pytest.raises(OptionValidationError) as exc_info:
            validate_option_value("value | cat /etc/passwd")
        assert "危険な文字" in str(exc_info.value)

    def test_invalid_value_with_backtick(self):
        """バッククォートを含む値が拒否されること"""
        with pytest.raises(OptionValidationError) as exc_info:
            validate_option_value("`whoami`")
        assert "危険な文字" in str(exc_info.value)

    def test_invalid_value_with_dollar(self):
        """$を含む値が拒否されること"""
        with pytest.raises(OptionValidationError) as exc_info:
            validate_option_value("$(cat /etc/passwd)")
        assert "危険な文字" in str(exc_info.value)
