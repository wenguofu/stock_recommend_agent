#!/usr/bin/env python3
"""
群聊复盘监控 — 监控 ~/Desktop/trading_chats/ 目录
发现新文件自动解析, 提取板块/股票/买卖建议, 推送到微信
"""
import sys, os, re, json, time, hashlib
from datetime import datetime
from collections import Counter

WATCH_DIR = os.path.expanduser('~/Desktop/trading_chats')
STATE_FILE = os.path.expanduser('~/.hermes/chat_monitor_state.json')

# 板块关键词
SECTOR_KEYWORDS = {
    'AI/人工智能': ['AI', '人工智能', '大模型', 'ChatGPT', 'GPT', 'LLM', '深度学习'],
    '半导体': ['半导体', '芯片', '存储', '封测', '晶圆', '光刻', 'EDA', 'HBM'],
    '机器人': ['机器人', '人形', '具身智能', '减速器', '伺服', '丝杠'],
    '算力': ['算力', '数据中心', 'GPU', '服务器', '光模块', 'CPO', '液冷'],
    '新能源车': ['新能源车', '电动车', '电池', '锂电', '固态电池', '钠电池'],
    '消费电子': ['消费电子', '手机', '果链', '华为链', 'MR', 'Vision Pro'],
    '低空经济': ['低空', '无人机', 'eVTOL', '飞行汽车'],
    '军工': ['军工', '航天', '船舶', '导弹', '雷达'],
    '医药': ['医药', '创新药', 'CXO', '医疗器械', '减肥药'],
    '光伏': ['光伏', '储能', '逆变器', 'HJT'],
}

# 股票代码正则
STOCK_PATTERN = re.compile(r'(?<!\d)(6\d{5}|0\d{5}|3\d{5})(?!\d)')

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {'processed_files': {}, 'last_scan': None}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def parse_file(filepath):
    """解析聊天文件, 提取板块和股票"""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    # 提取板块热度
    sector_hits = Counter()
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            count = content.count(kw)
            if count > 0:
                sector_hits[sector] += count
    
    # 提取股票代码
    stocks = list(set(STOCK_PATTERN.findall(content)))
    
    # 提取买卖倾向
    buy_keywords = ['买入', '加仓', '建仓', '看好', '推荐', 'all in', '梭哈', '低吸']
    sell_keywords = ['卖出', '减仓', '清仓', '看空', '回避', '止损', '割肉']
    
    buy_mentions = sum(content.count(kw) for kw in buy_keywords)
    sell_mentions = sum(content.count(kw) for kw in sell_keywords)
    
    sentiment = '偏多' if buy_mentions > sell_mentions * 1.5 else ('偏空' if sell_mentions > buy_mentions * 1.5 else '中性')
    
    # 提取关键消息 (包含板块关键词的行)
    key_messages = []
    for line in lines:
        line = line.strip()
        if len(line) < 10: continue
        for keywords in SECTOR_KEYWORDS.values():
            if any(kw in line for kw in keywords):
                key_messages.append(line[:120])
                break
    
    return {
        'file': os.path.basename(filepath),
        'lines': len(lines),
        'sectors': dict(sector_hits.most_common(8)),
        'stocks': stocks[:15],
        'sentiment': sentiment,
        'buy_mentions': buy_mentions,
        'sell_mentions': sell_mentions,
        'key_messages': key_messages[:5],
        'parsed_at': datetime.now().isoformat(),
    }

def generate_report(result):
    """生成报告文本"""
    lines = ['📊 群聊复盘分析', f"文件: {result['file']}  ({result['lines']}行)", '']
    
    if result['sectors']:
        lines.append('🔥 板块热度:')
        for sector, count in result['sectors'].items():
            bar = '█' * min(count, 10)
            lines.append(f'  {sector}: {bar} ({count}次)')
    
    if result['stocks']:
        lines.append(f"\n📈 提及股票 ({len(result['stocks'])}只):")
        lines.append(f"  {', '.join(result['stocks'][:10])}")
    
    lines.append(f"\n📊 情绪: {result['sentiment']}  买{result['buy_mentions']}次 / 卖{result['sell_mentions']}次")
    
    if result['key_messages']:
        lines.append('\n💬 关键消息:')
        for msg in result['key_messages']:
            lines.append(f'  > {msg}')
    
    return '\n'.join(lines)

def scan():
    state = load_state()
    
    if not os.path.exists(WATCH_DIR):
        os.makedirs(WATCH_DIR, exist_ok=True)
        print(f'Created {WATCH_DIR}')
        return None
    
    new_files = []
    for fname in sorted(os.listdir(WATCH_DIR)):
        if not fname.endswith(('.md', '.txt', '.log')):
            continue
        
        fpath = os.path.join(WATCH_DIR, fname)
        mtime = os.path.getmtime(fpath)
        file_hash = hashlib.md5(f'{fname}{mtime}'.encode()).hexdigest()
        
        if file_hash in state['processed_files']:
            continue
        
        result = parse_file(fpath)
        state['processed_files'][file_hash] = {
            'file': fname,
            'parsed_at': result['parsed_at'],
            'stocks': result['stocks'],
        }
        new_files.append(result)
    
    if new_files:
        state['last_scan'] = datetime.now().isoformat()
        save_state(state)
        return new_files
    
    return None

if __name__ == '__main__':
    results = scan()
    if results:
        for r in results:
            report = generate_report(r)
            print(report)
            print()
    else:
        print('No new files')
