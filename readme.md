## 项目介绍

使用langchain + streamlit + chromadb + langchain_community + langchain_core，实现一个聊天机器人和基于RAG的智能文档检索工具，使用的AI模型是阿里云百炼通义大模型

还有一个记账本功能。

主要是基于慕课网的课程、Bilibili 的教程还有GitHub的代码。


### 生成依赖包列表
1. 安装pipreqs
为了使用pipreqs生成最小化的requirements.txt文件，首先需要在你的环境中安装这个工具。只需一行命令，即可轻松完成安装：
```shell
pip install pipreqs
```
确保安装完成后，你就可以开始使用pipreqs来精简你的项目依赖了。

2. 运行pipreqs
在项目的根目录下，运行以下命令以生成requirements.txt文件：
```shell
pipreqs ./ --encoding=utf8 --force
```
这个命令会扫描你的代码文件，并仅生成项目实际所需的依赖包，排除conda base中的不相关包。生成的requirements.txt文件将干净、精简，与你在项目中手动引用的包完全一致。

注意：pipreqs通过扫描代码来确定项目依赖，因此它更侧重于“按需打包”。如果代码中没有直接导入的包，pipreqs可能无法识别（例如，通过插件或间接依赖安装的包）。

### 功能更新
新增LangGraph，是LangChain的高级库，为大语言模型带来循环计算能力，超越了LangChain的现行工作流，通过循环支持复杂的任务流程。


### 支持功能

#### 聊天记录

#### 聊天问答（可选联网）

#### 基于RAG本地知识库问答

#### 记账本

#### 登录注册

#### 启动
```python
streamlit run app.py
```