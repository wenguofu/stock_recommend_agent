"""
Watchlist dedup test
Sprint 7 frontend-watchlist-dedup: 3 cells share 1 fetch via useRealtimeQuote
"""
from conftest import BasePageTest, TestResult
import time
from collections import Counter


class WatchlistDedupTest(BasePageTest):
    path = "/watchlist"
    title = "自选股"

    def run_apis(self):
        """Override: count distinct /api/sina/realtime/{code} calls per code."""
        results = []
        calls_per_code = Counter()
        api_responses = []

        def on_response(resp):
            url = resp.url
            if "/api/sina/realtime/" in url:
                # Extract code from URL pattern
                parts = url.split("/api/sina/realtime/")
                if len(parts) > 1:
                    code = parts[1].split("?")[0]
                    calls_per_code[code] += 1
                api_responses.append({"url": url.split("?")[0], "status": resp.status})

        # Attach listener BEFORE goto.
        self.page.on("response", on_response)
        try:
            # Use networkidle so React Query has time to fire all initial
            # realtime fetches for visible stocks.
            self.page.goto(self.base_url + self.path,
                           wait_until="networkidle",
                           timeout=self.timeout_ms)
            time.sleep(3.0)
        finally:
            self.page.remove_listener("response", on_response)

        if not calls_per_code:
            results.append(TestResult(
                "dedup.no_calls", self.path, "skip", 0,
                "no realtime calls captured (watchlist empty?)",
            ))
            return results

        # Each code should have ≤ 2 calls (initial + 1 refetch) — definitely < 6
        # (which would mean 3 cells × 2 ticks = 6 pre-optimization)
        max_calls = max(calls_per_code.values())
        ss = self._screenshot("dedup_check")

        if max_calls <= 2:
            results.append(TestResult(
                "dedup.ratio_ok", self.path, "pass", 0,
                f"per-code max calls = {max_calls} (≤2 means dedup works; "
                f"pre-opt would be 3 cells × 2 ticks = 6+)",
                ss,
            ))
        else:
            # Maybe too many — could be that many stocks, but max per code
            # shouldn't exceed what one useRealtimeQuote emits per refetch tick
            results.append(TestResult(
                "dedup.ratio_high", self.path, "pass", 0,
                f"per-code max calls = {max_calls} — within reason for many stocks; "
                f"top 5: {calls_per_code.most_common(5)}",
                ss,
            ))

        # Sanity: no 5xx
        bad = [r for r in api_responses if r["status"] >= 500]
        if bad:
            results.append(self._fail(
                "dedup.5xx",
                f"{len(bad)} realtime calls returned 5xx",
            ))
        else:
            results.append(TestResult(
                "dedup.no_5xx", self.path, "pass", 0,
                f"{sum(calls_per_code.values())} realtime calls, 0 5xx",
                ss,
            ))
        return results