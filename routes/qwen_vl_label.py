"""
LoraTool - Qwen Local Labeling Routes
Multi-model support: Qwen3-VL-8B-Instruct / Qwen3.5-9B
Algorithm options: standard / fast / sdqa / segattn
"""
import os
import json
import re
import time
from flask import Blueprint, render_template, request, jsonify, Response
from pathlib import Path

qwen_vl_label_bp = Blueprint('qwen_vl_label', __name__)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp'}

# ── Paths ──────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(PROJECT_ROOT, 'qwen_vl_config.json')
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, 'prompts')

# ── Model Registry ─────────────────────────────────────────
MODEL_REGISTRY = {
    "qwen3-vl-8b": {
        "id": "qwen3-vl-8b",
        "name": "Qwen3-VL-8B-Instruct",
        "path": os.path.join(PROJECT_ROOT, "models", "Qwen", "Qwen3-VL-8B-Instruct"),
        "repo": "Qwen/Qwen3-VL-8B-Instruct",
        "size": "16 GB",
        "desc": "稳定版视觉语言模型，通用场景表现优秀",
    },
    "qwen35-9b": {
        "id": "qwen35-9b",
        "name": "Qwen3.5-9B",
        "path": os.path.join(PROJECT_ROOT, "models", "Qwen", "Qwen3.5-9B"),
        "repo": "Qwen/Qwen3.5-9B",
        "size": "~18 GB",
        "desc": "新一代多模态模型，推理+视觉联合增强，128K上下文",
    },
}

# ── Algorithm Options ──────────────────────────────────────
ALGORITHMS = {
    "standard": {
        "id": "standard",
        "name": "标准精度",
        "desc": "全局感知，平衡质量与速度",
        "max_tokens": 512,
    },
    "fast": {
        "id": "fast",
        "name": "快速模式",
        "desc": "精简输出，适合大批量快速处理",
        "max_tokens": 128,
    },
    "sdqa": {
        "id": "sdqa",
        "name": "SDQA",
        "desc": "结构描述+质量评估，多维度详细分析",
        "max_tokens": 768,
    },
    "segattn": {
        "id": "segattn",
        "name": "SegAttention",
        "desc": "分割注意力，区域级精细描述，适合复杂构图",
        "max_tokens": 1024,
    },
}

DEFAULT_MODEL_ID = "qwen3-vl-8b"
DEFAULT_ALGO_ID = "standard"

# ── Global State ───────────────────────────────────────────
_model = None
_processor = None
_device = None
_current_model_id = None
_abort_flag = False  # Set by cancel endpoint, checked in process_stream

# ── Env Diagnostic ─────────────────────────────────────────
_ENV_INFO = {}

def _diagnose_env():
    info = {'python': None, 'modelscope': False, 'torch': False, 'cuda': False, 'venv_path': None}
    import sys
    info['python'] = sys.executable
    info['venv_path'] = os.path.join(PROJECT_ROOT, 'venv', 'Scripts', 'python.exe')
    try:
        from modelscope import Qwen3VLForConditionalGeneration
        info['modelscope'] = True
    except ImportError:
        pass
    try:
        import torch
        info['torch'] = True
        info['cuda'] = torch.cuda.is_available()
    except ImportError:
        pass
    return info

_ENV_INFO = _diagnose_env()


# ── Config Helpers ─────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_config(data):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Model Helpers ──────────────────────────────────────────
def _get_model_info(model_id):
    """Get model registry entry by id, fallback to default."""
    return MODEL_REGISTRY.get(model_id, MODEL_REGISTRY[DEFAULT_MODEL_ID])

def _check_model_dir(path):
    """Check if model files exist at given path."""
    p = Path(path)
    if not p.exists():
        return False
    if not (p / 'config.json').exists():
        return False
    return True

def list_available_models():
    """Build model list with download/loaded status."""
    result = []
    for mid, info in MODEL_REGISTRY.items():
        downloaded = _check_model_dir(info['path'])
        result.append({
            'id': mid,
            'name': info['name'],
            'size': info['size'],
            'desc': info['desc'],
            'downloaded': downloaded,
            'loaded': (_current_model_id == mid),
        })
    return result


def download_model(model_id=''):
    """Download model from ModelScope by model_id."""
    if not model_id:
        model_id = DEFAULT_MODEL_ID
    info = _get_model_info(model_id)
    model_path = info['path']

    try:
        from modelscope import snapshot_download
        # cache_dir must be models/ (not models/Qwen/) so snapshot_download
        # produces models/Qwen/<model_name>/ not models/Qwen/Qwen/<model_name>/
        cache_root = os.path.join(PROJECT_ROOT, 'models')
        os.makedirs(cache_root, exist_ok=True)
        print(f"Downloading {info['repo']} -> {model_path} ...")
        local_dir = snapshot_download(info['repo'], cache_dir=cache_root, revision='master')
        # local_dir = {cache_root}/Qwen/Qwen3.5-9B  etc.
        if local_dir != model_path:
            import shutil
            if os.path.exists(model_path):
                shutil.rmtree(model_path)
            shutil.move(local_dir, model_path)
        return True, f"{info['name']} 下载完成"
    except ImportError:
        venv_hint = os.path.join(PROJECT_ROOT, 'venv', 'Scripts', 'python.exe')
        return False, f'缺少 modelscope 库\n请使用 venv Python 启动: {venv_hint} app.py'
    except Exception as e:
        return False, f"下载失败: {str(e)}"


def load_model(model_id='', device='auto'):
    """Load model by model_id. Auto-downloads if missing."""
    global _model, _processor, _device, _current_model_id

    if not model_id:
        model_id = DEFAULT_MODEL_ID
    info = _get_model_info(model_id)
    model_path = info['path']

    # Already loaded the same model
    if _model is not None and _current_model_id == model_id:
        return True, f"{info['name']} 已加载到 {_device}"

    # Different model loaded → unload first
    if _model is not None:
        unload_model()

    try:
        from modelscope import AutoProcessor
        import torch
        import json as _json

        # Check existence, download if needed
        if not _check_model_dir(model_path):
            print(f"模型 {info['name']} 不存在，自动下载...")
            ok, dl_msg = download_model(model_id)
            if not ok:
                return False, dl_msg

        if device == 'auto':
            device = 'cuda' if torch.cuda.is_available() else 'cpu'

        # Detect architecture from config.json
        cfg_path = os.path.join(model_path, 'config.json')
        with open(cfg_path, 'r', encoding='utf-8') as f:
            model_cfg = _json.load(f)
        arch = model_cfg.get('architectures', ['AutoModel'])[0]
        print(f"Loading {info['name']} (arch: {arch}) -> {device} ...")

        # Dynamically import the correct model class
        # Try modelscope first, fall back to transformers
        try:
            from modelscope import Qwen3VLForConditionalGeneration
            _model_cls_map = {
                'Qwen3VLForConditionalGeneration': Qwen3VLForConditionalGeneration,
            }
            ModelCls = _model_cls_map.get(arch)
        except ImportError:
            ModelCls = None

        # If not in modelscope map, try transformers directly
        if ModelCls is None:
            try:
                import transformers
                ModelCls = getattr(transformers, arch, None)
            except (ImportError, AttributeError):
                pass

        # Fallback: AutoModelForImageTextToText
        if ModelCls is None:
            try:
                from transformers import AutoModelForImageTextToText
                ModelCls = AutoModelForImageTextToText
            except ImportError:
                pass

        # Last resort: modelscope AutoModel
        if ModelCls is None:
            from modelscope import AutoModel
            ModelCls = AutoModel

        _model = ModelCls.from_pretrained(
            model_path,
            trust_remote_code=True,
            dtype='auto',
            device_map=device
        )
        _log_memory(f"after loading {info['name']}")
        _processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
        _device = device
        _current_model_id = model_id

        return True, f"{info['name']} 已加载到 {device}"
    except ImportError:
        venv_hint = os.path.join(PROJECT_ROOT, 'venv', 'Scripts', 'python.exe')
        return False, f'缺少必要的库\n请使用: {venv_hint} app.py'
    except Exception as e:
        return False, f"加载失败: {str(e)}"


def unload_model():
    """Aggressively unload model and free GPU/CPU memory."""
    global _model, _processor, _device, _current_model_id

    if _model is not None:
        _model_name = _get_model_info(_current_model_id or DEFAULT_MODEL_ID)['name']
        print(f"[Memory] Unloading {_model_name} from {_device}...")
        # Move model to CPU first to release GPU memory immediately
        try:
            import torch
            if _device == 'cuda' and hasattr(_model, 'to'):
                _model.to('cpu')
                torch.cuda.synchronize()
        except: pass
        del _model; _model = None

    if _processor is not None:
        del _processor; _processor = None

    _device = None
    _current_model_id = None

    # Force garbage collection (multiple rounds for circular refs)
    import gc
    gc.collect()
    gc.collect()

    # Release CUDA memory
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except: pass

    print(f"[Memory] Unload complete")


# ═══════════════════════════════════════════════════════════
#  Routes
# ═══════════════════════════════════════════════════════════

def _log_memory(tag=""):
    """Log current GPU/CPU memory usage for debugging."""
    try:
        import torch
        if torch.cuda.is_available():
            alloc = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            print(f"[Memory] {tag} GPU: {alloc:.1f}G allocated, {reserved:.1f}G reserved")
    except: pass


@qwen_vl_label_bp.route('/')
def index():
    cfg = load_config()
    saved_model_id = cfg.get('last_model_id', DEFAULT_MODEL_ID)
    saved_algo = cfg.get('last_algorithm', DEFAULT_ALGO_ID)

    env_ok = _ENV_INFO.get('modelscope', False)
    env_warning = None
    if not env_ok:
        env_warning = (
            f'当前 Python 缺少 modelscope 库。'
            f'请使用 venv Python 启动: {_ENV_INFO.get("venv_path", "venv/Scripts/python.exe")} app.py'
        )

    return render_template('qwen_vl_label.html', active_page='qwen_vl_label',
                           saved_chufaci=cfg.get('last_chufaci', ''),
                           saved_template=cfg.get('last_template', ''),
                           saved_prompt=cfg.get('last_prompt', ''),
                           saved_model_id=saved_model_id,
                           saved_algo=saved_algo,
                           models=MODEL_REGISTRY,
                           algorithms=ALGORITHMS,
                           env_ok=env_ok,
                           env_warning=env_warning,
                           env_info=_ENV_INFO)


@qwen_vl_label_bp.route('/get_config', methods=['GET'])
def get_config():
    """Diagnostic endpoint — config loaded via Jinja2 template vars."""
    cfg = load_config()
    return jsonify({
        'success': True,
        'last_chufaci': cfg.get('last_chufaci', ''),
        'last_template': cfg.get('last_template', ''),
        'last_prompt': cfg.get('last_prompt', ''),
        'last_model_id': cfg.get('last_model_id', DEFAULT_MODEL_ID),
        'last_algorithm': cfg.get('last_algorithm', DEFAULT_ALGO_ID),
    })


@qwen_vl_label_bp.route('/save_config', methods=['POST'])
def save_config_route():
    data = request.json
    cfg = load_config()
    cfg['last_chufaci'] = data.get('chufaci', '')
    cfg['last_template'] = data.get('template_file', '')
    cfg['last_prompt'] = data.get('prompt', '')
    cfg['last_model_id'] = data.get('model_id', DEFAULT_MODEL_ID)
    cfg['last_algorithm'] = data.get('algorithm', DEFAULT_ALGO_ID)
    save_config(cfg)
    return jsonify({'success': True, 'message': '配置已保存'})


@qwen_vl_label_bp.route('/list_models', methods=['GET'])
def list_models_route():
    """Return all available models with download/loaded status."""
    return jsonify({'success': True, 'models': list_available_models()})


@qwen_vl_label_bp.route('/list_algorithms', methods=['GET'])
def list_algorithms_route():
    return jsonify({'success': True, 'algorithms': list(ALGORITHMS.values())})


@qwen_vl_label_bp.route('/download_model', methods=['POST'])
def download_model_route():
    data = request.json
    model_id = data.get('model_id', DEFAULT_MODEL_ID)
    ok, msg = download_model(model_id)
    return jsonify({'success': ok, 'message': msg})


@qwen_vl_label_bp.route('/load_model', methods=['POST'])
def load_model_route():
    data = request.json
    model_id = data.get('model_id', DEFAULT_MODEL_ID)
    device = data.get('device', 'auto')
    ok, msg = load_model(model_id, device)
    return jsonify({'success': ok, 'message': msg, 'device': _device, 'model_id': _current_model_id})


@qwen_vl_label_bp.route('/unload_model', methods=['POST'])
def unload_model_route():
    unload_model()
    return jsonify({'success': True, 'message': '模型已卸载'})


@qwen_vl_label_bp.route('/model_status', methods=['GET'])
def model_status():
    if _model is None:
        return jsonify({
            'success': True, 'loaded': False,
            'model_id': None, 'device': None,
            'message': '模型未加载'
        })
    info = _get_model_info(_current_model_id)
    return jsonify({
        'success': True, 'loaded': True,
        'model_id': _current_model_id,
        'model_name': info['name'],
        'device': _device,
        'message': f"{info['name']} 已加载到 {_device}"
    })


# ── Template CRUD (shared with Ollama) ────────────────────

@qwen_vl_label_bp.route('/list_templates', methods=['GET'])
def list_templates():
    templates = []
    if os.path.isdir(TEMPLATES_DIR):
        for f in sorted(os.listdir(TEMPLATES_DIR)):
            if f.endswith('.json'):
                try:
                    with open(os.path.join(TEMPLATES_DIR, f), 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                    templates.append({'filename': f, 'name': data.get('name', f)})
                except: pass
    return jsonify({'success': True, 'templates': templates})


@qwen_vl_label_bp.route('/load_template', methods=['POST'])
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
        return jsonify({'success': True, 'name': tmpl.get('name', ''), 'prompt_text': tmpl.get('prompt_text', '')})
    except Exception as e:
        return jsonify({'success': False, 'message': f'读取模板失败: {e}'})


@qwen_vl_label_bp.route('/create_template', methods=['POST'])
def create_template():
    data = request.json
    name = data.get('name', '').strip()
    prompt_text = data.get('prompt_text', '').strip()
    if not name:
        return jsonify({'success': False, 'message': '模板名称不能为空'})
    safe = ''.join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
    if not safe:
        return jsonify({'success': False, 'message': '模板名称包含无效字符'})
    filename = safe + '.json'
    filepath = os.path.join(TEMPLATES_DIR, filename)
    if os.path.exists(filepath):
        return jsonify({'success': False, 'message': f'模板 "{safe}" 已存在'})
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({'name': name, 'prompt_text': prompt_text or '请用简短文字描述这张图片'}, f, ensure_ascii=False, indent=2)
        return jsonify({'success': True, 'message': '模板已创建', 'filename': filename})
    except Exception as e:
        return jsonify({'success': False, 'message': f'创建失败: {e}'})


@qwen_vl_label_bp.route('/delete_template', methods=['POST'])
def delete_template():
    data = request.json
    filename = data.get('filename', '')
    if not filename: return jsonify({'success': False, 'message': '未指定模板'})
    if not filename.endswith('.json'): filename += '.json'
    filepath = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({'success': False, 'message': '模板不存在'})
    try:
        os.remove(filepath)
        return jsonify({'success': True, 'message': '已删除'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {e}'})


@qwen_vl_label_bp.route('/save_template', methods=['POST'])
def save_template():
    data = request.json
    filename = data.get('filename', '')
    name = data.get('name', '')
    prompt_text = data.get('prompt_text', '')
    if not filename: return jsonify({'success': False, 'message': '未指定模板文件名'})
    if not filename.endswith('.json'): filename += '.json'
    filepath = os.path.join(TEMPLATES_DIR, filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({'name': name or filename.replace('.json', ''), 'prompt_text': prompt_text}, f, ensure_ascii=False, indent=2)
        return jsonify({'success': True, 'message': '模板已保存', 'filename': filename})
    except Exception as e:
        return jsonify({'success': False, 'message': f'保存模板失败: {e}'})


# ═══════════════════════════════════════════════════════════
#  Process Stream (SSE)
# ═══════════════════════════════════════════════════════════

@qwen_vl_label_bp.route('/cancel', methods=['POST'])
def cancel_route():
    """Cancel the running labeling job."""
    global _abort_flag
    _abort_flag = True
    return jsonify({'success': True, 'message': '已发送取消信号'})


@qwen_vl_label_bp.route('/process_stream', methods=['POST'])
def process_stream():
    global _abort_flag
    _abort_flag = False  # Reset for new job
    data = request.json
    image_path = data.get('image_path', '').strip()
    prompt = data.get('prompt', '').strip()
    chufaci = data.get('chufaci', '').strip()
    skip_existing = data.get('skip_existing', True)
    model_id = data.get('model_id', DEFAULT_MODEL_ID)
    algo_id = data.get('algorithm', DEFAULT_ALGO_ID)
    device = data.get('device', 'auto')
    max_tokens = int(data.get('max_tokens', ALGORITHMS.get(algo_id, ALGORITHMS[DEFAULT_ALGO_ID])['max_tokens']))

    # Save config
    cfg = load_config()
    cfg['last_chufaci'] = chufaci
    cfg['last_template'] = data.get('template_file', '')
    cfg['last_prompt'] = prompt
    cfg['last_model_id'] = model_id
    cfg['last_algorithm'] = algo_id
    save_config(cfg)

    if not prompt:
        prompt = '请用简短的文字描述这张图片的内容，用于训练AI模型，只输出描述文字，不要有任何其他解释。'
    if chufaci:
        prompt = prompt.replace('{chufaci}', chufaci)

    # Auto-load model if needed (send feedback events during loading)
    if _model is None or _current_model_id != model_id:
        def err_gen():
            info = _get_model_info(model_id)
            name = info['name']
            yield f'event: progress\ndata: {json.dumps({"current":0,"total":1,"filename":"","status":"processing","message":f"正在加载 {name}..."}, ensure_ascii=False)}\n\n'
            ok, msg = load_model(model_id, device)
            if not ok:
                yield f'event: error\ndata: {json.dumps({"message": msg}, ensure_ascii=False)}\n\n'
                return
            yield f'event: progress\ndata: {json.dumps({"current":0,"total":1,"filename":"","status":"processing","message":f"{name} 加载完成"}, ensure_ascii=False)}\n\n'
        # Loading is quick for CUDA, slow for CPU. Stream progress immediately.
        loading_gen = err_gen()
        # Yield loading progress FIRST before loading the model (but loading happens inside err_gen)
        # Actually, load_model is synchronous and slow. We need to yield BEFORE calling it.
        # Use a 2-phase approach: yield loading message, then load, then yield done.
        info = _get_model_info(model_id)
        name = info['name']
        # First yield: loading started
        _loading_start = f'event: progress\ndata: {json.dumps({"current":0,"total":1,"filename":"","status":"processing","message":f"正在加载 {name}..."}, ensure_ascii=False)}\n\n'
        ok, msg = load_model(model_id, device)
        if not ok:
            def _err():
                yield _loading_start
                yield f'event: error\ndata: {json.dumps({"message": msg}, ensure_ascii=False)}\n\n'
            return Response(_err(), mimetype='text/event-stream')
        # Model loaded, proceed to main generator

    # Auto-load model if needed
    if _model is None or _current_model_id != model_id:
        ok, msg = load_model(model_id, device)
        if not ok:
            def err_gen():
                yield f'event: error\ndata: {json.dumps({"message": msg}, ensure_ascii=False)}\n\n'
            return Response(err_gen(), mimetype='text/event-stream')

    def generate():
        global _abort_flag
        yield f'event: start\ndata: {json.dumps({"status":"started","model":_current_model_id,"algo":algo_id}, ensure_ascii=False)}\n\n'

        if not image_path:
            yield f'event: error\ndata: {json.dumps({"message":"请填写图片路径"}, ensure_ascii=False)}\n\n'; return
        if not os.path.isdir(image_path):
            yield f'event: error\ndata: {json.dumps({"message":f"路径不存在: {image_path}"}, ensure_ascii=False)}\n\n'; return

        images = sorted([f for f in os.listdir(image_path) if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS])
        if not images:
            yield f'event: error\ndata: {json.dumps({"message":"该路径下没有图片文件"}, ensure_ascii=False)}\n\n'; return

        total = 0; errors = 0
        yield f'event: progress\ndata: {json.dumps({"current":0,"total":len(images),"message":"开始处理..."}, ensure_ascii=False)}\n\n'

        for idx, filename in enumerate(images, 1):
            # Check abort flag between each image
            if _abort_flag:
                yield f'event: complete\ndata: {json.dumps({"total":total,"errors":errors,"message":f"已取消: 成功 {total} / 失败 {errors} / 总计 {len(images)}"}, ensure_ascii=False)}\n\n'
                return

            fp = os.path.join(image_path, filename)
            txt_path = os.path.join(image_path, os.path.splitext(filename)[0] + '.txt')

            if skip_existing and os.path.exists(txt_path):
                yield f'event: progress\ndata: {json.dumps({"current":idx,"total":len(images),"filename":filename,"status":"skipped","message":"txt已存在，跳过"}, ensure_ascii=False)}\n\n'
                continue

            try:
                from PIL import Image
                with Image.open(fp) as pil_img:
                    pil_img.load()  # force load to catch corrupt images early
                    # Convert to RGB if needed
                    if pil_img.mode != 'RGB':
                        pil_img = pil_img.convert('RGB')
                    # Use PIL object (not filepath) for better cross-model compatibility
                    messages = [{"role":"user","content":[
                        {"type":"image","image": pil_img},
                        {"type":"text","text": prompt}
                    ]}]
                    # Build chat_template kwargs — disable thinking mode for Qwen3.5
                    tmpl_kwargs = dict(tokenize=True, add_generation_prompt=True,
                                      return_dict=True, return_tensors="pt")
                    if _current_model_id == 'qwen35-9b':
                        tmpl_kwargs['enable_thinking'] = False
                    inputs = _processor.apply_chat_template(messages, **tmpl_kwargs)
                inputs = inputs.to(_model.device)

                yield f'event: progress\ndata: {json.dumps({"current":idx,"total":len(images),"filename":filename,"status":"processing","message":"推理中..."}, ensure_ascii=False)}\n\n'

                import torch
                with torch.no_grad():
                    generated_ids = _model.generate(
                        **inputs, max_new_tokens=max_tokens,
                        pad_token_id=_processor.tokenizer.pad_token_id or _processor.tokenizer.eos_token_id
                    )

                generated_ids_trimmed = [out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)]
                caption = _processor.batch_decode(generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0].strip()
                # Strip think blocks from models that emit reasoning chains
                caption = re.sub(r'<think>.*?</think>\s*', '', caption, flags=re.DOTALL).strip()

                # Explicitly free GPU tensors to prevent VRAM fragmentation
                del generated_ids_trimmed, generated_ids, inputs
                torch.cuda.empty_cache()

                if caption:
                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(caption)
                    total += 1
                    snippet = caption[:50] + ('...' if len(caption) > 50 else '')
                    yield f'event: progress\ndata: {json.dumps({"current":idx,"total":len(images),"filename":filename,"status":"success","caption":caption,"message":f"完成: {snippet}"}, ensure_ascii=False)}\n\n'
                else:
                    errors += 1
                    yield f'event: progress\ndata: {json.dumps({"current":idx,"total":len(images),"filename":filename,"status":"error","message":"模型返回为空"}, ensure_ascii=False)}\n\n'
            except Exception as e:
                errors += 1
                # Clean up any tensors that may have been allocated before the error
                try: del inputs, generated_ids
                except: pass
                torch.cuda.empty_cache()
                yield f'event: progress\ndata: {json.dumps({"current":idx,"total":len(images),"filename":filename,"status":"error","message":str(e)}, ensure_ascii=False)}\n\n'
            time.sleep(0.1)

        yield f'event: complete\ndata: {json.dumps({"total":total,"errors":errors,"message":f"完成: 成功 {total} / 失败 {errors} / 总计 {len(images)}"}, ensure_ascii=False)}\n\n'

    return Response(generate(), mimetype='text/event-stream')
