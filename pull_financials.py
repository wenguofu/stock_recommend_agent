#!/usr/bin/env python3
"""拉取自选股财报数据到DB"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

from fundamental_data import fetch_and_cache

watchlist = ['300433', '300259', '300136', '300679', '600150', '002407', '301696', '002436', '600487']

for code in watchlist:
    try:
        result = fetch_and_cache(code)
        if result:
            print(f"{code}: ✅ ROE={result.get('roe')} GM={result.get('gross_margin')} PE={result.get('pe_ttm')}")
        else:
            print(f"{code}: ❌ API返回空")
    except Exception as e:
        logger.error(f"{code}: ❌ {str(e)[:120]}", exc_info=False)
