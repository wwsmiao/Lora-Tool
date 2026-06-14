"""
LoraTool - Face Split Routes
Detect faces in images and crop them using MTCNN (facenet-pytorch).
"""
import os
import sys
import cv2
import numpy as np
from PIL import Image
from flask import Blueprint, render_template, request, jsonify, Response

face_split_bp = Blueprint('face_split', __name__)

# Global detector singleton
_detector = None

def _get_facenet_data_dir():
    """Resolve facenet_pytorch/data directory, works in PyInstaller bundle."""
    import facenet_pytorch
    import sys
    # In PyInstaller bundle, data files are extracted alongside the module
    # Try multiple resolution strategies
    candidates = []
    # 1) sys._MEIPASS (PyInstaller COLLECT mode root)
    if getattr(sys, '_MEIPASS', None):
        candidates.append(os.path.join(sys._MEIPASS, 'facenet_pytorch', 'data'))
    # 2) __file__ relative (works in normal Python)
    pkg_dir = os.path.dirname(facenet_pytorch.__file__)
    candidates.append(os.path.join(pkg_dir, 'data'))
    # 3) Look relative to this file's parent
    candidates.append(os.path.join(os.path.dirname(__file__), '..', 'facenet_pytorch', 'data'))
    for cand in candidates:
        if os.path.isdir(cand):
            return cand
    # Fallback: try to find onet.pt anywhere under MEIPASS
    if getattr(sys, '_MEIPASS', None):
        for root, dirs, files in os.walk(sys._MEIPASS):
            if 'onet.pt' in files:
                return root
    return candidates[1]  # best-effort fallback

def _patch_mtcnn_state_dict_paths():
    """Patch MTCNN sub-networks so they find model files in PyInstaller bundle."""
    import sys
    from facenet_pytorch.models import mtcnn
    data_dir = _get_facenet_data_dir()
    # Override the class-level state_dict_path
    mtcnn.PNet.state_dict_path = os.path.join(data_dir, 'pnet.pt')
    mtcnn.RNet.state_dict_path = os.path.join(data_dir, 'rnet.pt')
    mtcnn.ONet.state_dict_path = os.path.join(data_dir, 'onet.pt')
    # Also patch any already-cached versions in sys.modules
    for mod_name in list(sys.modules.keys()):
        if 'mtcnn' in mod_name.lower():
            mod = sys.modules[mod_name]
            if hasattr(mod, 'PNet'):
                mod.PNet.state_dict_path = mtcnn.PNet.state_dict_path
            if hasattr(mod, 'RNet'):
                mod.RNet.state_dict_path = mtcnn.RNet.state_dict_path
            if hasattr(mod, 'ONet'):
                mod.ONet.state_dict_path = mtcnn.ONet.state_dict_path


def get_detector():
    """Lazy-init MTCNN detector (singleton, GPU preferred)."""
    global _detector
    if _detector is None:
        import torch, sys
        # Patch model file paths before importing facenet_pytorch
        _patch_mtcnn_state_dict_paths()
        from facenet_pytorch import MTCNN
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        _detector = MTCNN(
            image_size=160,
            margin=20,
            min_face_size=20,
            thresholds=[0.6, 0.7, 0.7],
            factor=0.709,
            post_process=True,
            keep_all=True,
            device=device,
        )
    return _detector


def pil_imread(filepath):
    """Read image using PIL (supports Unicode/Chinese paths)."""
    pil_img = Image.open(filepath)
    if pil_img.mode not in ('RGB', 'RGBA'):
        pil_img = pil_img.convert('RGB')
    if pil_img.mode == 'RGBA':
        bg = Image.new('RGB', pil_img.size, (255, 255, 255))
        bg.paste(pil_img, mask=pil_img.split()[3])
        pil_img = bg
    return pil_img


def pil_imwrite(filepath, pil_img):
    """Save image using PIL (supports Unicode/Chinese paths)."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ('.jpg', '.jpeg'):
        pil_img.save(filepath, 'JPEG', quality=95)
    else:
        pil_img.save(filepath)


@face_split_bp.route('/')
def index():
    return render_template('face_split.html', active_page='face_split')


@face_split_bp.route('/process', methods=['POST'])
def process():
    data = request.json
    image_path = data.get('image_path', '').strip()
    face_size_raw = data.get('face_size', '512')
    output_path = data.get('output_path', '').strip()
    min_confidence_raw = data.get('min_confidence', 0.5)

    # ── 参数校验 ──────────────────────────────────────────
    if not image_path or not output_path:
        return jsonify({'success': False, 'message': '请填写图片路径和输出路径'})

    try:
        face_size = int(face_size_raw)
    except ValueError:
        return jsonify({'success': False, 'message': '人脸尺寸必须是数字'})

    try:
        min_confidence = float(min_confidence_raw)
        min_confidence = max(0.1, min(1.0, min_confidence))
    except ValueError:
        min_confidence = 0.5

    if not os.path.isdir(image_path):
        return jsonify({'success': False, 'message': f'图片路径不存在: {image_path}'})

    os.makedirs(output_path, exist_ok=True)

    img_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}

    try:
        detector = get_detector()
    except Exception as e:
        return jsonify({'success': False, 'message': f'无法加载MTCNN模型: {e}'})

    # ── 收集所有待处理文件 ────────────────────────────────
    all_files = sorted([
        f for f in os.listdir(image_path)
        if os.path.splitext(f)[1].lower() in img_exts
    ])
    total_images = len(all_files)

    if total_images == 0:
        return jsonify({'success': False, 'message': '该路径下没有图片文件'})

    stats = {'total_faces': 0, 'failed_images': []}

    # ── 流式生成器 ──────────────────────────────────────

    def generate():
        from flask import make_response, Response as FlaskResponse
        from PIL import ImageEnhance

        # 首行：总图片数（前端据此计算百分比）
        yield f"__total__:{total_images}\n"

        for idx, filename in enumerate(all_files):
            filepath = os.path.join(image_path, filename)
            line = None  # 当前图片的最终结果行

            try:
                pil_img = pil_imread(filepath)
            except Exception as e:
                line = f'❌ {filename}: 无法读取图片 ({e})'
                stats['failed_images'].append(filename)
                yield f"{idx + 1}|{line}\n"
                continue

            try:
                boxes, probs = detector.detect(pil_img)
            except Exception as e:
                line = f'❌ {filename}: 检测出错 ({e})'
                stats['failed_images'].append(filename)
                yield f"{idx + 1}|{line}\n"
                continue

            if boxes is None or len(boxes) == 0:
                line = f'⏭️ {filename}: 未检测到人脸'
                stats['failed_images'].append(filename)
                yield f"{idx + 1}|{line}\n"
                continue

            valid_indices = []
            confidences = []
            for i, p in enumerate(probs):
                if p is not None and p >= min_confidence:
                    valid_indices.append(i)
                    confidences.append(float(p))

            if len(valid_indices) == 0:
                line = f'⏭️ {filename}: 置信度低于阈值 {min_confidence}'
                stats['failed_images'].append(filename)
                yield f"{idx + 1}|{line}\n"
                continue

            name_no_ext = os.path.splitext(filename)[0]
            saved = []
            for rank, i in enumerate(valid_indices):
                x1, y1, x2, y2 = [int(v) for v in boxes[i]]
                w, h = x2 - x1, y2 - y1

                # 正方形裁剪（无黑边）
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                side = int(max(w, h) * 1.1)
                half = side // 2
                sq_x1 = max(0, center_x - half)
                sq_y1 = max(0, center_y - half)
                sq_x2 = min(pil_img.width, sq_x1 + side)
                sq_y2 = min(pil_img.height, sq_y1 + side)
                if sq_x2 - sq_x1 < side:
                    sq_x1 = max(0, sq_x2 - side)
                if sq_y2 - sq_y1 < side:
                    sq_y1 = max(0, sq_y2 - side)

                face_crop = pil_img.crop((sq_x1, sq_y1, sq_x2, sq_y2))

                # 锐化增强
                enhancer = ImageEnhance.Sharpness(face_crop)
                face_crop = enhancer.enhance(1.5)

                face_resized = face_crop.resize((face_size, face_size), Image.LANCZOS)
                save_name = f"{name_no_ext}_face{rank + 1}.jpg"
                save_path = os.path.join(output_path, save_name)
                pil_imwrite(save_path, face_resized)
                saved.append(save_name)

            face_count = len(valid_indices)
            stats['total_faces'] += face_count
            conf_min = min(confidences)
            conf_max = max(confidences)
            line = (f'✅ {filename}: 检测到 {face_count} 张人脸 '
                    f'(置信度 {conf_min:.2f}~{conf_max:.2f})')
            yield f"{idx + 1}|{line}\n"

        # 最后一行：汇总
        summary = (f"═══ 处理完成 ═══\n"
                   f"总图片: {total_images} 张 | 提取人脸: {stats['total_faces']} 张\n"
                   f"输出目录: {output_path}")
        _tf = stats['total_faces']
        _tf = stats['total_faces']
        yield f'__done__|{_tf}|{total_images}|{summary}' + chr(10)
    return Response(
        generate(),
        mimetype='text/plain',
        headers={
            'X-Accel-Buffering': 'no',
            'Cache-Control': 'no-cache',
        }
    )
