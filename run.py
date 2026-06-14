# -*- coding: utf-8 -*-
"""
LoraTool - PyInstaller 入口脚本
打包命令: pyinstaller LoraTool.spec
"""
import sys
import os
import webbrowser
import time
import socket

# 确保工作目录正确
WORK_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(WORK_DIR)
sys.path.insert(0, WORK_DIR)

# 设置环境变量（覆盖 app.py 中的硬编码路径）
os.environ['LORATOOL_WORK_DIR'] = WORK_DIR

# ── 打包模式下使用独立固定密钥，与开发环境 session 隔离 ─────
# 打包后用固定密钥，这样之前登录过的用户 session 会保留
# 与开发环境密钥不同，所以开发时的 session 不会带入打包版本
if getattr(sys, 'frozen', False):
    os.environ['LORATOOL_SESSION_KEY'] = 'LoraTool-Pkg-2026-04-17-SessionKey'

from app import app

# ── 打包模式下替换 SECRET_KEY ────────────────────────────────
if getattr(sys, 'frozen', False) and 'LORATOOL_SESSION_KEY' in os.environ:
    app.secret_key = os.environ['LORATOOL_SESSION_KEY']

def wait_for_port(port, host='127.0.0.1', timeout=30):
    """等待端口可用"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                return True
        except:
            pass
        time.sleep(0.3)
    return False

def open_browser_when_ready(port=5000):
    """等待端口就绪后打开浏览器"""
    if wait_for_port(port):
        time.sleep(0.5)  # 额外等待确保服务完全就绪
        webbrowser.open(f'http://127.0.0.1:{port}')
    else:
        print(f"[WARN] 等待端口 {port} 超时，请手动打开浏览器访问 http://127.0.0.1:{port}")

if __name__ == '__main__':
    os.makedirs(os.path.join(WORK_DIR, 'static', 'uploads'), exist_ok=True)

    # 启动后台线程等待端口就绪后打开浏览器
    import threading
    threading.Thread(target=open_browser_when_ready, daemon=True).start()

    print("\n" + "="*50)
    print("  LoraTool 启动中...")
    print("  访问地址: http://127.0.0.1:5000")
    print("  按 Ctrl+C 停止服务")
    print("="*50 + "\n")

    app.run(debug=False, threaded=True, host='0.0.0.0', port=5000)
