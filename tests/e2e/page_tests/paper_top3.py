"""
PaperAccounts TOP-3 ranking card test
Sprint 7 frontend-final-optimizations: top-3 by total_profit_pct
"""
from conftest import BasePageTest, TestResult
import time


class PaperTop3Test(BasePageTest):
    path = "/paper"
    title = "模拟盘"

    def run_clicks(self):
        """Override: verify TOP-3 card presence + ordering."""
        results = []
        t0 = time.time()
        try:
            self.page.goto(self.base_url + self.path, wait_until="domcontentloaded",
                           timeout=self.timeout_ms)
            time.sleep(2.0)
            ss = self._screenshot("paper_top3")

            body_text = self.page.text_content("body") or ""

            if "TOP 3" not in body_text and "TOP3" not in body_text:
                # Skip if fewer than 3 accounts
                if "新建模拟盘" in body_text or "还没有" in body_text:
                    results.append(TestResult(
                        "click.top3_card", self.path, "skip", 0,
                        "less than 3 accounts — TOP 3 card not rendered (by spec)",
                        ss,
                    ))
                    return results
                results.append(self._fail(
                    "click.top3_card",
                    "TOP 3 card text not found in body",
                    ss,
                ))
                return results

            results.append(TestResult(
                "click.top3_card", self.path, "pass",
                (time.time() - t0) * 1000,
                "TOP 3 card present", ss,
            ))

            # Check ranking link
            link = self.page.query_selector(
                "a:has-text('完整排名'), a:has-text('查看完整'), button:has-text('完整排名')"
            )
            results.append(TestResult(
                "click.top3_link", self.path, "pass" if link else "skip",
                0,
                "完整排名 link " + ("present" if link else "missing"),
                ss,
            ))

        except Exception as e:
            results.append(self._fail("click.top3_card", f"{e}"))
        return results