"""
Sprint 6 主入口: 打开 portal, 跑全部 25 个页面的 E2E 测试

用法:
  # 默认 smoke 模式 (页面加载 + 基本元素)
  .venv/bin/python tests/e2e/portal_e2e.py

  # API 测试模式 (抓取所有 stockAPI 调用, 检查 5xx)
  .venv/bin/python tests/e2e/portal_e2e.py --mode apis

  # 完整模式 (含 click)
  .venv/bin/python tests/e2e/portal_e2e.py --mode full

  # 单页面
  .venv/bin/python tests/e2e/portal_e2e.py --page /monitoring

  # 指定浏览器
  .venv/bin/python tests/e2e/portal_e2e.py --browser chromium --headless
"""
import os
import sys
import argparse
import time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, "tests", "e2e"))

from conftest import BasePageTest, TestResult, make_report, save_report, PORTAL_URL
from page_tests import ALL_TESTS, BY_PATH


def main():
    parser = argparse.ArgumentParser(description="Portal E2E 浏览器测试")
    parser.add_argument("--mode", choices=["smoke", "apis", "full"], default="smoke",
                        help="测试模式: smoke (页面加载) | apis (抓 API) | full (含 click)")
    parser.add_argument("--page", help="只测单个页面, 如 /monitoring")
    parser.add_argument("--base-url", default=PORTAL_URL, help="Portal base URL")
    parser.add_argument("--browser", default="chromium", choices=["chromium", "firefox"])
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--no-headless", dest="headless", action="store_false")
    parser.add_argument("--output-format", choices=["json", "md", "both"], default="both")
    args = parser.parse_args()

    # 校验 base-url 可达
    import urllib.request
    try:
        with urllib.request.urlopen(args.base_url + "/api/health", timeout=5) as r:
            print(f"✅ {args.base_url}/api/health → {r.status}")
    except Exception as e:
        print(f"❌ 后端不可达: {e}\n  请先启动 Flask: .venv/bin/python api_server.py")
        sys.exit(1)

    # 选 pages
    if args.page:
        cls = BY_PATH.get(args.page)
        if not cls:
            print(f"❌ 未知 path: {args.page}\n  可用: {list(BY_PATH.keys())[:5]}...")
            sys.exit(1)
        tests = [cls]
    else:
        tests = ALL_TESTS
    print(f"\n🚀 E2E 测试: mode={args.mode} pages={len(tests)} browser={args.browser}")
    print(f"   URL: {args.base_url}\n")

    # 启动 Playwright
    from playwright.sync_api import sync_playwright
    results = []
    start = time.time()
    with sync_playwright() as p:
        browser = getattr(p, args.browser).launch(headless=args.headless)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.set_default_timeout(20_000)

        for i, cls in enumerate(tests, 1):
            tname = cls.__name__
            try:
                t = cls(page, base_url=args.base_url)
                page_results = t.run_all(mode=args.mode)
                results.extend(page_results)
            except Exception as e:
                import traceback
                results.append(TestResult(
                    "init", cls.path, "fail", 0,
                    f"{tname} 初始化失败: {e}\n{traceback.format_exc()[:300]}"
                ))

            # 进度
            passed = sum(1 for r in results if r.status == "pass")
            failed = sum(1 for r in results if r.status == "fail")
            print(f"  [{i:2d}/{len(tests)}] {cls.path:35s} → 累计 pass={passed} fail={failed}")

        # 关闭
        context.close()
        browser.close()

    # 报告
    report = make_report(results, start)
    save_report(report, mode=args.mode)

    # 总结
    s = report["summary"]
    print(f"\n{'=' * 60}")
    print(f"总结: {s['passed']} pass / {s['failed']} fail / {s['skipped']} skip")
    print(f"耗时: {s['duration_s']}s")
    if s["failed"] > 0:
        print(f"\n失败明细:")
        for r in report["results"]:
            if r["status"] == "fail":
                print(f"  - {r['page']} :: {r['name']}: {r['details'][:200]}")
        sys.exit(1)
    else:
        print(f"\n✅ 全部通过!")
        sys.exit(0)


if __name__ == "__main__":
    main()
