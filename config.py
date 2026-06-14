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
# 从环境变量或 .env 文件读取（优先级：环境变量 > .env 文件）
# 请勿在此硬编码密钥

def _load_env_file():
    """加载项目根目录的 .env 文件（若存在）。"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, val = line.partition('=')
                    key, val = key.strip(), val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val
    except FileNotFoundError:
        pass

_load_env_file()

BAIDU_APPID = os.environ.get('BAIDU_APPID', '')
BAIDU_APPKEY = os.environ.get('BAIDU_APPKEY', '')

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
