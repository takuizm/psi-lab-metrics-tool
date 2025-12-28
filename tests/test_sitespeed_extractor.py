"""
sitespeed_extractor.py のユニットテスト
"""

import json
from pathlib import Path

import pytest

from src.extractors.sitespeed_extractor import SitespeedExtractor, SitespeedExtractionError
from src.utils.url_utils import determine_resource_type


@pytest.fixture
def sample_har_path(tmp_path):
    """サンプルHARファイルを一時ディレクトリにコピー"""
    fixtures_dir = Path(__file__).parent / "fixtures"
    har_content = (fixtures_dir / "sample_har.json").read_text(encoding="utf-8")
    har_path = tmp_path / "test.har"
    har_path.write_text(har_content, encoding="utf-8")
    return har_path


@pytest.fixture
def extractor():
    """SitespeedExtractor インスタンス"""
    return SitespeedExtractor()


class TestSitespeedExtractor:
    """SitespeedExtractor のテストクラス"""

    def test_extract_waterfall_from_har_success(self, extractor, sample_har_path):
        """HARファイルから正常にWaterfallデータを抽出できること"""
        result = extractor.extract_waterfall_from_har(str(sample_har_path))

        assert result is not None
        assert "meta" in result
        assert "page_metrics" in result
        assert "entries" in result
        assert "summary" in result

    def test_extract_waterfall_meta_info(self, extractor, sample_har_path):
        """メタ情報が正しく抽出されること"""
        target_info = {
            "url": "https://example.com/",
            "name": "Example",
            "mobile": False,
            "browser": "chrome",
        }
        result = extractor.extract_waterfall_from_har(
            str(sample_har_path), target_info=target_info
        )

        meta = result["meta"]
        assert meta["tool"] == "sitespeed.io"
        assert meta["url"] == "https://example.com/"
        assert meta["site_name"] == "Example"
        assert meta["strategy"] == "desktop"
        assert meta["browser"] == "chrome"

    def test_extract_waterfall_page_metrics(self, extractor, sample_har_path):
        """ページメトリクスが正しく計算されること"""
        result = extractor.extract_waterfall_from_har(str(sample_har_path))

        metrics = result["page_metrics"]
        assert metrics["total_requests"] == 4
        assert metrics["dom_content_loaded_ms"] == 500
        assert metrics["load_time_ms"] == 1500
        assert metrics["ttfb_ms"] == 50  # 最初のリクエストの wait
        assert metrics["dns_ms"] == 25
        assert metrics["connect_ms"] == 35
        assert metrics["ssl_ms"] == 45

    def test_extract_waterfall_entries(self, extractor, sample_har_path):
        """エントリが正しく抽出されること"""
        result = extractor.extract_waterfall_from_har(str(sample_har_path))

        entries = result["entries"]
        assert len(entries) == 4

        # 最初のエントリ（メインドキュメント）
        first_entry = entries[0]
        assert first_entry["url"] == "https://example.com/"
        assert first_entry["method"] == "GET"
        assert first_entry["status"] == 200
        assert first_entry["resource_type"] == "document"
        assert first_entry["is_secure"] is True
        assert first_entry["connection_reused"] is False

        # タイミング
        timings = first_entry["timings"]
        assert timings["dns"] == 25
        assert timings["connect"] == 35
        assert timings["ssl"] == 45
        assert timings["wait"] == 50

    def test_extract_waterfall_connection_reused(self, extractor, sample_har_path):
        """接続再利用が正しく検出されること"""
        result = extractor.extract_waterfall_from_har(str(sample_har_path))

        entries = result["entries"]

        # 最初のエントリは新規接続
        assert entries[0]["connection_reused"] is False

        # 2番目以降のエントリは接続再利用（DNS/connect が -1）
        assert entries[1]["connection_reused"] is True
        assert entries[2]["connection_reused"] is True
        assert entries[3]["connection_reused"] is True

    def test_extract_waterfall_resource_types(self, extractor, sample_har_path):
        """リソースタイプが正しく判定されること"""
        result = extractor.extract_waterfall_from_har(str(sample_har_path))

        entries = result["entries"]

        resource_types = [e["resource_type"] for e in entries]
        assert "document" in resource_types
        assert "stylesheet" in resource_types
        assert "script" in resource_types
        assert "image" in resource_types

    def test_extract_waterfall_summary(self, extractor, sample_har_path):
        """サマリーが正しく計算されること"""
        result = extractor.extract_waterfall_from_har(str(sample_har_path))

        summary = result["summary"]
        assert summary["total_entries"] == 4

        # リソースタイプ別集計
        by_type = summary["by_resource_type"]
        assert by_type["counts"]["document"] == 1
        assert by_type["counts"]["stylesheet"] == 1
        assert by_type["counts"]["script"] == 1
        assert by_type["counts"]["image"] == 1

        # 接続統計
        conn_stats = summary["connection_stats"]
        assert conn_stats["new"] == 1
        assert conn_stats["reused"] == 3

    def test_extract_waterfall_file_not_found(self, extractor):
        """存在しないファイルでエラーになること"""
        with pytest.raises(SitespeedExtractionError) as exc_info:
            extractor.extract_waterfall_from_har("/nonexistent/path/test.har")

        assert "HARファイルが見つかりません" in str(exc_info.value)

    def test_extract_waterfall_empty_entries(self, extractor, tmp_path):
        """エントリが空のHARファイルでエラーになること"""
        empty_har = {
            "log": {
                "version": "1.2",
                "entries": []
            }
        }
        har_path = tmp_path / "empty.har"
        har_path.write_text(json.dumps(empty_har), encoding="utf-8")

        with pytest.raises(SitespeedExtractionError) as exc_info:
            extractor.extract_waterfall_from_har(str(har_path))

        assert "エントリがありません" in str(exc_info.value)

    def test_extractor_stats(self, extractor, sample_har_path):
        """統計情報が正しく更新されること"""
        # 初期状態
        stats = extractor.get_stats()
        assert stats["total_extractions"] == 0
        assert stats["successful_extractions"] == 0

        # 抽出実行
        extractor.extract_waterfall_from_har(str(sample_har_path))

        # 統計確認
        stats = extractor.get_stats()
        assert stats["total_extractions"] == 1
        assert stats["successful_extractions"] == 1
        assert stats["total_requests_processed"] == 4
        assert stats["success_rate"] == 1.0

    def test_extractor_stats_reset(self, extractor, sample_har_path):
        """統計情報がリセットできること"""
        extractor.extract_waterfall_from_har(str(sample_har_path))
        extractor.reset_stats()

        stats = extractor.get_stats()
        assert stats["total_extractions"] == 0
        assert stats["successful_extractions"] == 0
        assert stats["total_requests_processed"] == 0

    def test_mobile_strategy(self, extractor, sample_har_path):
        """モバイル戦略が正しく設定されること"""
        target_info = {"mobile": True}
        result = extractor.extract_waterfall_from_har(
            str(sample_har_path), target_info=target_info
        )

        assert result["meta"]["strategy"] == "mobile"


class TestResourceTypeDetection:
    """リソースタイプ判定のテスト（共通ユーティリティ関数）"""

    def test_determine_resource_type_by_content_type(self):
        """Content-Typeによるリソースタイプ判定"""
        assert determine_resource_type("", "text/html") == "document"
        assert determine_resource_type("", "text/css") == "stylesheet"
        assert determine_resource_type("", "application/javascript") == "script"
        assert determine_resource_type("", "image/png") == "image"
        assert determine_resource_type("", "font/woff2") == "font"
        assert determine_resource_type("", "application/json") == "fetch"

    def test_determine_resource_type_by_url_extension(self):
        """URL拡張子によるリソースタイプ判定"""
        assert determine_resource_type("https://example.com/style.css", "") == "stylesheet"
        assert determine_resource_type("https://example.com/app.js", "") == "script"
        assert determine_resource_type("https://example.com/logo.png", "") == "image"
        assert determine_resource_type("https://example.com/font.woff2", "") == "font"

    def test_determine_resource_type_fallback(self):
        """判定不能な場合はotherになること"""
        assert determine_resource_type("https://example.com/unknown", "") == "other"
