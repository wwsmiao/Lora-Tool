"""
LoraTool - Ollama Local Labeling Routes
Use local Ollama models for image captioning/labeling.
Supports any Ollama vision model with customizable model name.
"""
import os
import json
import base64
import time
from flask import Blueprint, render_template, request, jsonify

qwen_label_bp = Blueprint('qwen_label', __name__)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp'}

# Config & templates
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(PROJECT_ROOT, 'ollama_config.json')
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, 'prompts')

# Available models (static fallback, dynamically replaced by get_ollama_models at runtime)
AVAILABLE_MODELS = [
    'qwen3-vl:8b',
    'qwen3-vl:4b',
    'qwen3.5:4b',
    'qwen3.5:9b',
    'qwen3.5:27b',
    'qwen3.5:35b',
    'qwen2.5vl:7b',
    'gemma4:e2b',
    'gemma4:latest',
    'gemma3:12b',
    'gemma3:4b',
    'llava:7b',
    'llava:13b',
    'llava:34b',
    'llama3.2-vision:11b',
]


def get_ollama_models(api_url='http://localhost:11434'):
    """
    Query Ollama /api/tags endpoint and return available models.
    Always includes AVAILABLE_MODELS static list (for offline/uninstalled models like qwen3.5:4b).
    Deduplicates against Ollama's live list, preserving static order priority.
    """
    seen = set()
    result = []

    # 1. Static fallback models always come first (qwen3.5:4b etc.)
    for m in AVAILABLE_MODELS:
        if m not in seen:
            seen.add(m)
            result.append(m)

    # 2. Merge Ollama's live list, appending new ones at the end
    try:
        import requests as _req
        resp = _req.get(f"{api_url.rstrip('/')}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = resp.json().get('models', [])
            for m in models:
                name = m['name']
                if name not in seen:
                    seen.add(name)
                    result.append(name)
    except Exception:
        pass

    return result


def load_config():
    """Load saved config"""
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


@qwen_label_bp.route('/')
def index():
    cfg = load_config()
    api_url = cfg.get('last_api_url', 'http://localhost:11434')
    models = get_ollama_models(api_url)
    saved_model = cfg.get('last_model', '')
    # Fallback to first available model if saved one not in current list
    if saved_model not in models:
        saved_model = models[0] if models else ''
    return render_template('qwen_label.html', active_page='qwen_label',
                           saved_chufaci=cfg.get('last_chufaci', ''),
                           saved_model=saved_model,
                           available_models=models,
                           saved_api_url=api_url,
                           saved_template=cfg.get('last_template', ''),
                           saved_prompt=cfg.get('last_prompt', ''))


@qwen_label_bp.route('/get_config', methods=['GET'])
def get_config():
    cfg = load_config()
    return jsonify({
        'success': True,
        'last_chufaci': cfg.get('last_chufaci', ''),
        'last_model': cfg.get('last_model', 'qwen3:8b'),
        'last_api_url': cfg.get('last_api_url', 'http://localhost:11434'),
        'last_template': cfg.get('last_template', ''),
        'last_prompt': cfg.get('last_prompt', '')
    })


@qwen_label_bp.route('/save_config', methods=['POST'])
def save_config_route():
    data = request.json
    cfg = load_config()
    cfg['last_chufaci'] = data.get('chufaci', '')
    cfg['last_api_url'] = data.get('api_url', 'http://localhost:11434')

    # Model from dropdown (accept any non-empty model name, including dynamically discovered ones)
    model = data.get('model', '')
    if model:
        cfg['last_model'] = model

    # Template & prompt
    template = data.get('template_file', '')
    if template:
        cfg['last_template'] = template
    prompt = data.get('prompt', '')
    if prompt:
        cfg['last_prompt'] = prompt

    save_config(cfg)
    return jsonify({'success': True, 'message': '配置已保存'})


@qwen_label_bp.route('/get_models', methods=['GET'])
def get_models_route():
    """Return available Ollama models (live + fallback list)."""
    try:
        models = get_ollama_models()
        return jsonify({'success': True, 'models': models})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'models': AVAILABLE_MODELS})


@qwen_label_bp.route('/test_connection', methods=['POST'])
def test_connection_route():
    """Test Ollama API connectivity."""
    data = request.json
    api_url = data.get('ollama_url', 'http://localhost:11434').rstrip('/')
    try:
        import requests as _req
        resp = _req.get(f"{api_url}/api/tags", timeout=5)
        if resp.status_code == 200:
            return jsonify({'success': True, 'message': 'Ollama 服务正常'})
        return jsonify({'success': False, 'message': f'HTTP {resp.status_code}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@qwen_label_bp.route('/list_templates', methods=['GET'])
def list_templates():
    """List available prompt templates"""
    templates = []
    if os.path.isdir(TEMPLATES_DIR):
        for f in sorted(os.listdir(TEMPLATES_DIR)):
            if f.endswith('.json'):
                try:
                    with open(os.path.join(TEMPLATES_DIR, f), 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                    templates.append({'filename': f, 'name': data.get('name', f)})
                except:
                    pass
    return jsonify({'success': True, 'templates': templates})


@qwen_label_bp.route('/load_template', methods=['POST'])
def load_template():
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


@qwen_label_bp.route('/create_template', methods=['POST'])
def create_template():
    """Create a new template JSON file"""
    data = request.json
    name = data.get('name', '').strip()
    prompt_text = data.get('prompt_text', '').strip()
    if not name:
        return jsonify({'success': False, 'message': '模板名称不能为空'})
    # Sanitize filename
    safe = ''.join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
    if not safe:
        return jsonify({'success': False, 'message': '模板名称包含无效字符'})
    filename = safe + '.json'
    filepath = os.path.join(TEMPLATES_DIR, filename)
    if os.path.exists(filepath):
        return jsonify({'success': False, 'message': f'模板 "{safe}" 已存在'})
    template_data = {
        'name': name,
        'prompt_text': prompt_text or '请用简短文字描述这张图片，用于训练AI模型，只输出描述文字。'
    }
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, ensure_ascii=False, indent=2)
        return jsonify({'success': True, 'message': '模板已创建', 'filename': filename})
    except Exception as e:
        return jsonify({'success': False, 'message': f'创建失败: {e}'})


@qwen_label_bp.route('/delete_template', methods=['POST'])
def delete_template():
    """Delete a template file"""
    data = request.json
    filename = data.get('filename', '')
    if not filename:
        return jsonify({'success': False, 'message': '未指定模板'})
    if not filename.endswith('.json'):
        filename += '.json'
    filepath = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'message': '模板不存在'})
    try:
        os.remove(filepath)
        return jsonify({'success': True, 'message': '已删除'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {e}'})
def save_template():
    """Save template content (auto-save from frontend)"""
    data = request.json
    filename = data.get('filename', '')
    name = data.get('name', '')
    prompt_text = data.get('prompt_text', '')
    
    if not filename:
        return jsonify({'success': False, 'message': '未指定模板文件名'})
    if not filename.endswith('.json'):
        filename += '.json'
    
    filepath = os.path.join(TEMPLATES_DIR, filename)
    
    # Validate JSON structure
    try:
        template_data = {
            'name': name or filename.replace('.json', ''),
            'prompt_text': prompt_text
        }
        # Test JSON serialization
        json.dumps(template_data, ensure_ascii=False)
    except Exception as e:
        return jsonify({'success': False, 'message': f'模板数据无效: {e}'})
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, ensure_ascii=False, indent=2)
        return jsonify({
            'success': True, 
            'message': '模板已保存',
            'filename': filename
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'保存模板失败: {e}'})


@qwen_label_bp.route('/process_stream', methods=['POST'])
def process_stream():
    """
    Stream processing progress using Server-Sent Events (SSE).
    Each image processed yields an event to frontend for real-time display.
    """
    data = request.json
    image_path = data.get('image_path', '').strip()
    api_url = data.get('api_url', 'http://localhost:11434').strip()
    model_name = data.get('model_name', '').strip()
    prompt = data.get('prompt', '').strip()
    chufaci = data.get('chufaci', '').strip()
    skip_existing = data.get('skip_existing', True)

    # Use saved model from config if not provided
    if not model_name:
        cfg = load_config()
        model_name = cfg.get('last_model', 'qwen3:8b')
    if not api_url:
        cfg = load_config()
        api_url = cfg.get('last_api_url', 'http://localhost:11434')

    # Save last used config
    cfg = load_config()
    cfg['last_chufaci'] = chufaci
    cfg['last_api_url'] = api_url
    if model_name in AVAILABLE_MODELS:
        cfg['last_model'] = model_name
    save_config(cfg)

    # Set default prompt before generate() to avoid UnboundLocalError
    if not prompt:
        prompt = '请用简短的文字描述这张图片的内容，用于训练AI模型，只输出描述文字，不要有任何其他解释。'

    # Replace {chufaci} placeholder with actual trigger word
    if chufaci:
        prompt = prompt.replace('{chufaci}', chufaci)

    def generate():
        yield 'event: start\ndata: {"status": "started"}\n\n'

        if not image_path:
            yield 'event: error\ndata: {"message": "请填写图片路径"}\n\n'
            return
        if not model_name:
            yield 'event: error\ndata: {"message": "请选择模型"}\n\n'
            return
        if not os.path.isdir(image_path):
            yield f'event: error\ndata: {{"message": "路径不存在: {image_path}"}}\n\n'
            return

        images = sorted([
            f for f in os.listdir(image_path)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        ])

        if not images:
            yield 'event: error\ndata: {"message": "该路径下没有图片文件"}\n\n'
            return

        try:
            import requests
        except ImportError:
            yield 'event: error\ndata: {"message": "缺少 requests 库"}\n\n'
            return

        total = 0
        errors = 0

        # Initial status
        yield f'event: progress\ndata: {{"current": 0, "total": {len(images)}, "message": "开始处理..."}}\n\n'

        for idx, filename in enumerate(images, 1):
            filepath = os.path.join(image_path, filename)
            txt_name = os.path.splitext(filename)[0] + '.txt'
            txt_path = os.path.join(image_path, txt_name)

            # Skip existing txt
            if skip_existing and os.path.exists(txt_path):
                yield f'event: progress\ndata: {{"current": {idx}, "total": {len(images)}, "filename": "{filename}", "status": "skipped", "message": "txt已存在，跳过"}}\n\n'
                continue

            try:
                with open(filepath, 'rb') as f:
                    img_b64 = base64.b64encode(f.read()).decode('utf-8')

                # Ollama /api/generate endpoint
                api_endpoint = f"{api_url.rstrip('/')}/api/generate"
                payload = {
                    "model": model_name,
                    "prompt": prompt,
                    "images": [img_b64],
                    "stream": False
                }

                yield f'event: progress\ndata: {{"current": {idx}, "total": {len(images)}, "filename": "{filename}", "status": "processing", "message": "正在处理..."}}\n\n'

                response = requests.post(api_endpoint, json=payload, timeout=180)
                resp_data = response.json()
                caption = resp_data.get('response', '').strip()

                if caption:
                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(caption)
                    total += 1
                    # Escape special chars for JSON
                    caption_escaped = caption.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '')
                    yield f'event: progress\ndata: {{"current": {idx}, "total": {len(images)}, "filename": "{filename}", "status": "success", "caption": "{caption_escaped}", "message": "完成: {caption[:50]}..."}}\n\n'
                else:
                    errors += 1
                    yield f'event: progress\ndata: {{"current": {idx}, "total": {len(images)}, "filename": "{filename}", "status": "error", "message": "模型返回为空"}}\n\n'
            except requests.exceptions.ConnectionError:
                errors += 1
                yield f'event: error\ndata: {{"message": "连接 Ollama 失败，请确认服务已启动 ({api_url})"}}\n\n'
                break
            except Exception as e:
                errors += 1
                err_msg = str(e).replace('\\', '\\\\').replace('"', '\\"')
                yield f'event: progress\ndata: {{"current": {idx}, "total": {len(images)}, "filename": "{filename}", "status": "error", "message": "{err_msg}"}}\n\n'

            time.sleep(0.2)

        # Final summary
        yield f'event: complete\ndata: {{"total": {total}, "errors": {errors}, "message": "完成: 成功 {total} / 失败 {errors} / 总计 {len(images)}"}}\n\n'

    from flask import Response
    return Response(generate(), mimetype='text/event-stream')


@qwen_label_bp.route('/process', methods=['POST'])
def process():
    """
    Process images using local Ollama model.
    Supports trigger word via {chufaci} placeholder in prompt.
    """
    data = request.json
    image_path = data.get('image_path', '').strip()
    api_url = data.get('api_url', 'http://localhost:11434').strip()
    model_name = data.get('model_name', '').strip()
    prompt = data.get('prompt', '').strip()
    chufaci = data.get('chufaci', '').strip()
    skip_existing = data.get('skip_existing', True)

    # Use saved model from config if not provided
    if not model_name:
        cfg = load_config()
        model_name = cfg.get('last_model', 'qwen3:8b')
    if not api_url:
        cfg = load_config()
        api_url = cfg.get('last_api_url', 'http://localhost:11434')

    # Save last used config
    cfg = load_config()
    cfg['last_chufaci'] = chufaci
    cfg['last_api_url'] = api_url
    if model_name in AVAILABLE_MODELS:
        cfg['last_model'] = model_name
    save_config(cfg)

    if not image_path:
        return jsonify({'success': False, 'message': '请填写图片路径'})
    if not model_name:
        return jsonify({'success': False, 'message': '请选择模型'})
    if not os.path.isdir(image_path):
        return jsonify({'success': False, 'message': f'路径不存在: {image_path}'})

    # Default prompt
    if not prompt:
        prompt = '请用简短的文字描述这张图片的内容，用于训练AI模型，只输出描述文字，不要有任何其他解释。'

    # Replace {chufaci} placeholder with actual trigger word
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

    try:
        import requests
    except ImportError:
        return jsonify({'success': False, 'message': '缺少 requests 库，请执行: pip install requests'})

    for idx, filename in enumerate(images, 1):
        filepath = os.path.join(image_path, filename)
        txt_name = os.path.splitext(filename)[0] + '.txt'
        txt_path = os.path.join(image_path, txt_name)

        # Skip existing txt
        if skip_existing and os.path.exists(txt_path):
            results.append(f"  ⏭️ [{idx}/{len(images)}] {filename}: txt已存在，跳过")
            total += 1
            continue

        try:
            with open(filepath, 'rb') as f:
                img_b64 = base64.b64encode(f.read()).decode('utf-8')

            # Ollama /api/generate endpoint
            api_endpoint = f"{api_url.rstrip('/')}/api/generate"
            payload = {
                "model": model_name,
                "prompt": prompt,
                "images": [img_b64],
                "stream": False
            }

            response = requests.post(api_endpoint, json=payload, timeout=120)
            resp_data = response.json()
            caption = resp_data.get('response', '').strip()

            if caption:
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(caption)
                total += 1
                results.append(f"  ✅ [{idx}/{len(images)}] {filename}: {caption[:60]}...")
            else:
                errors += 1
                results.append(f"  ❌ [{idx}/{len(images)}] {filename}: 模型返回为空")
        except requests.exceptions.ConnectionError:
            errors += 1
            results.append(f"  ❌ 连接 Ollama 失败，请确认服务已启动 ({api_url})")
            break
        except Exception as e:
            errors += 1
            results.append(f"  ❌ [{idx}/{len(images)}] {filename}: {str(e)}")

        time.sleep(0.2)

    summary = (
        f"═══ Ollama 本地标注完成 ═══\n"
        f"路径: {image_path}\n"
        f"模型: {model_name}\n"
        f"API: {api_url}\n"
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