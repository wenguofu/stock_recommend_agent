"""
任务中心 /task-center
合并自 /task-execution 和 /task-results（Sprint 7 frontend-pages-merge 优化）
"""
from conftest import BasePageTest, TestResult


class TaskCenterTest(BasePageTest):
    path = "/task-center"
    title = "任务中心"
    api_endpoints = [
        "/api/scheduler/status",
        "/api/tasks",
    ]
    interactive = [
        {"selector": ".ant-tabs-tab:has-text('执行状态')", "description": "执行状态 Tab"},
        {"selector": ".ant-tabs-tab:has-text('执行结果')", "description": "执行结果 Tab",
         "optional": True},
        {"selector": ".ant-picker", "description": "日期选择器 (执行结果 tab)",
         "optional": True},
    ]


class TaskExecutionRedirectTest(BasePageTest):
    """Sprint 7 frontend-pages-merge: /task-execution → /task-center"""
    path = "/task-execution"
    title = "任务中心"

    def run_smoke(self):
        """Override: verify redirect happens, then check title."""
        import time
        results = []
        t0 = time.time()
        try:
            elapsed = self.goto()
            # Wait for SPA redirect
            self.page.wait_for_url("**/task-center", timeout=8000)
            time.sleep(1.0)
            ss = self._screenshot("redirect_task_execution")
            body_text = self.page.text_content("body") or ""
            if "任务中心" not in body_text:
                results.append(self._fail(
                    "smoke.redirect",
                    "redirected but 任务中心 not in body",
                    ss,
                ))
                return results
            results.append(TestResult(
                "smoke.redirect", self.path, "pass",
                (time.time() - t0) * 1000,
                f"redirected /task-execution → /task-center ({elapsed:.0f}ms)",
                ss,
            ))
            # Layout check
            try:
                self.page.wait_for_selector(".ant-layout, .ant-tabs", timeout=5000)
                results.append(TestResult(
                    "smoke.layout", self.path, "pass",
                    (time.time() - t0) * 1000,
                    "redirected page renders", ss,
                ))
            except Exception as e:
                results.append(self._fail("smoke.layout", str(e), ss))
        except Exception as e:
            results.append(self._fail("smoke.redirect", f"{e}"))
        return results


class TaskResultsRedirectTest(BasePageTest):
    """Sprint 7 frontend-pages-merge: /task-results → /task-center"""
    path = "/task-results"
    title = "任务中心"

    def run_smoke(self):
        import time
        results = []
        t0 = time.time()
        try:
            elapsed = self.goto()
            self.page.wait_for_url("**/task-center", timeout=8000)
            time.sleep(1.0)
            ss = self._screenshot("redirect_task_results")
            body_text = self.page.text_content("body") or ""
            if "任务中心" not in body_text:
                results.append(self._fail(
                    "smoke.redirect",
                    "redirected but 任务中心 not in body",
                    ss,
                ))
                return results
            results.append(TestResult(
                "smoke.redirect", self.path, "pass",
                (time.time() - t0) * 1000,
                f"redirected /task-results → /task-center ({elapsed:.0f}ms)",
                ss,
            ))
            try:
                self.page.wait_for_selector(".ant-layout, .ant-tabs", timeout=5000)
                results.append(TestResult(
                    "smoke.layout", self.path, "pass",
                    (time.time() - t0) * 1000,
                    "redirected page renders", ss,
                ))
            except Exception as e:
                results.append(self._fail("smoke.layout", str(e), ss))
        except Exception as e:
            results.append(self._fail("smoke.redirect", f"{e}"))
        return results