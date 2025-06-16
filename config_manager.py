"""
설정 관리 모듈
API 키 암호화/복호화 및 애플리케이션 설정 관리
"""
import os
import json
import base64
import platform
import hashlib
import getpass
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import tkinter as tk
from tkinter import messagebox


class ConfigManager:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = self.load_config()
        
    def load_config(self):
        """설정 파일 로드"""
        default_config = {
            'api_key_encrypted': '',
            'daily_token_limit': 2000000,
            'max_retries': 3,
            'timeout_seconds': 60,
            'base_model': 'gpt-4.1-mini',
            'dpi': 300,
            'batch_size': 5,
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
    def _generate_auto_password(self):
        """시스템 정보를 기반으로 자동 비밀번호 생성"""
        try:
            # 시스템 고유 정보 수집
            username = getpass.getuser()
            machine_name = platform.node()
            system_info = platform.system() + platform.version()
            
            # 추가 고유 정보 (Windows의 경우)
            try:
                if platform.system() == "Windows":
                    import subprocess
                    # Windows 시스템 UUID 가져오기
                    result = subprocess.run(['wmic', 'csproduct', 'get', 'uuid'], 
                                          capture_output=True, text=True, shell=True)
                    if result.returncode == 0:
                        uuid_line = [line for line in result.stdout.split('\n') if line.strip() and 'UUID' not in line]
                        if uuid_line:
                            system_info += uuid_line[0].strip()
            except:
                pass
            
            # 정보들을 조합하여 해시 생성
            combined_info = f"{username}_{machine_name}_{system_info}"
            
            # SHA256으로 해시 생성 후 처음 32자 사용
            hash_object = hashlib.sha256(combined_info.encode())
            auto_password = hash_object.hexdigest()[:32]
            
            return auto_password
            
        except Exception as e:
            print(f"자동 비밀번호 생성 오류: {e}")
            # 기본 값으로 대체
            return "default_ocr_app_password_2024"

    def _get_key(self, password):
        """패스워드로부터 암호화 키 생성"""
        salt = self._get_or_create_salt()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)
    
    def _get_or_create_salt(self):
        """솔트 가져오기 (항상 config에서 읽기만 함)"""
        if 'encryption_salt' in self.config:
            return base64.b64decode(self.config['encryption_salt'])
        else:
            return None

    def encrypt_api_key(self, api_key):
        """API 키 암호화 (환경 무관, 무작위 솔트 사용)"""
        # 항상 새 솔트 생성
        salt = os.urandom(32)
        self.config['encryption_salt'] = base64.b64encode(salt).decode()
        auto_password = self._generate_auto_password()
        try:
            f = self._get_key(auto_password)
            encrypted_key = f.encrypt(api_key.encode())
            self.config['api_key_encrypted'] = base64.urlsafe_b64encode(encrypted_key).decode()
            self.save_config()
            return True
        except Exception as e:
            print(f"API 키 암호화 오류: {e}")
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror("설정 저장 오류", f"API 키 암호화/저장 중 오류 발생: {e}")
                root.destroy()
            except Exception:
                pass
            return False
    
    def decrypt_api_key(self):
        """API 키 복호화 (시스템 기반 자동 복호화)"""
        auto_password = self._generate_auto_password()
        try:
            if not self.config['api_key_encrypted']:
                return None
                
            f = self._get_key(auto_password)
            encrypted_key = base64.urlsafe_b64decode(self.config['api_key_encrypted'].encode())
            decrypted_key = f.decrypt(encrypted_key)
            return decrypted_key.decode()
        except Exception as e:
            print(f"API 키 복호화 오류: {e}")
            return None
    
    def get_setting(self, key, default=None):
        """설정값 가져오기"""
        return self.config.get(key, default)
    
    def set_setting(self, key, value):
        """설정값 설정"""
        self.config[key] = value
        self.save_config()
    
    def has_encrypted_api_key(self):
        """암호화된 API 키가 있는지 확인"""
        return bool(self.config.get('api_key_encrypted'))
