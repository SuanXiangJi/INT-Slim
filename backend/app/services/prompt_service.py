import os
import yaml
from typing import Dict, Any, Optional

class PromptService:
    """提示词服务，用于加载和管理所有提示词模板"""
    
    def __init__(self):
        self.prompts_dir = os.path.join(os.path.dirname(__file__), '../prompts')
        self.prompts: Dict[str, Any] = {}
        self.config: Dict[str, Any] = {}
        self.load_all_prompts()
        self.load_config()
    
    def load_config(self) -> None:
        """加载全局配置"""
        config_path = os.path.join(self.prompts_dir, 'config.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
    
    def load_prompt_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """加载单个提示词文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Failed to load prompt file {file_path}: {e}")
            return None
    
    def load_all_prompts(self) -> None:
        """加载所有提示词模板"""
        # 遍历所有目录，加载所有YAML文件
        for root, dirs, files in os.walk(self.prompts_dir):
            for file in files:
                if file.endswith('.yaml') and file != 'config.yaml':
                    file_path = os.path.join(root, file)
                    # 构建提示词ID，格式：目录名.文件名（不含扩展名）
                    rel_path = os.path.relpath(file_path, self.prompts_dir)
                    prompt_id = os.path.splitext(rel_path.replace(os.sep, '.'))[0]
                    
                    prompt_data = self.load_prompt_file(file_path)
                    if prompt_data:
                        self.prompts[prompt_id] = prompt_data
    
    def get_prompt(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取提示词模板"""
        return self.prompts.get(prompt_id)
    
    def get_prompt_content(self, prompt_id: str, **kwargs) -> Optional[str]:
        """获取填充后的提示词内容"""
        prompt = self.get_prompt(prompt_id)
        if not prompt or 'content' not in prompt:
            return None
        
        try:
            return prompt['content'].format(**kwargs)
        except KeyError as e:
            print(f"Missing parameter {e} for prompt {prompt_id}")
            return None
    
    def get_default_model(self) -> Dict[str, Any]:
        """获取默认模型配置"""
        return self.config.get('default_model', {})
    
    def get_available_models(self) -> list:
        """获取可用模型列表"""
        return self.config.get('available_models', [])
    
    def refresh_prompts(self) -> None:
        """刷新所有提示词模板"""
        self.prompts.clear()
        self.load_all_prompts()

# 创建全局提示词服务实例
prompt_service = PromptService()
