"""
LoraTool - Aliyun API Labeling Routes
Use Alibaba Cloud (DashScope) API for image captioning/labeling.
"""
import os
import json
import base64
import time
import requests
from flask import Blueprint, render_template, request, jsonify

aliyun_label_bp = Blueprint('aliyun_label', __name__)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp'}

# Config file path (in project root)
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'aliyun_config.json')

# Templates folder
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'prompt_templates')


def load_config():
    """Load saved config (API key, etc.)"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_config(data):
    """Save config to file"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@aliyun_label_bp.route('/')
def index():
    return render_template('aliyun_label.html', active_page='aliyun_label')


@aliyun_label_bp.route('/get_config', methods=['GET'])
def get_config():
    """Get saved API key config"""
    cfg = load_config()
    # Return masked API key for display
    api_key = cfg.get('api_key', '')
    masked = api_key[:8] + '****' + api_key[-4:] if len(api_key) > 12 else ''
    return jsonify({
        'success': True,
        'api_key_masked': masked,
        'api_key_saved': bool(api_key),
        'last_model': cfg.get('last_model', 'qwen3.5-plus'),
        'last_chufaci': cfg.get('last_chufaci', ''),
        'last_template': cfg.get('last_template', ''),
        'last_prompt': cfg.get('last_prompt', '')
    })


@aliyun_label_bp.route('/save_config', methods=['POST'])
def save_config_route():
    """Save API key config"""
    data = request.json
    api_key = data.get('api_key', '').strip()
    model = data.get('model', 'qwen3.5-plus')
    chufaci = data.get('chufaci', '')
    template_file = data.get('template_file', '')
    prompt = data.get('prompt', '')

    cfg = load_config()
    if api_key:
        cfg['api_key'] = api_key
    cfg['last_model'] = model
    cfg['last_chufaci'] = chufaci
    if template_file:
        cfg['last_template'] = template_file
    if prompt:
        cfg['last_prompt'] = prompt
    save_config(cfg)

    return jsonify({'success': True, 'message': '配置已保存'})


@aliyun_label_bp.route('/list_templates', methods=['GET'])
def list_templates():
    """List available prompt templates"""
    templates = []
    if os.path.isdir(TEMPLATES_DIR):
        for f in sorted(os.listdir(TEMPLATES_DIR)):
            if f.endswith('.json'):
                filepath = os.path.join(TEMPLATES_DIR, f)
                try:
                    with open(filepath, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                    templates.append({
                        'filename': f,
                        'name': data.get('name', f)
                    })
                except:
                    pass
    return jsonify({'success': True, 'templates': templates})


@aliyun_label_bp.route('/load_template', methods=['POST'])
def load_template():
    """Load a specific template content"""
    data = request.json
    filename = data.get('filename', '')
    if not filename:
        return jsonify({'success': False, 'message': '未指定模板文件'})

    filepath = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'message': '模板文件不存在'})

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tmpl = json.load(f)
        return jsonify({
            'success': True,
            'name': tmpl.get('name', ''),
            'prompt_text': tmpl.get('prompt_text', '')
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'读取模板失败: {e}'})


@aliyun_label_bp.route('/process', methods=['POST'])
def process():
    """
    Process images using Aliyun DashScope API (Qwen3.5 series).
    """
    data = request.json
    image_path = data.get('image_path', '').strip()
    api_key = data.get('api_key', '').strip()
    model_name = data.get('model_name', 'qwen3.5-plus').strip()
    prompt = data.get('prompt', '').strip()
    chufaci = data.get('chufaci', '').strip()

    if not image_path:
        return jsonify({'success': False, 'message': '请填写图片路径'})

    # If no API key provided by frontend, try to load from saved config
    if not api_key:
        saved_cfg = load_config()
        api_key = saved_cfg.get('api_key', '')
    if not api_key:
        return jsonify({'success': False, 'message': '请先在上方配置并保存 API Key'})

    if not os.path.isdir(image_path):
        return jsonify({'success': False, 'message': f'路径不存在: {image_path}'})

    if not prompt:
        prompt = '请用简短的文字描述这张图片的内容，用于训练AI模型，只输出描述文字。'

    # Replace {chufaci} placeholder in prompt
    if chufaci:
        prompt = prompt.replace('{chufaci}', chufaci)

    images = sorted([
        f for f in os.listdir(image_path)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
    ])

    if not images:
        return jsonify({'success': False, 'message': '该路径下没有图片文件'})

    results = []
    total = 0
    errors = 0

    for idx, filename in enumerate(images, 1):
        filepath = os.path.join(image_path, filename)
        txt_name = os.path.splitext(filename)[0] + '.txt'
        txt_path = os.path.join(image_path, txt_name)

        # Skip if txt already exists
        if os.path.exists(txt_path):
            results.append(f"  ⏭️ [{idx}/{len(images)}] {filename}: txt已存在，跳过")
            total += 1
            continue

        try:
            with open(filepath, 'rb') as f:
                img_b64 = base64.b64encode(f.read()).decode('utf-8')

            ext = os.path.splitext(filename)[1].lower()
            mime_map = {
                '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.png': 'image/png', '.gif': 'image/gif',
                '.bmp': 'image/bmp', '.webp': 'image/webp'
            }
            mime = mime_map.get(ext, 'image/jpeg')

            # DashScope API call
            url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}}
                        ]
                    }
                ]
            }

            response = requests.post(url, json=payload, headers=headers, timeout=60)
            resp_data = response.json()

            if response.status_code == 200:
                caption = resp_data['choices'][0]['message']['content'].strip()
                if caption:
                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(caption)
                    total += 1
                    results.append(f"  ✅ [{idx}/{len(images)}] {filename}: {caption[:50]}...")
                else:
                    errors += 1
                    results.append(f"  ❌ [{idx}/{len(images)}] {filename}: 模型返回为空")
            else:
                errors += 1
                err_msg = resp_data.get('error', {}).get('message', str(resp_data))
                results.append(f"  ❌ [{idx}/{len(images)}] {filename}: API错误 - {err_msg[:80]}")

        except Exception as e:
            errors += 1
            results.append(f"  ❌ [{idx}/{len(images)}] {filename}: {str(e)}")

        # Rate limit: small delay
        time.sleep(0.3)

    summary = (
        f"═══ 阿里云API标注完成 ═══\n"
        f"路径: {image_path}\n"
        f"模型: {model_name}\n"
        f"触发词: {chufaci or '(未设置)'}\n"
        f"成功: {total} / 失败: {errors} / 总计: {len(images)}\n\n"
    )
    results.insert(0, summary)

    return jsonify({
        'success': True,
        'message': '\n'.join(results),
        'total': total,
        'errors': errors
    })
