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

# ── About Page ──────────────────────────────────────────────
SOFTWARE_VERSION = 'v1.0.0'
SOFTWARE_DATE    = '2026.6.14'
AUTHOR_NAME      = '薇薇的猫/qclaw'
AUTHOR_PLATFORM  = '薇薇的猫'
AUTHOR_BILIBILI   = 'https://space.bilibili.com/472768517'
SOFTWARE_DESC    = (
    'LoraTool 是一款面向 AI 图像训练与标注的本地工具集，'
    '支持 Qwen3-VL / Qwen3.5 多模型本地推理标注、Ollama API 标注，'
    '集成人脸检测分割、图片批量重命名/尺寸调整、标注文本编辑与批量翻译，'
    '以及字符串批量替换等辅助功能。全程本地运行，数据安全不外泄。'
)
