# -*- coding: utf-8 -*-
"""数据库配置加载器"""
from db_config import DB_CONFIG

_db_cfg_cache = None

def load_db_config():
    global _db_cfg_cache
    if _db_cfg_cache is not None:
        return _db_cfg_cache
    _db_cfg_cache = DB_CONFIG.copy()
    return _db_cfg_cache
