#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen3-VL 标注功能诊断脚本
用于检查功能是否正常
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_dependencies():
    """检查依赖库"""
    print("=" * 50)
    print("检查依赖库")
    print("=" * 50)
    
    dependencies = [
        ('flask', 'Flask'),
        ('transformers', 'Transformers'),
        ('modelscope', 'ModelScope'),
        ('torch', 'PyTorch'),
        ('PIL', 'Pillow'),
    ]
    
    missing = []
    for module, name in dependencies:
        try:
            __import__(module)
            print(f"✓ {name} 已安装")
        except ImportError:
            print(f"✗ {name} 未安装")
            missing.append(name)
    
    return missing

def check_model_classes():
    """检查模型类是否可用"""
    print("\n" + "=" * 50)
    print("检查模型类")
    print("=" * 50)
    
    try:
        from modelscope import Qwen3VLForConditionalGeneration
        print("✓ Qwen3VL 模型类可用 (modelscope)")
        return True
    except ImportError as e:
        print(f"✗ 无法导入 Qwen3VL 模型类: {e}")
        return False

def check_routes():
    """检查路由是否正确注册"""
    print("\n" + "=" * 50)
    print("检查路由注册")
    print("=" * 50)
    
    try:
        from main import register_routes
        from flask import Flask
        
        app = Flask(__name__)
        register_routes(app)
        
        # 检查 Qwen3-VL 路由
        rules = [rule.rule for rule in app.url_map.iter_rules()]
        qwen_vl_routes = [r for r in rules if '/qwen_vl_label' in r]
        
        if qwen_vl_routes:
            print("✓ Qwen3-VL 路由已注册:")
            for route in qwen_vl_routes:
                print(f"  - {route}")
            return True
        else:
            print("✗ Qwen3-VL 路由未注册")
            return False
    except Exception as e:
        print(f"✗ 检查路由时出错: {e}")
        return False

def check_templates():
    """检查模板文件"""
    print("\n" + "=" * 50)
    print("检查模板文件")
    print("=" * 50)
    
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'qwen_vl_label.html')
    
    if os.path.exists(template_path):
        print(f"✓ 模板文件存在: {template_path}")
        
        # 检查关键元素
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        checks = [
            ('chufaciInput', '触发词输入框'),
            ('imagePath', '图片路径输入框'),
            ('modelPath', '模型路径输入框'),
            ('startLabeling', '开始标注函数'),
            ('process_stream', '处理流函数'),
        ]
        
        for element, description in checks:
            if element in content:
                print(f"  ✓ {description} ({element})")
            else:
                print(f"  ✗ 缺少 {description} ({element})")
        
        return True
    else:
        print(f"✗ 模板文件不存在: {template_path}")
        return False

def main():
    print("\nQwen3-VL 标注功能诊断")
    print("=" * 50)
    
    # 检查依赖
    missing_deps = check_dependencies()
    if missing_deps:
        print(f"\n⚠️  缺少依赖: {', '.join(missing_deps)}")
        print("请执行: pip install " + " ".join([d.lower() for d in missing_deps]))
        return
    
    # 检查模型类
    if not check_model_classes():
        print("\n⚠️  模型类不可用，请更新 transformers: pip install --upgrade transformers")
        return
    
    # 检查路由
    if not check_routes():
        print("\n⚠️  路由未正确注册，请检查 main.py")
        return
    
    # 检查模板
    check_templates()
    
    print("\n" + "=" * 50)
    print("诊断完成")
    print("=" * 50)
    print("\n如果所有检查都通过，请:")
    print("1. 启动 Flask 应用: python app.py")
    print("2. 访问: http://127.0.0.1:5000/qwen_vl_label/")
    print("3. 配置模型路径并加载模型")
    print("4. 开始标注\n")

if __name__ == '__main__':
    main()
