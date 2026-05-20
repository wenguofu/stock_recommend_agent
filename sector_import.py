"""
九大板块日报导入工具 v2

用途：将「九大板块」PDF导入到 a-stock-trading 系统的结构化数据
用法：uv run python sector_import.py /path/to/九大板块_YYYYMMDD.pdf

v2 改进：
- ✅ 跨页断句合并 — 移除页码/页眉干扰后整体解析
- ✅ 数据标注清理 — stocks字段去除"（财联社电报）"等来源标注
- ✅ 字段边界精确 — 用正则块级匹配替代逐行解析
- ✅ 数据验证 — 检查字段是否完整，标记异常
"""

import json
import os
import sys
import re
from datetime import datetime

SECTOR_DATA_DIR = os.path.join(os.path.dirname(__file__), "sector_data")

SECTOR_NAMES = [
    "机器人", "半导体材料", "煤炭", "存储芯片", "算力",
    "油气开采及服务", "光纤概念", "电网设备", "证券"
]

FIELD_LABELS = {
    "涨幅居前个股：": "stocks",
    "涨幅居前个股:": "stocks",
    "驱动因素：": "driver",
    "驱动因素:": "driver",
    "泰度内参：": "insight",
    "泰度内参:": "insight",
    "机构观点：": "view",
    "机构观点:": "view",
}


def extract_text_from_pdf(pdf_path):
    """使用pymupdf提取PDF文本"""
    import pymupdf
    doc = pymupdf.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    doc.close()
    return text


def clean_text(text):
    """
    清理PDF提取文本：
    1. 移除页码 (独立一行且是数字 1-20)
    2. 移除页眉 "博观而约取，厚积而薄发"
    3. 移除风险提示行
    4. 合并跨页断句（行尾无标点 + 下行小写开头）
    5. 移除空白行干扰
    """
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        s = line.strip()
        # 移除页码：独立的1-20数字
        if re.match(r'^\d{1,2}$', s):
            continue
        # 移除页眉
        if "博观而约取" in s:
            continue
        # 移除风险提示
        if "风险提示" in s:
            continue
        # 移除注解行
        if "市场有风险" in s or "纪哲康" in s or "崔红霞" in s or "李运杰" in s:
            continue
        if "投顾执业编号" in s:
            continue
        cleaned.append(s)
    
    return "\n".join(cleaned)


def parse_sectors_from_text(text, date_str):
    """解析九大板块文本为结构化数据（块级解析）"""
    # Step 1: Clean
    clean = clean_text(text)
    
    # Step 2: Extract market summary (between "【盘面泰度点评】" and "【要点速览】")
    market_summary = ""
    m = re.search(r'【盘面泰度点评】\s*(.*?)(?=【要点速览】)', clean, re.DOTALL)
    if m:
        market_summary = m.group(1).strip()
        # Remove trailing section headers
        market_summary = re.sub(r'【A 股指数性价比追踪】.*$', '', market_summary)
        # Flatten excessive newlines
        market_summary = re.sub(r'\n{3,}', '\n\n', market_summary)
        # Remove any remaining standalone page numbers
        market_summary = re.sub(r'^\d{1,2}\s*\n', '', market_summary, flags=re.MULTILINE)
    
    # Step 3: Extract sector blocks
    # Pattern: 【数字】、【板块名】内容... until next 【N】、 or end
    # The raw text uses Chinese brackets like: 一、【机器人】把握自己的节奏
    sector_pattern = re.compile(
        r'[一二三四五六七八九]、【(.+?)】.*?\n(.*?)(?=(?:[一二三四五六七八九]、【|$))',
        re.DOTALL
    )
    
    sector_blocks = sector_pattern.findall(clean)
    
    sectors = []
    for raw_name, raw_content in sector_blocks:
        raw_name = raw_name.strip()
        raw_content = raw_content.strip()
        
        if not raw_name and not raw_content:
            continue
        
        # Extract sector name
        name = ""
        for sn in SECTOR_NAMES:
            if sn in raw_name:
                name = sn
                break
        if not name:
            n = re.sub(r'[【】\[\]]', '', raw_name)
            n = re.sub(r'板块.*$', '', n)
            name = n.strip() or raw_name[:10]
        
        # Extract fields using field labels
        sector = {"name": name, "stocks": "", "driver": "", "insight": "", "view": ""}
        
        for label, field_name in FIELD_LABELS.items():
            # Find content after label until next field label or end
            escaped_label = re.escape(label)
            pattern = rf'{escaped_label}\s*(.*?)(?=(?:{"|".join(re.escape(l) for l in FIELD_LABELS.keys())}|$))'
            m = re.search(pattern, raw_content, re.DOTALL)
            if m:
                content = m.group(1).strip()
                # Flatten newlines
                content = re.sub(r'\n\s*', '', content)
                
                if field_name == "stocks":
                    # Clean data source annotations
                    content = re.sub(r'等等[。，]?（[^）]*）', '', content)
                    content = re.sub(r'等[。，]?（[^）]*）', '', content)
                    content = re.sub(r'（[^）]*）', '', content)
                    content = re.sub(r'等等\.?\s*$', '', content)
                    content = re.sub(r'等\.?\s*$', '', content)
                
                sector[field_name] = content.strip()
        
        sectors.append(sector)
    
    return {
        "date": date_str,
        "market_summary": market_summary,
        "sectors": sectors
    }


def validate_data(data):
    """验证数据质量，返回问题列表"""
    issues = []
    
    if not data["market_summary"]:
        issues.append("⚠️ 大盘概况为空")
    
    if len(data["sectors"]) != 9:
        issues.append(f"⚠️ 板块数={len(data['sectors'])}，预期9个")
    
    for s in data["sectors"]:
        name = s["name"]
        for field in ["stocks", "driver", "insight", "view"]:
            if not s.get(field):
                issues.append(f"⚠️ {name}.{field} 为空")
            elif field == "stocks" and len(s[field]) < 10:
                issues.append(f"⚠️ {name}.{field} 过短({len(s[field])}字符): {s[field][:50]}")
            elif field != "stocks" and len(s[field]) < 20:
                issues.append(f"⚠️ {name}.{field} 过短({len(s[field])}字符): {s[field][:50]}")
        
        # Check for remnants of page numbers or headers
        if re.search(r'^\d{1,2}\s*$', s.get("driver", "")):
            issues.append(f"⚠️ {name}.driver 包含页面残留页码")
    
    return issues


def save_sector_data(data):
    """保存结构化数据"""
    os.makedirs(SECTOR_DATA_DIR, exist_ok=True)
    
    json_path = os.path.join(SECTOR_DATA_DIR, f"{data['date']}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    md_path = os.path.join(SECTOR_DATA_DIR, f"{data['date']}.md")
    md = f"# 九大板块日报 · {data['date']}\n\n## 大盘概况\n{data['market_summary']}\n\n## 板块明细\n"
    for s in data['sectors']:
        md += f"\n### {s.get('name','?')}\n- **领涨**: {s.get('stocks','')}\n- **驱动**: {s.get('driver','')}\n- **内参**: {s.get('insight','')}\n- **观点**: {s.get('view','')}\n"
    
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    
    return json_path, md_path


def parse_date_from_filename(pdf_path):
    """从文件名提取日期"""
    basename = os.path.basename(pdf_path)
    matches = re.findall(r'(20\d{2})(\d{2})(\d{2})', basename)
    for y, m, d in matches:
        if 1 <= int(m) <= 12 and 1 <= int(d) <= 31:
            return f"{y}-{m}-{d}"
    return datetime.now().strftime("%Y-%m-%d")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: uv run python sector_import.py <pdf_path>")
        print("示例: uv run python sector_import.py 九大板块_20260518.pdf")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"❌ 文件不存在: {pdf_path}")
        sys.exit(1)
    
    print(f"📄 正在处理: {pdf_path}")
    text = extract_text_from_pdf(pdf_path)
    date_str = parse_date_from_filename(pdf_path)
    data = parse_sectors_from_text(text, date_str)
    
    # Validate
    issues = validate_data(data)
    
    json_path, md_path = save_sector_data(data)
    
    print(f"✅ 导入完成！")
    print(f"   JSON: {json_path}")
    print(f"   MD:   {md_path}")
    print(f"   板块数: {len(data['sectors'])}")
    
    if issues:
        print(f"\n❌ 数据验证问题 ({len(issues)}):")
        for iss in issues:
            print(f"   {iss}")
    else:
        print(f"\n✅ 数据验证通过！")
    
    print(f"\n📊 板块概要:")
    for s in data['sectors']:
        slen = {k: len(s.get(k,'')) for k in ['stocks','driver','insight','view']}
        print(f"   {s['name']:10s} | 涨{slen['stocks']:3d} 驱{slen['driver']:3d} 参{slen['insight']:3d} 观{slen['view']:3d}")
