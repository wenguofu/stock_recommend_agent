# tests/test_hot_sectors.py
import json
import os
import sys
sys.path.insert(0, '/Users/wgfu/work/a-stock-trading')

def test_hot_sector_manager_load():
    """Test HotSectorManager loads from json"""
    from screening.hot_sector_manager import HotSectorManager
    mgr = HotSectorManager()
    sectors = mgr.get_current_sectors()
    assert isinstance(sectors, list)
    assert len(sectors) > 0


def test_hot_sector_manager_update():
    """Test weekly update function exists"""
    from screening.hot_sector_manager import HotSectorManager
    mgr = HotSectorManager()
    assert hasattr(mgr, 'update_weekly')