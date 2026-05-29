"""
用户数据管理模块
实现用户数据的持久化存储，包括聊天记录、记账记录等
数据存储在 user_data/{username}/ 目录下
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path


class UserDataManager:
    """用户数据管理器"""

    # 默认数据根目录
    DEFAULT_ROOT = "./user_data"

    def __init__(self, root_path: str = None):
        """
        初始化用户数据管理器

        Args:
            root_path: 数据存储根目录
        """
        self.root_path = Path(root_path or self.DEFAULT_ROOT)
        self._ensure_root_dir()

    def _ensure_root_dir(self):
        """确保根目录存在"""
        self.root_path.mkdir(parents=True, exist_ok=True)

    def _get_user_dir(self, username: str) -> Path:
        """获取用户数据目录"""
        user_dir = self.root_path / username
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def _load_json(self, filepath: Path, default: Any = None) -> Any:
        """加载JSON文件"""
        if not filepath.exists():
            return default
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载文件失败 {filepath}: {e}")
            return default

    def _save_json(self, filepath: Path, data: Any) -> bool:
        """保存JSON文件"""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存文件失败 {filepath}: {e}")
            return False

    # ========== 聊天记录管理 ==========

    def get_chat_history(self, username: str, chat_type: str = "chat_bot") -> List[Dict]:
        """
        获取聊天历史记录

        Args:
            username: 用户名
            chat_type: 聊天类型 (chat_bot/doc_bot)

        Returns:
            消息列表
        """
        user_dir = self._get_user_dir(username)
        filepath = user_dir / f"chat_{chat_type}.json"
        return self._load_json(filepath, default=[])

    def save_chat_history(self, username: str, messages: List[Dict], chat_type: str = "chat_bot") -> bool:
        """
        保存聊天历史记录

        Args:
            username: 用户名
            messages: 消息列表
            chat_type: 聊天类型

        Returns:
            是否保存成功
        """
        user_dir = self._get_user_dir(username)
        filepath = user_dir / f"chat_{chat_type}.json"
        return self._save_json(filepath, messages)

    def append_chat_message(self, username: str, message: Dict, chat_type: str = "chat_bot") -> bool:
        """
        追加单条聊天消息

        Args:
            username: 用户名
            message: 消息字典
            chat_type: 聊天类型

        Returns:
            是否保存成功
        """
        messages = self.get_chat_history(username, chat_type)
        messages.append(message)
        return self.save_chat_history(username, messages, chat_type)

    def clear_chat_history(self, username: str, chat_type: str = "chat_bot") -> bool:
        """清空聊天记录"""
        return self.save_chat_history(username, [], chat_type)

    # ========== 记账记录管理 ==========

    def get_account_records(self, username: str) -> List[Dict]:
        """获取记账记录"""
        user_dir = self._get_user_dir(username)
        filepath = user_dir / "account_records.json"
        return self._load_json(filepath, default=[])

    def save_account_records(self, username: str, records: List[Dict]) -> bool:
        """保存记账记录"""
        user_dir = self._get_user_dir(username)
        filepath = user_dir / "account_records.json"
        return self._save_json(filepath, records)

    def add_account_record(self, username: str, record: Dict) -> bool:
        """添加记账记录"""
        records = self.get_account_records(username)
        record["id"] = datetime.now().strftime("%Y%m%d%H%M%S")
        record["created_at"] = datetime.now().isoformat()
        records.append(record)
        return self.save_account_records(username, records)

    def delete_account_record(self, username: str, record_id: str) -> bool:
        """删除记账记录"""
        records = self.get_account_records(username)
        records = [r for r in records if r.get("id") != record_id]
        return self.save_account_records(username, records)

    def clear_account_records(self, username: str) -> bool:
        """清空记账记录"""
        return self.save_account_records(username, [])

    # ========== 用户设置管理 ==========

    def get_user_settings(self, username: str) -> Dict:
        """获取用户设置"""
        user_dir = self._get_user_dir(username)
        filepath = user_dir / "settings.json"
        return self._load_json(filepath, default={
            "model_provider": "local",
            "local_model_name": "qwen2.5:3b",
            "cloud_model_name": "deepseek-v4-flash",
            "search_provider": "duckduckgo",
            "online": False,
            "show_thinking": False,
        })

    def save_user_settings(self, username: str, settings: Dict) -> bool:
        """保存用户设置"""
        user_dir = self._get_user_dir(username)
        filepath = user_dir / "settings.json"
        return self._save_json(filepath, settings)

    def update_user_settings(self, username: str, **kwargs) -> bool:
        """更新用户设置"""
        settings = self.get_user_settings(username)
        settings.update(kwargs)
        return self.save_user_settings(username, settings)

    # ========== 全部数据管理 ==========

    def export_all_data(self, username: str) -> Dict:
        """导出用户所有数据"""
        return {
            "chat_bot": self.get_chat_history(username, "chat_bot"),
            "doc_bot": self.get_chat_history(username, "doc_bot"),
            "account_records": self.get_account_records(username),
            "settings": self.get_user_settings(username),
            "exported_at": datetime.now().isoformat(),
        }

    def import_all_data(self, username: str, data: Dict) -> bool:
        """导入用户数据"""
        try:
            if "chat_bot" in data:
                self.save_chat_history(username, data["chat_bot"], "chat_bot")
            if "doc_bot" in data:
                self.save_chat_history(username, data["doc_bot"], "doc_bot")
            if "account_records" in data:
                self.save_account_records(username, data["account_records"])
            if "settings" in data:
                self.save_user_settings(username, data["settings"])
            return True
        except Exception as e:
            print(f"导入数据失败: {e}")
            return False

    def clear_all_data(self, username: str) -> bool:
        """清空用户所有数据"""
        try:
            self.clear_chat_history(username, "chat_bot")
            self.clear_chat_history(username, "doc_bot")
            self.clear_account_records(username)
            return True
        except Exception as e:
            print(f"清空数据失败: {e}")
            return False

    def get_user_stats(self, username: str) -> Dict:
        """获取用户数据统计"""
        chat_bot = self.get_chat_history(username, "chat_bot")
        doc_bot = self.get_chat_history(username, "doc_bot")
        records = self.get_account_records(username)

        income_count = len([r for r in records if r.get("类型") == "收入"])
        expense_count = len([r for r in records if r.get("类型") == "支出"])

        return {
            "chat_messages": len(chat_bot),
            "doc_chat_messages": len(doc_bot),
            "account_records": len(records),
            "income_count": income_count,
            "expense_count": expense_count,
        }


# 全局单例
_user_data_manager = None


def get_user_data_manager() -> UserDataManager:
    """获取用户数据管理器单例"""
    global _user_data_manager
    if _user_data_manager is None:
        _user_data_manager = UserDataManager()
    return _user_data_manager


def load_user_data_to_session(username: str, session_state):
    """
    登录时加载用户数据到session_state

    Args:
        username: 用户名
        session_state: Streamlit session_state对象
    """
    manager = get_user_data_manager()

    # 初始化messages字典
    if "messages" not in session_state:
        session_state.messages = {}

    # 加载聊天记录
    session_state.messages["chat_bot"] = manager.get_chat_history(username, "chat_bot")
    session_state.messages["doc_bot"] = manager.get_chat_history(username, "doc_bot")

    # 加载记账记录
    if "records" not in session_state:
        session_state.records = {}
    session_state.records[username] = manager.get_account_records(username)

    # 加载用户设置
    settings = manager.get_user_settings(username)
    session_state.model_provider = settings.get("model_provider", "local")
    session_state.local_model_name = settings.get("local_model_name", "qwen2.5:3b")
    session_state.cloud_model_name = settings.get("cloud_model_name", "deepseek-v4-flash")
    session_state.search_provider = settings.get("search_provider", "duckduckgo")
    session_state.online = settings.get("online", False)
    session_state.show_thinking = settings.get("show_thinking", False)


def save_user_data_from_session(username: str, session_state):
    """
    保存session_state中的用户数据

    Args:
        username: 用户名
        session_state: Streamlit session_state对象
    """
    manager = get_user_data_manager()

    # 保存聊天记录
    if "messages" in session_state:
        if "chat_bot" in session_state.messages:
            manager.save_chat_history(username, session_state.messages["chat_bot"], "chat_bot")
        if "doc_bot" in session_state.messages:
            manager.save_chat_history(username, session_state.messages["doc_bot"], "doc_bot")

    # 保存记账记录
    if "records" in session_state and username in session_state.records:
        manager.save_account_records(username, session_state.records[username])

    # 保存用户设置
    manager.save_user_settings(username, {
        "model_provider": session_state.get("model_provider", "local"),
        "local_model_name": session_state.get("local_model_name", "qwen2.5:3b"),
        "cloud_model_name": session_state.get("cloud_model_name", "deepseek-v4-flash"),
        "search_provider": session_state.get("search_provider", "duckduckgo"),
        "online": session_state.get("online", False),
        "show_thinking": session_state.get("show_thinking", False),
    })
