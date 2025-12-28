"""
URL関連ユーティリティ

sitespeed_extractor と waterfall_extractor で共通使用される
URL解析・リソースタイプ判定機能を提供。
"""

from urllib.parse import urlparse
from typing import List


def extract_host(url: str) -> str:
    """
    URLからホスト名を抽出

    Args:
        url: 対象URL

    Returns:
        ホスト名（例: "example.com:8080"）
    """
    try:
        return urlparse(url).netloc
    except Exception:
        return ''


def extract_path(url: str) -> str:
    """
    URLからパスを抽出（クエリ文字列含む）

    Args:
        url: 対象URL

    Returns:
        パス + クエリ（例: "/api/users?page=1"）
    """
    try:
        parsed = urlparse(url)
        return parsed.path + ('?' + parsed.query if parsed.query else '')
    except Exception:
        return ''


def determine_resource_type(url: str, content_type: str) -> str:
    """
    リソースタイプを判定

    Content-Type ヘッダーまたは URL 拡張子から
    リソースタイプを推定する。

    Args:
        url: 対象URL
        content_type: Content-Type ヘッダー値

    Returns:
        リソースタイプ（document, stylesheet, script, image, font, fetch, xhr, media, other）
    """
    content_type = content_type.lower()
    url_lower = url.lower()

    # Content-Type ベース判定
    content_type_mapping = [
        ('html', 'document'),
        ('css', 'stylesheet'),
        ('javascript', 'script'),
        ('script', 'script'),
        ('image', 'image'),
        ('font', 'font'),
        ('woff', 'font'),
        ('json', 'fetch'),
        ('xml', 'xhr'),
        ('video', 'media'),
        ('audio', 'media'),
    ]

    for keyword, resource_type in content_type_mapping:
        if keyword in content_type:
            return resource_type

    # URL 拡張子ベース判定（フォールバック）
    extension_mapping = [
        ('.css', 'stylesheet'),
        ('.js', 'script'),
    ]

    for ext, resource_type in extension_mapping:
        if ext in url_lower:
            return resource_type

    # 画像拡張子
    image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico']
    if any(ext in url_lower for ext in image_extensions):
        return 'image'

    # フォント拡張子
    font_extensions = ['.woff', '.woff2', '.ttf', '.eot', '.otf']
    if any(ext in url_lower for ext in font_extensions):
        return 'font'

    return 'other'


def get_status_text(status_code: int) -> str:
    """
    HTTPステータスコードからテキストを取得

    Args:
        status_code: HTTPステータスコード

    Returns:
        ステータステキスト（例: "OK", "Not Found"）
    """
    status_texts = {
        200: 'OK',
        201: 'Created',
        204: 'No Content',
        301: 'Moved Permanently',
        302: 'Found',
        304: 'Not Modified',
        400: 'Bad Request',
        401: 'Unauthorized',
        403: 'Forbidden',
        404: 'Not Found',
        500: 'Internal Server Error',
        502: 'Bad Gateway',
        503: 'Service Unavailable',
    }
    return status_texts.get(status_code, '')
