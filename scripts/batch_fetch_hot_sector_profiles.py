#!/usr/bin/env python3
"""
批量拉取热门板块股票的基本面数据（F10）并加载到数据库
使用 Chrome DevTools MCP 抓取东方财富 F10 页面

Usage:
    python scripts/batch_fetch_hot_sector_profiles.py [--sectors SectorsFile] [--limit N]

流程:
    1. 从 /api/sectors 获取所有板块列表
    2. 从 /api/sectors/performance 获取热门板块排序
    3. 对每个板块的成分股串行抓取 F10 数据
    4. 写入 stock_profiles 和 prediction_aggregates 表
"""
import sys, os, json, time, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import urllib.request
from datetime import datetime

API = os.environ.get('A_STOCK_API', 'http://127.0.0.1:35000')
CHROME_MCP = '/opt/homebrew/bin/chrome-devtools-mcp'
MCP_CALLER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp_caller.js')

DB_HOST = '127.0.0.1'
DB_USER = 'root'
DB_PASS = ''
DB_NAME = 'stock_trading'

PROGRESS_FILE = '/tmp/fetch_profiles_progress.json'


def api_get(path):
    url = f"{API}{path}"
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read())


def mcp_call(tool_name, arguments=None):
    """通过 Node.js mcp_caller.js 发送单个 JSON-RPC 命令到 Chrome"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments or {}
        }
    }
    result = subprocess.run(
        ['node', MCP_CALLER],
        input=(json.dumps(payload) + '\n').encode(),
        capture_output=True, timeout=40
    )
    output = result.stdout.decode().strip()
    if not output:
        return None
    try:
        return json.loads(output)
    except:
        return None


def mcp_snapshot():
    """获取当前页面快照"""
    r = mcp_call('take_snapshot', {})
    if r and 'result' in r:
        content = r['result'][0].get('content', [])
        text_lines = []
        for item in content:
            if isinstance(item, dict):
                texts = item.get('text', '')
                if texts:
                    text_lines.append(texts)
            elif isinstance(item, str):
                text_lines.append(item)
        return '\n'.join(text_lines)
    return ''


def parse_hxtc(snapshot):
    """解析 核心题材 页面（CDP innerText 使用 \t 分隔符）"""
    # CDP innerText uses \t for tab-separated content - normalize to lines
    normalized = snapshot.replace('\t', '\n')
    lines = normalized.split('\n')
    data = {
        'sector_themes': [],
        'main_business': '',
        'core_competitiveness': '',
        'industry_background': '',
        'business_description': '',
    }

    i = 0
    while i < len(lines):
        l = lines[i].strip()
        if l == '概念题材' and i + 1 < len(lines):
            # 解析题材列表
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt or nxt in ['题材亮点', '行业背景', '核心竞争力', '题材详情', '所属板块', '经营范围', '主营业务', '历史题材']:
                    break
                parts = nxt.rsplit(None, 1)
                if len(parts) == 2 and parts[1].startswith(('+', '-')) and '%' in parts[1]:
                    data['sector_themes'].append(nxt)
                j += 1
            i = j - 1
        elif l == '行业背景' and i + 1 < len(lines):
            parts = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt or nxt in ['核心竞争力', '题材详情', '所属板块', '经营范围', '主营业务', '历史题材']:
                    break
                parts.append(nxt)
                j += 1
            data['industry_background'] = '\n'.join(parts)
            i = j - 1
        elif l == '核心竞争力' and i + 1 < len(lines):
            parts = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt or nxt in ['行业背景', '题材详情', '所属板块', '经营范围', '主营业务', '历史题材']:
                    break
                parts.append(nxt)
                j += 1
            data['core_competitiveness'] = '\n'.join(parts)
            i = j - 1
        elif l == '主营业务' and i + 1 < len(lines):
            parts = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if not nxt or nxt in ['行业背景', '核心竞争力', '题材亮点', '题材详情', '所属板块', '经营范围', '历史题材']:
                    break
                parts.append(nxt)
                j += 1
            data['main_business'] = '\n'.join(parts)
            i = j - 1
        i += 1

    return data


def parse_gsgk(snapshot):
    """解析 公司概况 页面 - 提取经营范围"""
    lines = snapshot.split('\n')
    data = {'business_description': ''}
    for i, l in enumerate(lines):
        if l == '经营范围' and i + 1 < len(lines):
            parts = []
            for j in range(i + 1, min(i + 20, len(lines))):
                nxt = lines[j].strip()
                if not nxt or nxt in ['主营业务', '公司大事', '股东研究', '核心题材', '盈利预测', '财务分析']:
                    break
                parts.append(nxt)
            data['business_description'] = '\n'.join(parts)
            break
    return data


def parse_ylyc(snapshot):
    """解析 盈利预测 页面 - 提取机构预测汇总"""
    lines = snapshot.split('\n')
    data = {
        'eps_2025a': '', 'eps_2026e': '', 'eps_2027e': '', 'eps_2028e': '',
        'net_profit_2025a': '', 'net_profit_2026e': '', 'net_profit_2027e': '', 'net_profit_2028e': '',
        'revenue_2025a': '', 'revenue_2026e': '', 'revenue_2027e': '', 'revenue_2028e': '',
        'roe_2025a': '', 'roe_2026e': '', 'roe_2027e': '', 'roe_2028e': '',
        'rating_score': '', 'rating_label': '', 'analyst_count': '', 'avg_pe_ttm': '',
    }
    for i, l in enumerate(lines):
        l = l.strip()
        # 预测统计 section
        if l == '预测统计':
            # next rows contain the table
            j = i + 1
            while j < len(lines) and j < i + 30:
                row = lines[j].strip()
                if '每股收益' in row and '2026' in row:
                    # 2026E EPS: parse number before parentheses
                    import re
                    m = re.search(r'2026E.*?\((\d+)家\)', row)
                    if m:
                        val_m = re.search(r'([\d.]+)', row.split('2026E')[1])
                        if val_m:
                            data['eps_2026e'] = val_m.group(1)
                elif '归属于母公司' in row and '净利润' in row:
                    import re
                    m = re.search(r'(\d+\.?\d*)\s*亿', row)
                    if m:
                        if '2026E' in row:
                            data['net_profit_2026e'] = m.group(1) + '亿'
                elif '营业总收入' in row and '2026E' in row:
                    import re
                    m = re.search(r'(\d+\.?\d*)\s*亿', row)
                    if m:
                        data['revenue_2026e'] = m.group(1) + '亿'
                elif '净资产收益率' in row and '2026E' in row:
                    import re
                    m = re.search(r'([\d.]+)%', row)
                    if m:
                        data['roe_2026e'] = m.group(1) + '%'
                j += 1
    return data


def fetch_f10_profile(code, prefix='SZ'):
    """抓取单只股票的 F10 数据（使用 CDP 直连方式）"""
    result = {
        'code': code,
        'stock_name': '',
        'main_business': '',
        'sector_themes': [],
        'core_competitiveness': '',
        'industry_background': '',
        'business_description': '',
        'eps_2025a': '', 'eps_2026e': '', 'eps_2027e': '', 'eps_2028e': '',
        'net_profit_2025a': '', 'net_profit_2026e': '', 'net_profit_2027e': '', 'net_profit_2028e': '',
        'revenue_2025a': '', 'revenue_2026e': '', 'revenue_2027e': '', 'revenue_2028e': '',
        'roe_2025a': '', 'roe_2026e': '', 'roe_2027e': '', 'roe_2028e': '',
        'rating_score': '', 'rating_label': '', 'analyst_count': '', 'avg_pe_ttm': '',
    }

    try:
        # 调用 Node.js CDP fetch 脚本
        r = subprocess.run(
            ['node', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cdp_fetch.js'), code, prefix],
            capture_output=True, timeout=120
        )
        if r.returncode != 0 or not r.stdout:
            print(f"  [{code}] 抓取失败: script rc={r.returncode}")
            return result

        data = json.loads(r.stdout.decode().strip())
        hxtc_text = data.get('hxtc', '')
        gsgk_text = data.get('gsgk', '')
        ylyc_text = data.get('ylyc', '')

        # parse_hxtc needs list of lines - CDP text uses \t as separator
        hxtc_data = parse_hxtc(hxtc_text)
        result.update(hxtc_data)

        # 提取股票名称
        import re
        for line in hxtc_text.split('\n'):
            if code in line:
                m = re.search(r'([一-龥]+)\s*\(?\s*' + re.escape(code), line)
                if m:
                    result['stock_name'] = m.group(1)
                    break

        gsgk_data = parse_gsgk(gsgk_text)
        if gsgk_data.get('business_description'):
            result['business_description'] = gsgk_data['business_description']

        ylyc_data = parse_ylyc(ylyc_text)
        result.update(ylyc_data)

        print(f"  [{code}] 抓取完成: 主营={result['main_business'][:30] if result['main_business'] else 'N/A'}... 题材={len(result['sector_themes'])}条")

    except Exception as e:
        print(f"  [{code}] 抓取失败: {e}")

    return result


def save_to_mysql(profile_data):
    """保存到 MySQL"""
    import pymysql

    conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, charset='utf8mb4')
    cur = conn.cursor()

    # stock_profiles
    cur.execute("""
        INSERT INTO stock_profiles (code, stock_name, main_business, sector_themes, core_competitiveness, industry_background, business_description)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            stock_name=VALUES(stock_name),
            main_business=VALUES(main_business),
            sector_themes=VALUES(sector_themes),
            core_competitiveness=VALUES(core_competitiveness),
            industry_background=VALUES(industry_background),
            business_description=VALUES(business_description)
    """, (
        profile_data['code'],
        profile_data.get('stock_name', ''),
        profile_data.get('main_business', ''),
        profile_data.get('sector_themes', ''),
        profile_data.get('core_competitiveness', ''),
        profile_data.get('industry_background', ''),
        profile_data.get('business_description', ''),
    ))

    # prediction_aggregates (only if we have analyst data)
    if profile_data.get('eps_2026e'):
        cur.execute("""
            INSERT INTO prediction_aggregates (code, eps_2025a, eps_2026e, eps_2027e, eps_2028e,
                net_profit_2025a, net_profit_2026e, net_profit_2027e, net_profit_2028e,
                revenue_2025a, revenue_2026e, revenue_2027e, revenue_2028e,
                roe_2025a, roe_2026e, roe_2027e, roe_2028e,
                rating_score, rating_label, analyst_count, avg_pe_ttm)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                eps_2026e=VALUES(eps_2026e), eps_2027e=VALUES(eps_2027e), eps_2028e=VALUES(eps_2028e),
                net_profit_2026e=VALUES(net_profit_2026e), net_profit_2027e=VALUES(net_profit_2027e), net_profit_2028e=VALUES(net_profit_2028e),
                revenue_2026e=VALUES(revenue_2026e), revenue_2027e=VALUES(revenue_2027e), revenue_2028e=VALUES(revenue_2028e),
                roe_2026e=VALUES(roe_2026e), roe_2027e=VALUES(roe_2027e), roe_2028e=VALUES(roe_2028e),
                rating_score=VALUES(rating_score), rating_label=VALUES(rating_label),
                analyst_count=VALUES(analyst_count), avg_pe_ttm=VALUES(avg_pe_ttm)
        """, (
            profile_data['code'],
            profile_data.get('eps_2025a', ''),
            profile_data.get('eps_2026e', ''),
            profile_data.get('eps_2027e', ''),
            profile_data.get('eps_2028e', ''),
            profile_data.get('net_profit_2025a', ''),
            profile_data.get('net_profit_2026e', ''),
            profile_data.get('net_profit_2027e', ''),
            profile_data.get('net_profit_2028e', ''),
            profile_data.get('revenue_2025a', ''),
            profile_data.get('revenue_2026e', ''),
            profile_data.get('revenue_2027e', ''),
            profile_data.get('revenue_2028e', ''),
            profile_data.get('roe_2025a', ''),
            profile_data.get('roe_2026e', ''),
            profile_data.get('roe_2027e', ''),
            profile_data.get('roe_2028e', ''),
            profile_data.get('rating_score', ''),
            profile_data.get('rating_label', ''),
            profile_data.get('analyst_count', ''),
            profile_data.get('avg_pe_ttm', ''),
        ))

    conn.commit()
    cur.close()
    conn.close()


def get_sector_stocks(sector_name):
    """从API获取板块成分股"""
    import urllib.parse
    try:
        encoded = urllib.parse.quote(sector_name, safe='')
        raw = api_get(f"/api/sectors/{encoded}")
        # API returns {'stocks': [...]} not {'data': [...]}
        if isinstance(raw, dict):
            return raw.get('stocks', []) or raw.get('data', [])
        elif isinstance(raw, list):
            return raw
        return []
    except Exception as e:
        print(f"  获取板块[{sector_name}]成分股失败: {e}")
        return []


def load_progress():
    """加载进度"""
    try:
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    except:
        return {'done': [], 'sectors_processed': []}


def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=50, help='最多处理多少只股票')
    parser.add_argument('--sectors-file', type=str, default='', help='指定板块文件（一行一个板块名）')
    args = parser.parse_args()

    print("=" * 60)
    print("批量拉取热门板块股票基本面数据")
    print("=" * 60)

    # 获取板块列表
    if args.sectors_file:
        with open(args.sectors_file) as f:
            sector_names = [l.strip() for l in f if l.strip()]
        print(f"从文件加载 {len(sector_names)} 个板块")
    else:
        try:
            data = api_get('/api/sectors')
            sector_names = data if isinstance(data, list) else data.get('data', [])
        except Exception as e:
            print(f"获取板块列表失败: {e}")
            return
        print(f"从API获取 {len(sector_names)} 个板块")

    progress = load_progress()
    total = args.limit
    fetched = 0
    total_stocks = 0

    for sector_name in sector_names:
        print(f"\n📂 板块: {sector_name}")
        stocks = get_sector_stocks(sector_name)
        if not stocks:
            print(f"  无成分股或获取失败，跳过")
            continue

        print(f"  成分股数量: {len(stocks)}")
        total_stocks += len(stocks)

        for stock in stocks:
            code = stock.get('code', '')
            name = stock.get('name', '')

            if not code:
                continue

            if code in progress['done']:
                print(f"  ⏭ [{code}] {name} 已抓取，跳过")
                continue

            # 判断前缀
            if code.startswith('6'):
                prefix = 'SH'
            else:
                prefix = 'SZ'

            print(f"  🌐 [{code}] {name} 抓取中...", end='', flush=True)
            profile = fetch_f10_profile(code, prefix)

            if profile.get('main_business') or profile.get('sector_themes'):
                profile['stock_name'] = name or profile.get('stock_name', name)
                save_to_mysql(profile)
                progress['done'].append(code)
                save_progress(progress)
                fetched += 1
                print(f" ✅")
            else:
                print(f" ⚠️ 数据为空")

            if fetched >= total:
                print(f"\n达到上限 {total}，停止")
                break

            time.sleep(3)  # 串行，间隔3秒避免被反爬

        if fetched >= total:
            break

    print(f"\n{'=' * 60}")
    print(f"完成！共抓取 {fetched} 只股票，耗时 {total_stocks} 只成分股扫描")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
