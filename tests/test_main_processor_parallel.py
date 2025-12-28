from typing import Dict, Any, List

import pytest

from src.cli import psi_main as main_module


class StubCSVLoader:
    def __init__(self, csv_path: str, encoding: str = "utf-8-sig"):
        self._targets = [
            {"url": "https://example.com", "name": "Example", "enabled": True},
            {"url": "https://example.org", "name": "Example Org", "enabled": True},
        ]

    def validate_csv_format(self) -> Dict[str, Any]:
        return {"valid": True, "errors": [], "warnings": []}

    def load_targets(self, force_reload: bool = False) -> List[Dict[str, Any]]:
        return self._targets


class StubPSIClient:
    def __init__(self, api_key: str, timeout: int, retry_count: int, base_delay: float, max_delay: float):
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "rate_limit_hits": 0,
            "retries_performed": 0,
        }

    def get_page_metrics(self, url: str, strategy: str) -> Dict[str, Any]:
        self.stats["total_requests"] += 1
        self.stats["successful_requests"] += 1
        return {"dummy": True}

    def get_stats(self, include_success_rate: bool = True) -> Dict[str, Any]:
        stats = self.stats.copy()
        if include_success_rate:
            stats["success_rate"] = (
                stats["successful_requests"] / stats["total_requests"]
                if stats["total_requests"]
                else 0.0
            )
        return stats

    def reset_stats(self):
        for key in self.stats:
            self.stats[key] = 0

    def merge_external_stats(self, external_stats: Dict[str, Any]):
        for key, value in external_stats.items():
            if key in self.stats:
                self.stats[key] += value


class StubMetricsExtractor:
    def __init__(self):
        self._total = 0

    def extract_all_metrics(self, psi_response: Dict[str, Any], target_info: Dict[str, Any]) -> Dict[str, Any]:
        self._total += 1
        return {
            **target_info,
            "timestamp": "2025-01-01T00:00:00Z",
            "onload_ms": 1000.0,
            "ttfb_ms": 100.0,
            "lcp_ms": 1200.0,
            "cls": 0.05,
            "speed_index_ms": 1500.0,
        }

    def create_summary_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "site_name": metrics["name"],
            "name": metrics["name"],
            "url": metrics["url"],
            "strategy": metrics["strategy"],
            "timestamp": metrics["timestamp"],
            "onload_ms": metrics["onload_ms"],
            "ttfb_ms": metrics["ttfb_ms"],
            "lcp_ms": metrics["lcp_ms"],
            "cls": metrics["cls"],
            "speed_index_ms": metrics["speed_index_ms"],
        }

    def get_stats(self) -> Dict[str, Any]:
        total = self._total
        success_rate = 1.0 if total else 0.0
        return {
            "total_extractions": total,
            "successful_extractions": total,
            "failed_extractions": 0,
            "missing_metrics_count": 0,
            "success_rate": success_rate,
        }

    def reset_stats(self):
        self._total = 0


class StubOutputManager:
    def __init__(self, json_dir: str, csv_file: str, timestamp_format: str):
        self.saved_json: List[str] = []
        self.saved_csv: List[Dict[str, Any]] = []
        self.summary_saved: List[Dict[str, Any]] = []
        self.stats = {
            "json_files_created": 0,
            "csv_rows_written": 0,
            "total_data_size_bytes": 0,
            "cleanup_operations": 0,
        }

    def save_json(self, data: Dict[str, Any], site_name: str, strategy: str) -> str:
        filename = f"{site_name}_{strategy}.json"
        self.saved_json.append(filename)
        self.stats["json_files_created"] += 1
        return filename

    def append_csv(self, metrics: Dict[str, Any]) -> None:
        self.saved_csv.append(metrics)
        self.stats["csv_rows_written"] += 1

    def save_summary_csv(self, all_metrics: List[Dict[str, Any]], filename: str = None) -> str:
        self.summary_saved = list(all_metrics)
        return filename or "psi_summary_stub.csv"

    def get_stats(self) -> Dict[str, Any]:
        return self.stats.copy()

    def reset_stats(self):
        for key in self.stats:
            self.stats[key] = 0


@pytest.fixture(autouse=True)
def patch_dependencies(monkeypatch):
    monkeypatch.setattr(main_module, "CSVLoader", StubCSVLoader)
    monkeypatch.setattr(main_module, "PSIClient", StubPSIClient)
    monkeypatch.setattr(main_module, "MetricsExtractor", StubMetricsExtractor)
    monkeypatch.setattr(main_module, "OutputManager", StubOutputManager)


def test_parallel_processing_merges_results(tmp_path, monkeypatch):
    config = {
        "api": {
            "key": "dummy",
            "timeout": 30,
            "retry_count": 1,
            "base_delay": 1,
            "max_delay": 60,
        },
        "input": {
            "targets_csv": str(tmp_path / "targets.csv"),
            "csv_encoding": "utf-8-sig",
        },
        "execution": {
            "parallel": True,
            "max_workers": 2,
        },
        "output": {
            "json_dir": str(tmp_path / "output" / "json"),
            "csv_file": str(tmp_path / "output" / "csv" / "psi_metrics.csv"),
            "log_file": str(tmp_path / "logs" / "execution.log"),
            "timestamp_format": "%Y%m%d_%H%M%S",
        },
        "logging": {
            "level": "WARNING",
            "format": "%(message)s",
        },
    }

    (tmp_path / "output" / "json").mkdir(parents=True)
    (tmp_path / "output" / "csv").mkdir(parents=True)
    (tmp_path / "logs").mkdir(parents=True)

    processor = main_module.MainProcessor(config)
    result = processor.process_all_targets(["mobile", "desktop"], dry_run=False)

    assert result["success"] is True
    # 並列実行で 2ターゲット x 2戦略 = 4 レコード
    assert len(processor.output_manager.saved_json) == 4
    assert len(processor.output_manager.saved_csv) == 4

    psi_stats = processor.psi_client.get_stats()
    assert psi_stats["total_requests"] == 4
    assert psi_stats["successful_requests"] == 4


def test_processing_stats_counts_failed_requests(tmp_path, monkeypatch):
    class FlakyStubPSIClient(StubPSIClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._call_count = 0

        def get_page_metrics(self, url: str, strategy: str) -> Dict[str, Any]:
            self._call_count += 1
            self.stats["total_requests"] += 1
            if self._call_count == 1:
                self.stats["failed_requests"] += 1
                raise RuntimeError("PSI failure")
            self.stats["successful_requests"] += 1
            return {"dummy": True}

    monkeypatch.setattr(main_module, "PSIClient", FlakyStubPSIClient)

    config = {
        "api": {
            "key": "dummy",
            "timeout": 30,
            "retry_count": 1,
            "base_delay": 1,
            "max_delay": 60,
        },
        "input": {
            "targets_csv": str(tmp_path / "targets.csv"),
            "csv_encoding": "utf-8-sig",
        },
        "execution": {
            "parallel": False,
        },
        "output": {
            "json_dir": str(tmp_path / "output" / "json"),
            "csv_file": str(tmp_path / "output" / "csv" / "psi_metrics.csv"),
            "log_file": str(tmp_path / "logs" / "execution.log"),
            "timestamp_format": "%Y%m%d_%H%M%S",
        },
        "logging": {
            "level": "WARNING",
            "format": "%(message)s",
        },
    }

    (tmp_path / "output" / "json").mkdir(parents=True)
    (tmp_path / "output" / "csv").mkdir(parents=True)
    (tmp_path / "logs").mkdir(parents=True)

    processor = main_module.MainProcessor(config)
    result = processor.process_all_targets(["mobile", "desktop"], dry_run=False)

    assert result["success"] is False
    assert processor.processing_stats["total_requests"] == 4
    assert result["stats"]["total_requests"] == 4
