#!/usr/bin/env bash
# Sprint 6: 一键 E2E 套件 (smoke + apis + full)
# 用法: bash tests/e2e/run_all.sh
set -e

cd "$(dirname "$0")/../.."

PYTHON=".venv/bin/python"
E2E_DIR="tests/e2e"
LOG_DIR="$E2E_DIR/reports"
TS=$(date +%Y%m%d_%H%M%S)

echo "================================================================"
echo "🚀 Portal E2E 测试套件"
echo "时间: $TS"
echo "================================================================"

# 0. 健康检查
echo ""
echo "[0/4] 健康检查 ..."
$PYTHON -c "
import urllib.request
try:
    r = urllib.request.urlopen('http://localhost:35000/api/health', timeout=5)
    print(f'  Flask: {r.status} ✅')
except Exception as e:
    print(f'  Flask: ❌ {e}')
    print('  请先启动: nohup .venv/bin/python api_server.py &')
    exit(1)
"

# 1. Smoke
echo ""
echo "[1/4] Smoke (25 个页面, 加载 + 元素检测) ..."
$PYTHON $E2E_DIR/portal_e2e.py --mode smoke 2>&1 | tail -10

# 2. API
echo ""
echo "[2/4] API 拦截 (抓所有 /api/ 调用, 检查 5xx) ..."
$PYTHON $E2E_DIR/portal_e2e.py --mode apis 2>&1 | tail -10

# 3. Full (含 click)
echo ""
echo "[3/4] Full (含 click 交互) ..."
$PYTHON $E2E_DIR/portal_e2e.py --mode full 2>&1 | tail -10

# 4. 总结
echo ""
echo "================================================================"
echo "📊 总结"
echo "================================================================"
ls -lt $LOG_DIR/report_full_*.md 2>/dev/null | head -1 | awk '{print "  最新报告: " $NF}'
ls -lt $LOG_DIR/report_full_*.json 2>/dev/null | head -1 | awk '{print "  JSON 报告: " $NF}'

# 解析最新的 full 报告
LATEST=$(ls -t $LOG_DIR/report_full_*.json 2>/dev/null | head -1)
if [ -n "$LATEST" ]; then
    $PYTHON -c "
import json, sys
with open('$LATEST') as f:
    r = json.load(f)
s = r['summary']
print(f'  ✅ 通过: {s[\"passed\"]}')
print(f'  ❌ 失败: {s[\"failed\"]}')
print(f'  ⏭️  跳过: {s[\"skipped\"]}')
print(f'  耗时:   {s[\"duration_s\"]}s')
sys.exit(0 if s['failed'] == 0 else 1)
"
fi

echo ""
echo "✅ 全部完成!"
