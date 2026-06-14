"""
LoraTool - String Operations Routes
Replace strings in txt files or prepend text.
"""
import os
from flask import Blueprint, render_template, request, jsonify

string_ops_bp = Blueprint('string_ops', __name__)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.tif', '.webp'}
TEXT_EXTENSIONS = {'.txt', '.text', '.caption'}


@string_ops_bp.route('/')
def index():
    return render_template('string_ops.html', active_page='string_ops')


@string_ops_bp.route('/process', methods=['POST'])
def process():
    data = request.json
    txt_path = data.get('txt_path', '').strip()
    string_a = data.get('string_a', '')
    string_b = data.get('string_b', '')
    op_mode = data.get('op_mode', 'replace')  # replace or add

    if not txt_path:
        return jsonify({'success': False, 'message': '请填写文本路径'})

    if not os.path.isdir(txt_path):
        return jsonify({'success': False, 'message': f'路径不存在: {txt_path}'})

    if op_mode == 'replace' and not string_b:
        return jsonify({'success': False, 'message': '替换模式下，被替换的字符串不能为空'})

    results = []
    total = 0

    if op_mode == 'replace':
        # Replace mode: replace string_b with string_a in all txt files
        txt_files = sorted([
            f for f in os.listdir(txt_path)
            if os.path.splitext(f)[1].lower() in TEXT_EXTENSIONS
        ])

        if not txt_files:
            return jsonify({'success': False, 'message': '该路径下没有txt文本文件'})

        for filename in txt_files:
            filepath = os.path.join(txt_path, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                if string_b in content:
                    new_content = content.replace(string_b, string_a)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    total += 1
                    results.append(f"  ✅ {filename}: 已替换")
                else:
                    results.append(f"  ⏭️ {filename}: 未找到目标字符串")
            except Exception as e:
                results.append(f"  ❌ {filename}: {str(e)}")

        summary = (
            f"═══ 替换完成 ═══\n"
            f"路径: {txt_path}\n"
            f"查找: \"{string_b}\"\n"
            f"替换为: \"{string_a if string_a else '(删除)'}\"\n"
            f"已修改: {total}/{len(txt_files)}\n\n"
        )

    elif op_mode == 'add':
        # Add mode: prepend string_a to all txt files, create if missing for images
        txt_files = [
            f for f in os.listdir(txt_path)
            if os.path.splitext(f)[1].lower() in TEXT_EXTENSIONS
        ]

        # Find images without corresponding txt
        image_files = [
            f for f in os.listdir(txt_path)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
        ]

        for img_file in image_files:
            txt_name = os.path.splitext(img_file)[0] + '.txt'
            if txt_name not in txt_files:
                txt_files.append(txt_name)

        txt_files = sorted(set(txt_files))

        if not txt_files:
            return jsonify({'success': False, 'message': '该路径下没有任何文本或图片文件'})

        for filename in txt_files:
            filepath = os.path.join(txt_path, filename)
            try:
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                else:
                    content = ''

                # Prepend string_a if not already present
                if not content.startswith(string_a):
                    content = string_a + content
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    total += 1
                    created = '' if os.path.getsize(filepath) > len(string_a.encode('utf-8')) else ' (新建)'
                    results.append(f"  ✅ {filename}: 已添加{created}")
                else:
                    results.append(f"  ⏭️ {filename}: 已存在该字符串，跳过")
            except Exception as e:
                results.append(f"  ❌ {filename}: {str(e)}")

        summary = (
            f"═══ 添加完成 ═══\n"
            f"路径: {txt_path}\n"
            f"添加内容: \"{string_a}\"\n"
            f"已处理: {total}/{len(txt_files)}\n\n"
        )

    results.insert(0, summary)

    return jsonify({
        'success': True,
        'message': '\n'.join(results),
        'total': total
    })
