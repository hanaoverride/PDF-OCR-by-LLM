"""
OCR 처리 모듈
EasyOCR을 사용한 PDF 텍스트 추출 및 전처리
"""
import os
import json
import io
import numpy as np
import fitz
from PIL import Image
import easyocr
from tqdm import tqdm


class OCRProcessor:
    def __init__(self, config_manager):
        self.config = config_manager
        self.reader = None
        
    def initialize_reader(self):
        """EasyOCR 리더 초기화"""
        if self.reader is None:
            self.reader = easyocr.Reader(['ko', 'en'], gpu=True)
    
    def preprocess_pdf(self, input_pdf, json_path, start_page, end_page, progress_callback=None):
        """
        EasyOCR을 사용해 PDF 전체 페이지를 이미지로 변환한 뒤
        텍스트 박스와 내용을 추출하여 상대좌표 리스트로 저장합니다.
        start_page, end_page가 None인 경우 전체 페이지를 처리합니다.
        """
        dpi = self.config.get_setting('dpi', 300)
        
        # PDF 문서 열기
        doc = fitz.open(input_pdf)
        
        # 페이지 범위 설정
        if start_page is None and end_page is None:
            # 전체 페이지
            start_idx = 0
            end_idx = len(doc) - 1
        else:
            # 특정 페이지 범위 (1-based → 0-based 변환)
            start_idx = (start_page - 1) if start_page else 0
            end_idx = (end_page - 1) if end_page else (len(doc) - 1)
        
        # 1) PDF → 이미지 변환 (PyMuPDF 사용)
        images = []
        page_numbers = []
        
        for page_idx in range(start_idx, end_idx + 1):
            page = doc[page_idx]
            # DPI를 매트릭스로 변환 (72 DPI 기준)
            mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("ppm")
            img = Image.open(io.BytesIO(img_data))
            images.append(img)
            page_numbers.append(page_idx + 1)  # 1-based 페이지 번호
        
        doc.close()
        
        # 2) EasyOCR reader 초기화 (한글+영어)
        self.initialize_reader()

        blocks = []
        id_counter = 0
        total_pages = len(images)

        # 3) 페이지별로 OCR 수행
        for idx, (page_num, img) in enumerate(zip(page_numbers, images)):
            if progress_callback:
                if end_page is not None:
                    progress_callback(f"OCR 처리 중... 페이지 {page_num}/{end_page}", 
                                    (idx + 1) / total_pages * 100)
                else:
                    progress_callback(f"OCR 처리 중... 페이지 {page_num}/{total_pages}", 
                                    (idx + 1) / total_pages * 100)
            
            img_w, img_h = img.size
            # PIL 이미지를 NumPy 배열로 변환
            arr = np.array(img.convert('RGB'))

            # readtext → [(bbox, text, confidence), ...]
            results = self.reader.readtext(arr)

            for bbox, text, conf in results:
                # bbox: [ [x1,y1], [x2,y2], [x3,y3], [x4,y4] ]
                xs = [pt[0] for pt in bbox]
                ys = [pt[1] for pt in bbox]
                x_min, x_max = min(xs), max(xs)
                y_min, y_max = min(ys), max(ys)

                blocks.append({
                    'page': page_num,
                    'id': id_counter,
                    'text_raw': text,
                    'confidence': conf,
                    # 상대좌표 (0~1)
                    'x_rel': x_min / img_w,
                    'y_rel': y_min / img_h,
                    'w_rel': (x_max - x_min) / img_w,
                    'h_rel': (y_max - y_min) / img_h,
                    # baseline font size approximation
                    'font_size': (y_max - y_min)
                })
                id_counter += 1

        # 4) JSON 파일로 저장
        def np_default(o):
            # numpy scalar 타입이면 .item()으로 파이썬 스칼라 추출
            if isinstance(o, np.generic):
                return o.item()
            raise TypeError
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(blocks, f, ensure_ascii=False, indent=2, default=np_default)

        if progress_callback:
            progress_callback("OCR 처리 완료", 100)
        
        return blocks
