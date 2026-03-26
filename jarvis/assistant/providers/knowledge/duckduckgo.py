"""
DuckDuckGo knowledge provider — Level 1 (search only).

Uses the duckduckgo_search library to retrieve web results without any API key.
This is the default knowledge provider because:
  - Zero configuration needed (no API key, no account)
  - Privacy-respecting (DuckDuckGo doesn't track users)
  - Returns decent snippets for grounding LLM responses
  - Lightweight — no heavy dependencies

How DuckDuckGo search works under the hood:
  The duckduckgo_search library sends requests to DuckDuckGo's HTML endpoint
  (not an official API — DDG doesn't have a free structured API). It parses the
  HTML response to extract titles, snippets, and URLs. This means:
    - It can break if DDG changes their HTML structure (rare but possible)
    - There's an implicit rate limit (~20-30 requests/minute before soft blocking)
    - Results are web-search quality — good for news, facts, definitions
    - NOT good for: real-time data (stocks, sports scores), deep research

  For the voice assistant use case, this is perfect: "what's happening in the
  cricket match" or "who won the election" gets a snippet that the LLM can
  summarize conversationally. Keep queries short and specific.

Alternatives to consider:
  - SearXNG: Self-hosted meta-search engine. Aggregates results from Google,
    Bing, DDG, etc. Runs on your own server — fully local after setup.
    Best for: privacy + quality. Needs: a server to run it on.
  - Tavily: AI-optimized search API. Returns clean, structured snippets designed
    for LLM consumption. Best for: RAG quality. Needs: API key ($5/mo free tier).
  - Brave Search API: Privacy-focused, good snippets, generous free tier.
    Best for: balance of quality + privacy. Needs: API key.

Platform notes:
  - Works on all platforms (Mac, Jetson, Pi) — just needs internet
  - Gracefully returns empty results when offline (is_available() checks first)
  - The library is pure Python, no native dependencies

Usage:
    knowledge = DuckDuckGoKnowledgeProvider()
    if knowledge.is_available():
        results = knowledge.search("latest India cricket score")
        for r in results:
            print(r.title, r.snippet)
"""

import time
import socket

from core.interfaces import KnowledgeProvider, SearchResult
from core.registry import register
from core.config import config
from core.logger import get_logger

log = get_logger("knowledge.ddg")

try:
    # Package was renamed from 'duckduckgo_search' to 'ddgs' in late 2025.
    # Try the new name first, fall back to the old name for older installs.
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    HAS_DDGS = True
except ImportError:
    HAS_DDGS = False
    log.debug(
        "DuckDuckGo search not installed. "
        "Install with: pip install ddgs"
    )


@register("knowledge", "duckduckgo")
class DuckDuckGoKnowledgeProvider(KnowledgeProvider):
    """
    DuckDuckGo web search — no API key, works out of the box.

    Config (config.yaml):
        knowledge:
          provider: "duckduckgo"
          enabled: true              # master switch
          max_results: 3             # keep low for edge hardware context windows
          region: "in-en"            # DuckDuckGo region code (India-English)
          safesearch: "moderate"     # off, moderate, strict
          timeout: 5                 # seconds before giving up on a search
    """

    def __init__(self, **kwargs):
        if not HAS_DDGS:
            raise ImportError(
                "DuckDuckGo search not installed. "
                "Install with: pip install ddgs"
            )

        knowledge_cfg = config.get("knowledge", {})
        self._max_results = knowledge_cfg.get("max_results", 3)
        self._region = knowledge_cfg.get("region", "in-en")
        self._safesearch = knowledge_cfg.get("safesearch", "moderate")
        self._timeout = knowledge_cfg.get("timeout", 5)

        # Cache availability status to avoid repeated connectivity checks.
        # Reset to None after a failed search so the next query re-checks.
        self._available: bool | None = None

        log.info(
            "DuckDuckGo knowledge provider ready (region=%s, max_results=%d)",
            self._region, self._max_results,
        )

    def search(self, query: str, max_results: int = 0) -> list[SearchResult]:
        """
        Search DuckDuckGo and return results with titles and snippets.

        The snippets are typically 1-2 sentences — perfect for injecting into
        a 3B model's context without blowing up the KV cache.
        """
        if not max_results:
            max_results = self._max_results

        if not self.is_available():
            log.warning("Knowledge search unavailable (offline). Query: %s", query)
            return []

        start = time.time()
        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(
                    query,
                    region=self._region,
                    safesearch=self._safesearch,
                    max_results=max_results,
                ))

            results = []
            for r in raw_results:
                results.append(SearchResult(
                    title=r.get("title", ""),
                    snippet=r.get("body", ""),
                    url=r.get("href", ""),
                    source="duckduckgo",
                ))

            latency = time.time() - start
            log.info(
                'Knowledge search (%.2fs): "%s" → %d results',
                latency, query[:60], len(results),
            )
            return results

        except Exception as e:
            latency = time.time() - start
            log.warning(
                'Knowledge search failed (%.2fs): "%s" — %s',
                latency, query[:60], e,
            )
            # Reset availability cache so next query re-checks connectivity
            self._available = None
            return []

    def fetch(self, url: str) -> SearchResult | None:
        """
        Not implemented for DuckDuckGo (Level 1 provider — search only).

        To add fetch capability, implement a separate provider using
        trafilatura or readability-lxml for content extraction:

            import trafilatura
            downloaded = trafilatura.fetch_url(url)
            text = trafilatura.extract(downloaded)

        trafilatura is excellent at extracting article text from any webpage
        while stripping navigation, ads, and boilerplate. It's the same
        library that Common Crawl and many LLM training pipelines use.
        """
        log.debug("fetch() not supported by DuckDuckGo provider (Level 1 — search only)")
        return None

    def is_available(self) -> bool:
        """
        Check internet connectivity by attempting a socket connection to DuckDuckGo.

        Uses a raw socket instead of an HTTP request — faster (~50ms vs ~200ms)
        and doesn't count against any rate limits. Caches the result so repeated
        calls within a session don't re-check.

        The 2-second timeout is generous — on a normal connection this takes <100ms.
        If it takes longer, the connection is too flaky for real-time voice search.
        """
        if self._available is not None:
            return self._available

        try:
            sock = socket.create_connection(("duckduckgo.com", 443), timeout=2)
            sock.close()
            self._available = True
        except (socket.timeout, OSError):
            self._available = False
            log.info("Internet not available — knowledge features disabled")

        return self._available

    @property
    def capabilities(self) -> list[str]:
        return ["search"]
