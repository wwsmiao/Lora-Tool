"""
LoraTool - Batch Rename Routes
"""
import os
import shutil
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify

rename_bp = Blueprint('rename', __name__)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp'}


@rename_bp.route('/')
def index():
    return render_template('rename.html', active_page='rename')


@rename_bp.route('/process', methods=['POST'])
def process():
    data = request.json
    image_path = data.get('image_path', '').strip()
    mode = data.get('mode', '1')
    prefix = data.get('prefix', '').strip()
    suffix = data.get('suffix', '').strip()

    if not image_path:
        return jsonify({'success': False, 'message': '请填写图片路径'})

    if not os.path.isdir(image_path):
        return jsonify({'success': False, 'message': f'路径不存在: {image_path}'})

    images = sorted([
        f for f in os.listdir(image_path)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
    ])

    if not images:
        return jsonify({'success': False, 'message': '该路径下没有图片文件'})

    date_str = datetime.now().strftime('%Y%m%d')
    results = []
    # Use a temp prefix to avoid conflicts during renaming
    temp_prefix = '__tmp_rename_'

    # Pass 1: rename to temp names
    for idx, filename in enumerate(images, 1):
        old_path = os.path.join(image_path, filename)
        temp_path = os.path.join(image_path, f"{temp_prefix}{idx:04d}{os.path.splitext(filename)[1]}")
        os.rename(old_path, temp_path)

    # Pass 2: rename from temp names to final names
    for idx in range(1, len(images) + 1):
        ext = None
        for e in IMAGE_EXTENSIONS:
            tp = os.path.join(image_path, f"{temp_prefix}{idx:04d}{e}")
            if os.path.exists(tp):
                ext = e
                temp_path = tp
                break
        if not ext:
            continue

        if mode == '1':
            new_name = f"{idx}{ext}"
        elif mode == '2':
            new_name = f"{date_str}-{idx}{ext}"
        elif mode == '3':
            new_name = f"{prefix}{idx}{ext}"
        elif mode == '4':
            new_name = f"{idx}{suffix}{ext}"
        elif mode == '5':
            new_name = f"{prefix}{idx}{suffix}{ext}"
        else:
            new_name = f"{idx}{ext}"

        # Find original name for display
        original_name = images[idx - 1]
        new_path = os.path.join(image_path, new_name)
        os.rename(temp_path, new_path)
        results.append(f"  {original_name} → {new_name}")

    summary = (
        f"═══ 重命名完成 ═══\n"
        f"路径: {image_path}\n"
        f"模式: {mode}\n"
        f"总数量: {len(images)}\n\n"
    )
    results.insert(0, summary)

    return jsonify({
        'success': True,
        'message': '\n'.join(results),
        'total': len(images)
    })
