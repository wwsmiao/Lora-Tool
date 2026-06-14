# LoraTool

AI 图像标注工具集 —— 多模型本地推理 + 批量处理 + 流式输出

## 功能

| 模块 | 说明 |
|---|---|
| **Qwen 本地标注** | Qwen3-VL-8B / Qwen3.5-9B 本地推理，4 种算法精度，流式 SSE 输出 |
| **Ollama 本地标注** | 对接 Ollama API，支持任意 VL 模型批量打标 |
| **人脸图像分割** | MTCNN 检测人脸并裁剪，支持置信度调节 |
| **图片批量重命名** | 5 种命名模式（数字/日期/前缀/后缀组合） |
| **图片批量尺寸重设** | fit / fill / exact 三种缩放模式 |
| **字符串操作** | 批量替换或添加 txt 文本内容 |
| **标注修改** | 在线查看/编辑 图片+标注，支持查找替换和批量翻译 |
| **其他工具** | 精选在线工具导航集合 |

## 部署

### 环境要求

- Windows 10+ / Linux
- Python 3.10+
- [Ollama](https://ollama.com)（可选，使用 Ollama 标注时需要）
- NVIDIA GPU + CUDA 12.8（可选，CPU 可运行但较慢。本项目使用 torch 2.10+cu128）

### 1. 克隆项目

```bash
git clone https://github.com/wwsmiao/Lora-Tool.git
cd Lora-Tool
```

### 2. 创建虚拟环境

```bash
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # Linux
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

> 如需 GPU 加速，先安装 CUDA 版 PyTorch：
> ```bash
> pip install torch==2.10.0 torchvision==0.25.0 torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cu128
> ```

### 4. 下载模型（首次使用自动下载）

Qwen 本地标注首次选择模型并点击"开始标注"时，会自动从 ModelScope 下载模型到 `models/Qwen/` 目录：

- `models/Qwen/Qwen3-VL-8B-Instruct/` (~16 GB)
- `models/Qwen/Qwen3.5-9B/` (~18 GB)

或手动下载：
```bash
python -c "from modelscope import snapshot_download; snapshot_download('Qwen/Qwen3-VL-8B-Instruct', cache_dir='models')"
```

### 5. 启动

```bash
start.bat                   # Windows
venv/bin/python app.py      # Linux
```

访问 `http://127.0.0.1:5000`

## 配置

所有配置通过环境变量（可选）：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `LORATOOL_WORK_DIR` | 工作目录 | 项目根目录 |
| `LORATOOL_SECRET_KEY` | Flask 密钥 | 随机生成 |

> **百度翻译**：如需标注修改页面的翻译功能，复制 `.env.example` 为 `.env` 并填入真实的 Baidu API Key。

## 技术栈

- Flask + Jinja2 + Bootstrap 5
- PyTorch 2.10 + CUDA 12.8 + Transformers + ModelScope
- MTCNN（人脸检测）
- SSE（服务端推送流式输出）
- Pillow + OpenCV（图像处理）

## 许可证

MIT
