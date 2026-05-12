from curl_cffi import requests as cffi_requests
from scrapy.http import HtmlResponse
from scrapy.exceptions import NotConfigured
import logging

logger = logging.getLogger(__name__)

IMPERSONATE = "chrome124"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class CurlCffiMiddleware:
    """Replaces Scrapy's default HTTP client with curl_cffi for Chrome TLS fingerprint.
    Required to bypass Incapsula/Cloudflare WAF on thinksteroids.com and similar.
    """

    def process_request(self, request, spider):
        headers = {**DEFAULT_HEADERS, **{k.decode(): v[0].decode() for k, v in request.headers.items()}}
        try:
            r = cffi_requests.get(
                request.url,
                headers=headers,
                impersonate=IMPERSONATE,
                timeout=30,
                allow_redirects=True,
            )
            # Strip Content-Encoding — curl_cffi already decompressed the body.
            # If we pass the header through, Scrapy's HttpCompressionMiddleware
            # tries to decompress again and raises BadGzipFile / brotli errors.
            resp_headers = {k: v for k, v in r.headers.items()
                            if k.lower() not in ("content-encoding", "transfer-encoding")}
            return HtmlResponse(
                url=r.url,
                status=r.status_code,
                headers=resp_headers,
                body=r.content,
                encoding="utf-8",
                request=request,
            )
        except Exception as exc:
            logger.warning(f"curl_cffi failed for {request.url}: {exc}")
            raise
