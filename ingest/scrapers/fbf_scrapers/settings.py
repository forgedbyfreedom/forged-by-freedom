BOT_NAME = "fbf_scrapers"
SPIDER_MODULES = ["fbf_scrapers.spiders"]
NEWSPIDER_MODULE = "fbf_scrapers.spiders"

# curl_cffi replaces the default downloader — WAF bypass via Chrome TLS fingerprint
DOWNLOADER_MIDDLEWARES = {
    "fbf_scrapers.middlewares.CurlCffiMiddleware": 543,
    "scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware": 590,
}

# Be polite — forums hate hammering
DOWNLOAD_DELAY = 2.5
RANDOMIZE_DOWNLOAD_DELAY = True   # 1.25x–2.5x the base delay
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2.0
AUTOTHROTTLE_MAX_DELAY = 15.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

CONCURRENT_REQUESTS = 1
CONCURRENT_REQUESTS_PER_DOMAIN = 1

ROBOTSTXT_OBEY = False  # Forums typically block all bots in robots.txt

# Retry on transient errors
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [429, 500, 502, 503, 504]

# Don't cache — we want fresh data each run
HTTPCACHE_ENABLED = False

# Output
FEEDS = {}  # pipelines handle all output
ITEM_PIPELINES = {
    "fbf_scrapers.pipelines.TextOutputPipeline": 100,
    "fbf_scrapers.pipelines.JanoshikStructuredPipeline": 200,
}

LOG_LEVEL = "INFO"
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

# Suppress Scrapy 2.15 deprecation warnings from pre-2.13 method signatures
# (open_spider/process_item/process_request with spider arg, start_requests)
import warnings
from scrapy.exceptions import ScrapyDeprecationWarning  # noqa: E402
warnings.filterwarnings("ignore", category=ScrapyDeprecationWarning)
