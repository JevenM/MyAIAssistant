# 配置文件说明

本项目使用 **统一的密钥管理方案**，所有 API Key 集中管理，确保安全性。

## 📁 配置文件位置

### 当前使用的配置方式

**`.streamlit/secrets.toml`** - Streamlit 原生机密存储（推荐）

这是 Streamlit 应用的标准密钥管理方式，支持本地开发和部署。

## 🔧 如何配置

### 第一次使用

1. **复制示例文件**
   ```bash
   # Windows
   copy .streamlit\secrets.toml.example .streamlit\secrets.toml

   # Linux/Mac
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

2. **编辑 secrets.toml 文件**

   打开 `.streamlit/secrets.toml`，填入你的实际 API Key：

   ```toml
   [keys]
   dashscope_api_key = "sk-你的实际key"
   searchapi_api_key = "你的实际key"
   ```

3. **获取 API Key**

   | 服务 | 用途 | 申请地址 |
   |------|------|----------|
   | DashScope | 云端大模型 | https://dashscope.console.aliyun.com/ |
   | SearchAPI | 百度搜索 | https://www.searchapi.io/ |
   | Serper | Google 搜索 | https://serper.dev |
   | Tavily | AI 搜索 | https://tavily.com |
   | SerpAPI | Google 搜索 | https://serpapi.com |

## 🛡️ 安全措施

### 已实施的安全优化

1. **`.gitignore` 配置**
   - `.streamlit/secrets.toml` - 密钥文件被排除在版本控制外
   - `.env` - 环境变量文件被排除

2. **无硬编码密钥**
   - 所有 Python 源码文件中不再包含真实的 API Key
   - 密钥统一从 `llm_config.py` 读取

3. **示例文件分离**
   - `secrets.toml.example` 包含示例配置（无真实密钥）
   - 可以安全地提交到版本控制

### 重要提醒

⚠️ **永远不要将真实的 API Key 提交到 Git！**

如果你不小心提交了：
1. 立即在服务商后台撤销/重新生成 API Key
2. 从 Git 历史中删除（使用 `git filter-branch` 或 BFG Repo-Cleaner）

## 🔄 配置加载优先级

`llm_config.py` 按以下优先级加载配置：

1. **Streamlit secrets** (`.streamlit/secrets.toml`) - 最高优先级
2. **环境变量** - 次优先级
3. **默认值** (空字符串) - 最低优先级

## 📝 文件说明

| 文件 | 用途 | 是否提交到 Git |
|------|------|----------------|
| `.streamlit/secrets.toml` | 实际密钥配置 | ❌ 否（已加入 .gitignore） |
| `.streamlit/secrets.toml.example` | 配置示例 | ✅ 是 |
| `.streamlit/config.toml` | Streamlit 全局配置 | ✅ 是 |
| `llm_config.py` | 密钥读取和配置管理 | ✅ 是 |

## ❓ 常见问题

### Q: 我已经有 `.env` 文件，需要删除吗？
A: 本项目已删除 `.env` 文件，统一使用 `.streamlit/secrets.toml`。如果你有其他环境变量需要配置，可以保留 `.env`，但 API Key 建议全部迁移到 `secrets.toml`。

### Q: 部署到 Streamlit Cloud 怎么办？
A: 在 Streamlit Cloud 的 Dashboard 中，点击你的 App → Settings → Secrets，将 `secrets.toml` 的内容粘贴进去即可。

### Q: 使用 Docker 部署怎么办？
A: 可以将 `secrets.toml` 挂载为 volume，或者在容器启动时通过环境变量传递：
```bash
docker run -e DASHSCOPE_API_KEY=your_key -e SEARCHAPI_API_KEY=your_key your_image
```

### Q: 如何验证配置是否正确？
A: 启动应用后，系统会自动检查配置。如果缺少必需的 API Key，界面会显示提示信息。
