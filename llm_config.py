"""
LLM API 统一配置文件
管理和集中所有在线大模型 API 的配置

支持的配置来源（优先级从高到低）：
1. Streamlit secrets (.streamlit/secrets.toml) - 推荐用于 Streamlit 应用
2. 环境变量
3. 默认值（空字符串或预留值）

使用方法：
    from llm_config import DASHSCOPE_API_KEY, llm_config
"""
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, field


def _get_secret(key: str, default: str = "") -> str:
    """
    获取密钥，按优先级尝试：
    1. Streamlit secrets (如果在 Streamlit 环境中)
    2. 环境变量
    3. 默认值
    """
    # 尝试从 Streamlit secrets 读取
    try:
        import streamlit as st
        # 检查是否在 Streamlit 运行环境中
        if hasattr(st, 'secrets') and key in st.secrets.get('keys', {}):
            return st.secrets['keys'][key]
        # 也尝试直接读取（兼容嵌套和非嵌套格式）
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
    except ImportError:
        pass  # 未安装 streamlit
    except Exception:
        pass  # 不在 streamlit 环境中

    # 尝试从环境变量读取
    env_value = os.getenv(key.upper())
    if env_value:
        return env_value

    return default


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    display_name: str
    provider: str  # "local" | "dashscope" | "openai" | "anthropic"
    description: str = ""


@dataclass
class LLMConfig:
    """LLM API 统一配置类"""

    # ==================== DashScope (阿里云百炼/通义千问) ====================
    # 从 secrets.toml 或环境变量读取，如果不存在则使用空字符串（需要用户配置）
    DASHSCOPE_API_KEY: str = field(default_factory=lambda: _get_secret(
        "dashscope_api_key",
        ""  # 请配置到 secrets.toml 或环境变量
    ))
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # 云端模型列表 (通过 DashScope)
    CLOUD_MODELS: List[ModelConfig] = field(default_factory=lambda: [
        ModelConfig(
            name="deepseek-v4-flash",
            display_name="DeepSeek-V4-Flash",
            provider="dashscope",
            description="DeepSeek 快速模型"
        ),
        # ModelConfig(
        #     name="deepseek-reasoner",
        #     display_name="DeepSeek-Reasoner",
        #     provider="dashscope",
        #     description="DeepSeek 推理模型（带思考过程）"
        # ),
        ModelConfig(
            name="qwen3.6-plus",
            display_name="通义千问3.6-Plus",
            provider="dashscope",
            description="阿里云通义千问增强版"
        ),
        ModelConfig(
            name="qwen3.6-35b-a3b",
            display_name="通义千问3.6-35B-A3B",
            provider="dashscope",
            description="阿里云通义千问35B参数版"
        ),
        # ModelConfig(
        #     name="qwen-turbo",
        #     display_name="通义千问-Turbo",
        #     provider="dashscope",
        #     description="阿里云通义千问极速版"
        # ),
        # ModelConfig(
        #     name="qwen-3.7-max",  # 如需使用 qwen-3.7-max，取消注释此段
        #     display_name="通义千问3.7-Max",
        #     provider="dashscope",
        #     description="阿里云通义千问3.7 Max版"
        # ),
    ])

    # 思考模式专用模型
    THINKING_MODEL: str = "deepseek-reasoner"  # 用于思考模式的模型

    # ==================== 本地模型 (Ollama) ====================
    OLLAMA_BASE_URL: str = "http://localhost:11434"  # Ollama 服务地址

    LOCAL_MODELS: List[ModelConfig] = field(default_factory=lambda: [
        ModelConfig(
            name="qwen2.5:7b",
            display_name="通义千问2.5 (7B)",
            provider="local",
            description="本地运行，隐私性好"
        ),
        ModelConfig(
            name="qwen2.5:3b",
            display_name="通义千问2.5 (3B)",
            provider="local",
            description="本地运行，资源占用低"
        ),
        ModelConfig(
            name="llama3.2",
            display_name="Llama 3.2",
            provider="local",
            description="Meta Llama 3.2"
        ),
        ModelConfig(
            name="mistral:7b",
            display_name="Mistral (7B)",
            provider="local",
            description="Mistral 7B 模型"
        ),
    ])

    # ==================== 搜索 API ====================
    # SearchAPI (百度搜索)
    SEARCHAPI_API_KEY: str = field(default_factory=lambda: _get_secret(
        "searchapi_api_key",
        ""  # 请配置到 secrets.toml 或环境变量
    ))

    # Serper (Google 搜索)
    SERPER_API_KEY: str = field(default_factory=lambda: _get_secret(
        "serper_api_key",
        _get_secret("SERPER_API_KEY", "")  # 兼容旧环境变量名
    ))

    # Tavily (AI 搜索)
    TAVILY_API_KEY: str = field(default_factory=lambda: _get_secret(
        "tavily_api_key",
        _get_secret("TAVILY_API_KEY", "")
    ))

    # SerpAPI (Google 搜索)
    SERPAPI_KEY: str = field(default_factory=lambda: _get_secret(
        "serpapi_api_key",
        _get_secret("SERPAPI_KEY", "")
    ))

    # 搜索引擎列表
    SEARCH_PROVIDERS: Dict[str, Dict] = field(default_factory=lambda: {
        "duckduckgo": {
            "name": "🦆 DuckDuckGo",
            "description": "免费，无需API Key",
            "requires_key": False,
        },
        "baidu": {
            "name": "🌐 百度",
            "description": "SearchAPI，需要 API Key",
            "requires_key": True,
            "key_name": "searchapi_api_key",
        },
        "serper": {
            "name": "🔍 Google (Serper)",
            "description": "免费 2500次/月",
            "requires_key": True,
            "key_name": "serper_api_key",
            "signup_url": "https://serper.dev",
        },
        "tavily": {
            "name": "🤖 Tavily",
            "description": "免费 1000次/月",
            "requires_key": True,
            "key_name": "tavily_api_key",
            "signup_url": "https://tavily.com",
        },
        "serpapi": {
            "name": "🔎 SerpAPI",
            "description": "免费 100次/月",
            "requires_key": True,
            "key_name": "serpapi_api_key",
            "signup_url": "https://serpapi.com",
        },
    })

    # ==================== 默认配置 ====================
    DEFAULT_MODEL_PROVIDER: str = "local"  # "local" 或 "cloud"
    DEFAULT_LOCAL_MODEL: str = "qwen2.5:3b"
    DEFAULT_CLOUD_MODEL: str = "deepseek-v4-flash"
    DEFAULT_SEARCH_PROVIDER: str = "duckduckgo"

    # ==================== Embedding 配置 ====================
    EMBEDDING_MODEL_PATH: str = r"E:\Doctor1\coding\Langchain-Chatchat\_models\m3e-base"

    # ==================== 方法 ====================
    def get_cloud_model_names(self) -> List[str]:
        """获取所有云端模型名称列表"""
        return [m.name for m in self.CLOUD_MODELS]

    def get_local_model_names(self) -> List[str]:
        """获取所有本地模型名称列表"""
        return [m.name for m in self.LOCAL_MODELS]

    def get_model_display_name(self, name: str, provider: str) -> str:
        """获取模型的显示名称"""
        models = self.LOCAL_MODELS if provider == "local" else self.CLOUD_MODELS
        for m in models:
            if m.name == name:
                return m.display_name
        return name

    def validate_search_key(self, provider: str) -> bool:
        """验证搜索API Key是否配置"""
        if provider == "duckduckgo":
            return True
        if provider == "baidu":
            return bool(self.SEARCHAPI_API_KEY)
        if provider == "serper":
            return bool(self.SERPER_API_KEY)
        if provider == "tavily":
            return bool(self.TAVILY_API_KEY)
        if provider == "serpapi":
            return bool(self.SERPAPI_KEY)
        return False

    def check_api_key_configured(self) -> Dict[str, bool]:
        """检查各 API Key 是否已配置"""
        return {
            "dashscope": bool(self.DASHSCOPE_API_KEY),
            "searchapi": bool(self.SEARCHAPI_API_KEY),
            "serper": bool(self.SERPER_API_KEY),
            "tavily": bool(self.TAVILY_API_KEY),
            "serpapi": bool(self.SERPAPI_KEY),
        }

    def get_missing_keys(self) -> List[str]:
        """获取未配置的必需 API Key 列表"""
        missing = []
        if not self.DASHSCOPE_API_KEY:
            missing.append("dashscope_api_key (云端模型)")
        # searchapi 仅在使用百度搜索时需要
        return missing


# 全局配置实例
llm_config = LLMConfig()


# 便捷导入的常量
DASHSCOPE_API_KEY = llm_config.DASHSCOPE_API_KEY
DASHSCOPE_BASE_URL = llm_config.DASHSCOPE_BASE_URL
SEARCHAPI_API_KEY = llm_config.SEARCHAPI_API_KEY
SERPER_API_KEY = llm_config.SERPER_API_KEY
TAVILY_API_KEY = llm_config.TAVILY_API_KEY
SERPAPI_KEY = llm_config.SERPAPI_KEY
CLOUD_MODELS = llm_config.get_cloud_model_names()
LOCAL_MODELS = llm_config.get_local_model_names()
THINKING_MODEL = llm_config.THINKING_MODEL
