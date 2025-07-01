"""
API 처리 모듈
OpenAI API를 사용한 텍스트 교정
"""
import json
import datetime
import time
import openai
from tqdm import tqdm


class APIProcessor:
    def __init__(self, config_manager):
        self.config = config_manager
        self.usage = 0
        self.token_usage_file = 'token_usage.json'
        
    def load_token_usage(self):
        """토큰 사용량 로드"""
        try:
            with open(self.token_usage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('date') == datetime.datetime.now().strftime('%Y-%m-%d'):
                return data.get('used', 0)
        except Exception:
            pass
        return 0
    
    def save_token_usage(self, used):
        """토큰 사용량 저장"""
        data = {
            'date': datetime.datetime.now().strftime('%Y-%m-%d'),
            'used': used
        }
        with open(self.token_usage_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def check_token_limit(self):
        """일일 토큰 제한 확인"""
        daily_limit = self.config.get_setting('daily_token_limit', 2000000)
        current_usage = self.load_token_usage()
        return current_usage < daily_limit
    def recover_text_with_api(self, raw_json, out_json, api_key, progress_callback=None, log_callback=None):
        """API를 사용해 텍스트 교정"""
        # 설정값 로드
        batch_size = self.config.get_setting('batch_size', 50)
        max_retries = self.config.get_setting('max_retries', 3)
        timeout_seconds = self.config.get_setting('timeout_seconds', 60)
        base_model = self.config.get_setting('base_model', 'gpt-4.1-mini')
        
        # 토큰 사용량 로드
        usage = self.load_token_usage()
        
        # 데이터 로드
        with open(raw_json, 'r', encoding='utf-8') as f:
            items = json.load(f)
        
        corrected = []
        openai.api_key = api_key

        # 전체 블록을 batch_size 단위로 분할
        total = len(items)
        total_batches = (total + batch_size - 1) // batch_size
        
        for batch_idx in range(0, total, batch_size):
            chunk = items[batch_idx:batch_idx + batch_size]
            current_batch = batch_idx // batch_size + 1
            
            if progress_callback:
                progress_callback(f"API 교정 중... 배치 {current_batch}/{total_batches}", 
                                (current_batch / total_batches) * 100)
            
            raws = [b['text_raw'] for b in chunk]
            prompt = (
                "EasyOCR 결과를 바탕으로 원본 텍스트를 복원해주세요.\n\n"
                + "\n".join(raws)
            )

            retries = 0
            resp = None
            while retries < max_retries:
                try:
                    resp = openai.chat.completions.create(
                        model=base_model,
                        messages=[
                            {
                                'role': 'system',
                                'content': (
                                    '당신은 EasyOCR 텍스트 데이터 복구 전문가입니다. '
                                    '주어진 텍스트 조각 배열을 원본 형태로 복원하여, '
                                    '반드시 같은 순서와 개수의 줄로 응답해야 합니다.'
                                )
                            },
                            {'role': 'user', 'content': prompt}                        ],
                        temperature=0
                    )
                    break
                except Exception as e:
                    error_str = str(e).lower()
                    
                    # OpenAI API 오류 상세 처리
                    if any(keyword in error_str for keyword in ['invalid_api_key', 'incorrect api key', 'error code: 401', 'unauthorized']):
                        error_msg = ("유효한 API Key를 입력하지 않아 정상적인 교정 작업이 이루어지지 않았습니다. 작업을 중단합니다.\n"
                                   "API Key를 다시 확인하고 올바른 API Key를 입력해주세요.")
                        raise Exception(f"API_KEY_ERROR: {error_msg}")
                    
                    elif any(keyword in error_str for keyword in ['quota', 'rate limit', 'billing', 'exceeded']):
                        error_msg = ("API 사용량 한도를 초과했거나 결제 문제가 발생했습니다.\n"
                                   "OpenAI 계정의 사용량 및 결제 상태를 확인해주세요.")
                        raise Exception(f"QUOTA_ERROR: {error_msg}")
                    
                    elif any(keyword in error_str for keyword in ['model not found', 'invalid model', 'model']):
                        error_msg = ("지정된 모델을 찾을 수 없습니다.\n"
                                   "사용 가능한 모델명을 확인하고 다시 시도해주세요.")
                        raise Exception(f"MODEL_ERROR: {error_msg}")
                    
                    elif any(keyword in error_str for keyword in ['context length', 'token limit', 'too long']):
                        error_msg = ("입력 텍스트가 너무 길어서 처리할 수 없습니다.\n"
                                   "더 작은 단위로 나누어 처리해주세요.")
                        raise Exception(f"TOKEN_LIMIT_ERROR: {error_msg}")
                    elif any(keyword in error_str for keyword in ['connection', 'network', 'timeout']):
                        retries += 1
                        if retries < 3:
                            retry_msg = f"[재시도] 네트워크 오류로 재시도 중... ({retries}/3)"
                            if log_callback:
                                log_callback(retry_msg)
                            else:
                                print(retry_msg)
                            time.sleep(2)
                            continue
                        else:
                            error_msg = ("네트워크 연결 문제가 지속되고 있습니다.\n"
                                       "인터넷 연결을 확인하고 잠시 후 다시 시도해주세요.")
                            raise Exception(f"NETWORK_ERROR: {error_msg}")
                    
                    elif any(keyword in error_str for keyword in ['server error', '500', '502', '503']):
                        retries += 1
                        if retries < 3:
                            retry_msg = f"[재시도] 서버 오류로 재시도 중... ({retries}/3)"
                            if log_callback:
                                log_callback(retry_msg)
                            else:
                                print(retry_msg)
                            time.sleep(5)
                            continue
                        else:
                            error_msg = ("OpenAI 서버에 일시적인 문제가 발생했습니다.\n"
                                       "잠시 후 다시 시도해주세요.")
                            raise Exception(f"SERVER_ERROR: {error_msg}")
                    
                    else:
                        # 기타 알 수 없는 오류
                        error_msg = f"API 호출 중 알 수 없는 오류가 발생했습니다: {str(e)}"
                        skip_msg = f"[오류] 배치 {current_batch} 처리 중 예외: {e} — 스킵"
                        if log_callback:
                            log_callback(skip_msg)
                        else:
                            print(skip_msg)
                        raise Exception(f"UNKNOWN_API_ERROR: {error_msg}")

            if resp is None:
                # 실패한 경우 원본 텍스트 사용
                for b in chunk:
                    new_b = b.copy()
                    new_b['text_corrected'] = b['text_raw']
                    corrected.append(new_b)
                continue

            # 토큰 사용량 업데이트
            try:
                usage += resp.usage.total_tokens
                self.save_token_usage(usage)
            except:
                pass

            # 응답을 줄 단위로 나누어 각 블록에 매핑 (빈 줄도 포함)
            texts = resp.choices[0].message.content.split('\n')
            if len(texts) != len(chunk):
                if log_callback:
                    log_callback(f"[경고] 교정 결과 줄 수({len(texts)})와 원본 블록 수({len(chunk)})가 다릅니다. 빈 줄도 포함하여 매칭합니다.")
                # 부족하면 빈 문자열로 채움, 넘치면 자름
                if len(texts) < len(chunk):
                    texts += [''] * (len(chunk) - len(texts))
                else:
                    texts = texts[:len(chunk)]
            for b, txt in zip(chunk, texts):
                new_b = b.copy()
                new_b['text_corrected'] = txt
                corrected.append(new_b)

        # 결과 저장
        with open(out_json, 'w', encoding='utf-8') as f:
            json.dump(corrected, f, ensure_ascii=False, indent=2)
        
        if progress_callback:
            progress_callback("API 교정 완료", 100)
        
        return corrected
