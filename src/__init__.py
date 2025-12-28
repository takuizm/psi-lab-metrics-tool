"""
PSI Lab Metrics Tool

ウェブサイトのPageSpeed Insightsラボデータを自動取得するツール
sitespeed.io連携によるWaterfall詳細データ取得も対応
"""

__version__ = "1.3.0"
__author__ = "System Admin Team"
__description__ = "PageSpeed Insights Lab Metrics Collection Tool with sitespeed.io Waterfall Support"

# クライアント
from src.clients.psi_client import PSIClient, PSIAPIError, PSIRateLimitError
from src.clients.sitespeed_client import SitespeedClient, SitespeedError, SitespeedNotFoundError

# 抽出器
from src.extractors.metrics_extractor import MetricsExtractor, MetricsExtractionError
from src.extractors.sitespeed_extractor import SitespeedExtractor, SitespeedExtractionError
from src.extractors.waterfall_extractor import WaterfallExtractor, WaterfallExtractionError

# 入出力
from src.io.config_manager import ConfigManager, ConfigError
from src.io.csv_loader import CSVLoader, CSVError
from src.io.output_manager import OutputManager, OutputError

__all__ = [
    # PSI
    'PSIClient',
    'PSIAPIError',
    'PSIRateLimitError',
    'MetricsExtractor',
    'MetricsExtractionError',
    # sitespeed.io
    'SitespeedClient',
    'SitespeedError',
    'SitespeedNotFoundError',
    'SitespeedExtractor',
    'SitespeedExtractionError',
    # Waterfall
    'WaterfallExtractor',
    'WaterfallExtractionError',
    # Common
    'ConfigManager',
    'ConfigError',
    'CSVLoader',
    'CSVError',
    'OutputManager',
    'OutputError',
]
