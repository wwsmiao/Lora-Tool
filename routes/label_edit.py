"""
LoraTool - Label Edit Routes
Browse all images with their txt labels, edit inline with auto-save.
Supports search/replace, Baidu Translate API, pagination, and image compression.
"""
import os
import io
import base64
import random
import hashlib
import requests
from PIL import Image
from flask import Blueprint, render_template, request, jsonify
from config import IMAGE_EXTENSIONS, TEXT_EXTENSIONS, BAIDU_APPID, BAIDU_APPKEY

label_edit_bp = Blueprint('label_edit', __name__)

# --- Config ---
PAGE_SIZE = 100       # 每页最多加载图片数
MAX_IMAGE_DIM = 800   # 图片最长边像素（压缩阈值）


# =============================================================================
# 工具函数
# =============================================================================

def _compress_image_to_base64(filepath, max_dim=MAX_IMAGE_DIM):
    """压缩图片并返回 base64 data URI，失败返回 None。"""
    try:
        img = Image.open(filepath)
        # 转换为 RGB（JPEG 不支持透明通道）
        if img.mode in ('RGBA', 'LA', 'P'):
            rgb = Image.new('RGB', img.size, (255, 255, 255))
            rgb.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = rgb
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # 等比缩放
        w, h = img.size
        if max(w, h) > max_dim:
            ratio = max_dim / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

        # 编码为 JPEG
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=80, optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        return f'data:image/jpeg;base64,{b64}'
    except Exception:
        return None


def _make_items(image_path, filenames, offset=0, limit=PAGE_SIZE):
    """对 filenames[offset:offset+limit] 生成 items（含压缩图片 + txt 内容）。"""
    items = []
    for filename in filenames[offset: offset + limit]:
        filepath = os.path.join(image_path, filename)
        txt_name = os.path.splitext(filename)[0] + '.txt'
        txt_path = os.path.join(image_path, txt_name)

        # Read txt content (try utf-8, fallback gbk)
        txt_content = ''
        if os.path.exists(txt_path):
            for enc in ('utf-8', 'gbk', 'gb2312'):
                try:
                    with open(txt_path, 'r', encoding=enc) as f:
                        txt_content = f.read()
                    break
                except Exception:
                    pass

        # Compress + encode image
        img_data = _compress_image_to_base64(filepath)

        items.append({
            'filename': filename,
            'txt_name': txt_name,
            'txt_content': txt_content,
            'img_data': img_data,
        })
    return items


# =============================================================================
# 页面路由
# =============================================================================

@label_edit_bp.route('/')
def index():
    path = request.args.get('path', '')
    return render_template('label_edit.html', path=path)


# =============================================================================
# 数据加载（分页）
# =============================================================================

@label_edit_bp.route('/load', methods=['POST'])
def load():
    """
    加载指定路径下的图片列表（分页）。
    请求体: { image_path, page=1, page_size=100 }
    返回: { success, items, total, page, page_size, total_pages }
    """
    data = request.json or {}
    image_path = data.get('image_path', '').strip()
    page = max(1, int(data.get('page', 1)))
    page_size = min(300, max(10, int(data.get('page_size', PAGE_SIZE))))

    if not image_path:
        return jsonify({'success': False, 'message': '请填写路径'}), 400

    if not os.path.isdir(image_path):
        return jsonify({'success': False, 'message': f'路径不存在: {image_path}'}), 400

    sort = data.get('sort', 'name_asc')  # name_asc | name_desc | date_asc | date_desc

    images = [
        f for f in os.listdir(image_path)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
    ]

    # 自然排序 key：将文件名按"数字段 / 非数字段"交替拆分
    # - 数字段转为 int，保证 1,2,10 按数值排（而非字典序的 1,10,2）
    # - 非数字段统一小写，抹除大小写差异
    def _natural_key(name: str):
        parts = []
        i = 0
        name_lower = name.lower()
        while i < len(name_lower):
            if name_lower[i].isdigit():
                # 连续数字，转为 int
                j = i
                while j < len(name_lower) and name_lower[j].isdigit():
                    j += 1
                parts.append((0, int(name_lower[i:j])))
                i = j
            else:
                # 连续非数字（字母/汉字等），转为 str
                j = i
                while j < len(name_lower) and not name_lower[j].isdigit():
                    j += 1
                parts.append((1, name_lower[i:j]))  # 大小写已在 name_lower 中抹平
                i = j
        return parts

    # 排序策略
    if sort == 'name_desc':
        images.sort(key=_natural_key, reverse=True)
    elif sort == 'date_asc':
        images.sort(key=lambda f: os.path.getmtime(os.path.join(image_path, f)))
    elif sort == 'date_desc':
        images.sort(key=lambda f: os.path.getmtime(os.path.join(image_path, f)), reverse=True)
    else:  # name_asc（默认）
        images.sort(key=_natural_key)

    if not images:
        return jsonify({'success': False, 'message': '该路径下没有图片文件'}), 400

    total = len(images)
    total_pages = (total + page_size - 1) // page_size
    offset = (page - 1) * page_size

    items = _make_items(image_path, images, offset=offset, limit=page_size)

    return jsonify({
        'success': True,
        'items': items,
        'total': total,
        'page': page,
        'page_size': page_size,
        'total_pages': total_pages,
        'sort': sort,
        'image_path': image_path,
    })


@label_edit_bp.route('/count', methods=['POST'])
def count():
    """返回指定路径下的图片总数（不加载图片，用于快速检查）。"""
    data = request.json or {}
    image_path = data.get('image_path', '').strip()
    if not image_path or not os.path.isdir(image_path):
        return jsonify({'success': False, 'message': '无效路径'}), 400

    images = sorted([
        f for f in os.listdir(image_path)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
    ])
    return jsonify({'success': True, 'total': len(images)})


# =============================================================================
# 保存 & 翻译
# =============================================================================

@label_edit_bp.route('/save', methods=['POST'])
def save():
    """保存单个 txt 文件。"""
    data = request.json
    image_path = data.get('image_path', '').strip()
    txt_name = data.get('txt_name', '').strip()
    content = data.get('content', '')

    if not image_path or not txt_name:
        return jsonify({'success': False, 'message': '参数不完整'}), 400

    txt_path = os.path.join(image_path, txt_name)
    try:
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True, 'message': f'已保存 {txt_name}'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'保存失败: {str(e)}'}), 500


@label_edit_bp.route('/translate', methods=['POST'])
def translate():
    """翻译单条文本。"""
    data = request.json
    text = (data.get('text') or '').strip()
    direction = data.get('direction', 'zh2en')

    if not text:
        return jsonify({'success': False, 'message': '文本为空'})

    if not BAIDU_APPID or not BAIDU_APPKEY:
        return jsonify({'success': False, 'message': '翻译功能未配置'})

    salt = random.randint(32768, 65536)
    sign_str = f'{BAIDU_APPID}{text}{salt}{BAIDU_APPKEY}'
    sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()

    url = 'https://fanyi-api.baidu.com/api/trans/vip/translate'
    payload = {
        'q': text,
        'appid': BAIDU_APPID,
        'salt': salt,
        'from': 'zh' if direction == 'zh2en' else 'en',
        'to': 'en' if direction == 'zh2en' else 'zh',
        'sign': sign,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    try:
        r = requests.post(url, data=payload, headers=headers, timeout=10)
        result = r.json()
        if 'trans_result' in result and result['trans_result']:
            translated = result['trans_result'][0]['dst']
            return jsonify({'success': True, 'translated': translated})
        else:
            msg = result.get('error_msg', '翻译失败')
            return jsonify({'success': False, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': f'翻译请求异常: {str(e)}'})


# =============================================================================
# 批量操作
# =============================================================================

@label_edit_bp.route('/replace_all', methods=['POST'])
def replace_all():
    """批量查找替换。"""
    data = request.json
    image_path = data.get('image_path', '').strip()
    search_str = data.get('search_str', '')
    replace_str = data.get('replace_str', '')

    if not image_path or not search_str:
        return jsonify({'success': False, 'message': '参数不完整'}), 400

    if not os.path.isdir(image_path):
        return jsonify({'success': False, 'message': '路径不存在'}), 400

    changed = 0
    for filename in os.listdir(image_path):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in TEXT_EXTENSIONS:
            continue
        filepath = os.path.join(image_path, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            try:
                with open(filepath, 'r', encoding='gbk') as f:
                    content = f.read()
            except Exception:
                continue

        if search_str not in content:
            continue

        new_content = content.replace(search_str, replace_str)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            changed += 1
        except Exception:
            pass

    return jsonify({
        'success': True,
        'message': f'已完成，修改了 {changed} 个文件'
    })


@label_edit_bp.route('/translate_all', methods=['POST'])
def translate_all():
    """批量翻译所有 txt 文件。"""
    data = request.json
    image_path = data.get('image_path', '').strip()
    direction = data.get('direction', 'zh2en')

    if not image_path or not os.path.isdir(image_path):
        return jsonify({'success': False, 'message': '路径不存在'}), 400

    if not BAIDU_APPID or not BAIDU_APPKEY:
        return jsonify({'success': False, 'message': '翻译功能未配置'})

    changed = 0
    errors = []

    for filename in os.listdir(image_path):
        ext = os.path.splitext(filename)[1].lower()
        if ext not in TEXT_EXTENSIONS:
            continue
        filepath = os.path.join(image_path, filename)

        # Read
        content = ''
        for enc in ('utf-8', 'gbk'):
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    content = f.read()
                break
            except Exception:
                pass
        if not content.strip():
            continue

        # Translate
        salt = random.randint(32768, 65536)
        sign_str = f'{BAIDU_APPID}{content}{salt}{BAIDU_APPKEY}'
        sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()

        url = 'https://fanyi-api.baidu.com/api/trans/vip/translate'
        payload = {
            'q': content,
            'appid': BAIDU_APPID,
            'salt': salt,
            'from': 'zh' if direction == 'zh2en' else 'en',
            'to': 'en' if direction == 'zh2en' else 'zh',
            'sign': sign,
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        try:
            r = requests.post(url, data=payload, headers=headers, timeout=15)
            result = r.json()
            if 'trans_result' in result and result['trans_result']:
                translated = result['trans_result'][0]['dst']
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(translated)
                changed += 1
            else:
                errors.append(f'{filename}: {result.get("error_msg", "未知错误")}')
        except Exception as e:
            errors.append(f'{filename}: {str(e)}')

    msg = f'翻译完成，成功 {changed} 个'
    if errors:
        msg += f'，失败 {len(errors)} 个'
    return jsonify({'success': True, 'message': msg})
