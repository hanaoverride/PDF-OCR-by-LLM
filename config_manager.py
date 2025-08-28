"""
설정 관리 모듈
애플리케이션 설정 관리
"""
import os
import json


class ConfigManager:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = self.load_config()
        
    def load_config(self):
        """설정 파일 로드"""
        default_config = {
            'api_key': '',
            'daily_token_limit': 2000000,
            'max_retries': 3,
            'timeout_seconds': 60,
            'base_model': 'gpt-5-mini',
            'dpi': 300,
            'batch_size': 50,
            'output_folder': '',
            'last_pdf_folder': '',
        }
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                default_config.update(loaded_config)
        except Exception as e:
            print(f"설정 파일 로드 오류: {e}")
        return default_config
    
    def save_config(self):
        """설정 파일 저장"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"설정 파일 저장 오류: {e}")
    
    def get_setting(self, key, default=None):
        """설정값 가져오기"""
        return self.config.get(key, default)

    def set_setting(self, key, value):
        """설정값 설정"""
        self.config[key] = value
        self.save_config()

    def has_api_key(self):
        """API 키가 있는지 확인"""
        return bool(self.config.get('api_key'))
