"""
LoraTool - Configuration
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB

# Supported image extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp'}

# Supported text extensions
TEXT_EXTENSIONS = {'.txt', '.text', '.caption'}

# ── Baidu Translate API Config ──────────────────────────
# 优先级：环境变量 > baidu_translate_config.json
# 将 appid/appkey 写入 baidu_translate_config.json

def _load_baidu_config():
    """从 baidu_translate_config.json 加载翻译 API 配置，失败返回空字典。"""
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'baidu_translate_config.json')
    try:
        import json as _json
        with open(cfg_path, 'r', encoding='utf-8') as f:
            return _json.load(f)
    except Exception:
        return {}

_baidu_cfg = _load_baidu_config()

BAIDU_APPID = os.environ.get('BAIDU_APPID') or _baidu_cfg.get('appid', '')
BAIDU_APPKEY = os.environ.get('BAIDU_APPKEY') or _baidu_cfg.get('appkey', '')
