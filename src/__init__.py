"""
PSI Lab Metrics Tool

ウェブサイトのPageSpeed Insightsラボデータを自動取得するツール
sitespeed.io連携によるWaterfall詳細データ取得も対応
"""

__version__ = "1.2.0"
__author__ = "System Admin Team"
__description__ = "PageSpeed Insights Lab Metrics Collection Tool with sitespeed.io Waterfall Support"

from .psi_client import PSIClient, PSIAPIError, PSIRateLimitError
from .metrics_extractor import MetricsExtractor, MetricsExtractionError
from .sitespeed_client import SitespeedClient, SitespeedError, SitespeedNotFoundError
from .sitespeed_extractor import SitespeedExtractor, SitespeedExtractionError
from .config_manager import ConfigManager, ConfigError
from .csv_loader import CSVLoader, CSVError
from .output_manager import OutputManager, OutputError

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
    # Common
    'ConfigManager',
    'ConfigError',
    'CSVLoader',
    'CSVError',
    'OutputManager',
    'OutputError',
]
