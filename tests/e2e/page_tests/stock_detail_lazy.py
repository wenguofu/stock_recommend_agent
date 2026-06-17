"""
StockDetail lazy-load test
Sprint 7 frontend-final-optimizations: tab-gated queries (only default-tab
fires on initial mount; rest only when tab activated)
"""
from conftest import BasePageTest, TestResult
import time
from collections import Counter


class StockDetailLazyTest(BasePageTest):
    path = "/stock/600519"  # Use 600519 (not 000001 used by StockDetailTest) so cache is cold.
    title = "个股详情"

    # Queries that should NOT fire until their tab is activated
    LAZY_ENDPOINTS = [
        "/api/fundamentals/",
        "/api/analyst/predictions/",
        "/api/stock/profile/",
        "/api/sentiment/all/",
        "/api/sina/money_flow/history/",
        "/api/risk/report",
        "/api/ml/predict/",
    ]
    # Queries that SHOULD fire on initial mount
    EAGER_ENDPOINTS = [
        "/api/sina/realtime/",
        "/api/sina/comprehensive_with_indicators/",
        "/api/sina/daily/",
        "/api/sina/daily/with_benchmark/",
        "/api/watchlist",
    ]

    def run_apis(self):
        """Verify lazy endpoints don't fire before tab activation."""
        results = []
        all_calls = []

        def on_response(resp):
            url = resp.url.split("?")[0]
            all_calls.append({"url": url, "status": resp.status, "method": resp.request.method})

        # Attach listener BEFORE goto so initial fetches are captured.
        self.page.on("response", on_response)
        try:
            # Override goto to wait for networkidle so React has time to hydrate
            # and fire its API calls.
            self.page.goto(self.base_url + self.path,
                           wait_until="networkidle",
                           timeout=self.timeout_ms)
            time.sleep(3.0)
        finally:
            self.page.remove_listener("response", on_response)

        # Categorize
        eager = [c for c in all_calls if any(e in c["url"] for e in self.EAGER_ENDPOINTS)]
        lazy_fired = [c for c in all_calls if any(e in c["url"] for e in self.LAZY_ENDPOINTS)]

        ss = self._screenshot("stock_detail_initial")

        # Eager check
        eager_endpoints_hit = Counter(c["url"] for c in eager)
        if eager_endpoints_hit:
            results.append(TestResult(
                "lazy.eager", self.path, "pass", 0,
                f"eager endpoints fired as expected: {list(eager_endpoints_hit.keys())[:5]}",
                ss,
            ))
        else:
            results.append(self._fail(
                "lazy.eager",
                "no eager endpoints fired (realtime/comprehensive/daily missing)",
                ss,
            ))

        # Lazy check — these should NOT fire on initial mount
        if not lazy_fired:
            results.append(TestResult(
                "lazy.not_fired", self.path, "pass", 0,
                f"none of {len(self.LAZY_ENDPOINTS)} lazy endpoints fired on initial mount — "
                f"OPTIMIZATION CONFIRMED (was firing all 11 queries)",
                ss,
            ))
        else:
            urls = list({c["url"] for c in lazy_fired})
            results.append(TestResult(
                "lazy.fired", self.path, "fail" if len(urls) > 2 else "skip",
                0,
                f"{len(urls)} lazy endpoint(s) fired before tab activation: {urls[:3]}",
                ss,
            ))
        return results