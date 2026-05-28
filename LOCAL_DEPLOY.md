# 本地化部署指南

## 概述

本项目已从云端 API（通义大模型 + SearchAPI）迁移到完全本地运行：
- **大模型**: 通义大模型 → Ollama 本地模型 (qwen2.5)
- **搜索**: SearchAPI → DuckDuckGo（免费，无需 API Key）
- **向量嵌入**: m3e-base（已是本地）
- **向量数据库**: ChromaDB（已是本地）

## 部署步骤

### 1. 安装 Ollama

**Windows:**
- 下载: https://ollama.com/download
- 或使用 winget: `winget install Ollama.Ollama`

**Mac:**
```bash
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. 启动 Ollama 服务并下载模型

```bash
# 启动服务（Windows/Mac 通常自动启动）
ollama serve

# 下载中文模型（推荐 qwen2.5，通义千问开源版）
ollama pull qwen2.5:7b

# 如果显存/内存不够，可以用更小的模型
# ollama pull qwen2.5:3b
# ollama pull llama3.2
```

### 3. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 4. 运行应用

```bash
streamlit run app.py
```

## 模型推荐

| 模型 | 大小 | 显存需求 | 说明 |
|------|------|----------|------|
| qwen2.5:7b | ~4.7GB | 8GB+ | 推荐，中文效果好 |
| qwen2.5:3b | ~2GB | 4GB+ | 轻量级，适合低配置 |
| llama3.2:3b | ~2GB | 4GB+ | 英文为主 |
| mistral:7b | ~4.1GB | 8GB+ | 多语言支持好 |

## 常见问题

### Q: Ollama 连接失败
```bash
# 检查服务是否运行
ollama list

# 手动启动服务
ollama serve
```

### Q: 显存不足
使用更小的模型，或在 ChatOllama 中设置 `num_gpu=0` 使用 CPU：
```python
model = ChatOllama(
    model="qwen2.5:7b",
    num_gpu=0,  # 使用 CPU
)
```

### Q: DuckDuckGo 搜索失败
DuckDuckGo 偶尔会有限制，可以：
1. 关闭网页搜索开关
2. 或配置代理：`export DDG_PROXY=socks5://127.0.0.1:1080`
