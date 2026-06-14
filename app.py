# -*- coding: utf-8 -*-
"""
LoraTool - Flask Web Application
Main entry point
"""
import sys, os
from datetime import datetime
import traceback

# 确保工作目录正确 - 支持环境变量（打包后动态获取）
WORK_DIR = os.environ.get('LORATOOL_WORK_DIR', os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(WORK_DIR, 'debug.log')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, session, request, jsonify, redirect, url_for, make_response, render_template
from main import register_routes
from config_loader import load_db_config
import pymysql

app = Flask(__name__, template_folder='templates', static_folder='static')

from config import UPLOAD_FOLDER, MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# ── Auth Config ────────────────────────────────────────────
# SECRET_KEY 优先从环境变量读取，否则使用随机生成值（每次启动不同）
import secrets
app.config['SECRET_KEY'] = os.environ.get(
    'LORATOOL_SECRET_KEY',
    'LoraTool-' + secrets.token_hex(32)
)
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30  # 30 days

# ── JSON Encoding ─────────────────────────────────────────
app.config['JSON_AS_ASCII'] = False  # 允许中文等非ASCII字符
app.config['JSON_ENSURE_ASCII'] = False


# ── 移除所有登录和VIP检查 ──────────────────────────────
# 所有功能现在完全开放，无需登录或VIP

# Register blueprints
register_routes(app)


@app.route('/')
def home():
    return redirect('/about/')


if __name__ == '__main__':
    os.makedirs('static/uploads', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    app.run(debug=False, threaded=True, host='0.0.0.0', port=5000)
