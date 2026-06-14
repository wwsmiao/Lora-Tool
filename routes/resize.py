"""
LoraTool - Image Resize Routes (OpenCV read + PIL write, parallelized)
"""
import os
import cv2
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from flask import Blueprint, render_template, request, jsonify

resize_bp = Blueprint('resize', __name__)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp'}
MAX_WORKERS = 8

# cv2.imread with Unicode support
def imread(path):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def _resize_one(src, dst, target_w, target_h, mode):
    img = imread(src)
    if img is None:
        return False, "read failed"
    orig_h, orig_w = img.shape[:2]

    if target_w > 0 and target_h > 0:
        if mode == 'exact':
            new_w, new_h = target_w, target_h
        elif mode == 'fill':
            ratio = max(target_w / orig_w, target_h / orig_h)
            new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
        else:  # fit
            ratio = min(target_w / orig_w, target_h / orig_h)
            new_w, new_h = int(orig_w * ratio), int(orig_h * ratio)
    elif target_w > 0:
        ratio = target_w / orig_w
        new_w, new_h = target_w, int(orig_h * ratio)
    else:
        ratio = target_h / orig_h
        new_w, new_h = int(orig_w * ratio), target_h

    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    # cv2 BGR->RGB via PIL (PIL supports Unicode paths natively)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    ext = os.path.splitext(dst)[1].lower()
    if ext in ('.jpg', '.jpeg'):
        pil_img.save(dst, 'JPEG', quality=95)
    else:
        pil_img.save(dst)
    return True, f"{orig_w}x{orig_h} -> {new_w}x{new_h}"


@resize_bp.route('/')
def index():
    return render_template('resize.html', active_page='resize')


@resize_bp.route('/process', methods=['POST'])
def process():
    data = request.json
    image_path = data.get('image_path', '').strip()
    width = data.get('width', '0')
    height = data.get('height', '0')
    mode = data.get('mode', 'fit')
    output_path = data.get('output_path', '').strip()

    if not image_path:
        return jsonify({'success': False, 'message': '请填写图片路径'})

    if not os.path.isdir(image_path):
        return jsonify({'success': False, 'message': f'路径不存在: {image_path}'})

    try:
        target_w = int(width) if width else 0
        target_h = int(height) if height else 0
    except ValueError:
        return jsonify({'success': False, 'message': '宽度和高度必须是数字'})

    if target_w <= 0 and target_h <= 0:
        return jsonify({'success': False, 'message': '至少填写一个尺寸'})

    if not output_path:
        output_path = image_path
    else:
        os.makedirs(output_path, exist_ok=True)

    images = sorted([
        f for f in os.listdir(image_path)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
    ])

    if not images:
        return jsonify({'success': False, 'message': '该路径下没有图片文件'})

    results = []
    total = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for filename in images:
            src = os.path.join(image_path, filename)
            dst = os.path.join(output_path, filename)
            futures[executor.submit(_resize_one, src, dst, target_w, target_h, mode)] = filename

        for future in as_completed(futures):
            filename = futures[future]
            ok, msg = future.result()
            if ok:
                total += 1
                results.append(f"  OK {filename}: {msg}")
            else:
                results.append(f"  FAIL {filename}: {msg}")

    summary = (
        f"===== Size Adjust Done =====\n"
        f"Input: {image_path}\n"
        f"Output: {output_path}\n"
        f"Target: {target_w if target_w else 'auto'} x {target_h if target_h else 'auto'}\n"
        f"Mode: {mode}\n"
        f"Processed: {total}/{len(images)}\n"
    )
    results.insert(0, summary)

    return jsonify({'success': True, 'message': '\n'.join(results), 'total': total})
