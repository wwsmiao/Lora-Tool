# -*- mode: python ; coding: utf-8 -*-
import sys

block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('routes', 'routes'),
        ('config.py', '.'),
        ('config_loader.py', '.'),
        ('db_config.py', '.'),
        ('prompts', 'prompts'),
        ('ollama_config.json', '.'),
        ('baidu_translate_config.json', '.'),
    ],
    hiddenimports=[
        'flask', 'pymysql', 'cryptography', 'werkzeug', 
        'cv2', 'PIL', 'requests', 'facenet_pytorch'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['venv', '__pycache__', '*.pyc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='LoraTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 保留控制台窗口以便查看日志
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
