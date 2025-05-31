"""
PDF 처리 모듈
교정된 텍스트를 PDF에 오버레이
"""
import json
import fitz
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


class PDFProcessor:
    def __init__(self, config_manager):
        self.config = config_manager
        self.setup_fonts()
        
    def setup_fonts(self):
        """폰트 설정"""
        try:
            pdfmetrics.registerFont(
                TTFont('MalgunGothic', r'C:\Windows\Fonts\malgun.ttf')
            )
        except Exception as e:
            print(f"폰트 등록 오류: {e}")
    
    def overlay_with_fitz(self, input_pdf, blocks, output_pdf, progress_callback=None):
        """교정된 텍스트를 PDF에 오버레이"""
        dpi = self.config.get_setting('dpi', 300)
        scale = 72.0 / dpi  # 1pt = 1/72in
        
        doc = fitz.open(input_pdf)
        
        # 페이지별로 블록 분류
        by_page = {}
        for b in blocks:
            by_page.setdefault(b['page'], []).append(b)

        total_pages = len(doc)
        
        for pno, page in enumerate(doc, start=1):
            if progress_callback:
                progress_callback(f"PDF 오버레이 처리 중... 페이지 {pno}/{total_pages}", 
                                (pno / total_pages) * 100)
            
            # 현재 페이지의 블록만 처리
            if pno not in by_page:
                continue
                
            w_pt, h_pt = page.rect.width, page.rect.height
            
            # TextWriter 객체 생성
            tw = fitz.TextWriter(page.rect)

            # 현재 페이지의 블록들만 처리
            for b in by_page[pno]:
                x0 = b['x_rel'] * w_pt
                y0 = b['y_rel'] * h_pt
                x1 = x0 + b['w_rel'] * w_pt
                y1 = y0 + b['h_rel'] * h_pt
                
                rect = fitz.Rect(x0, y0, x1, y1)
                text = b.get('text_corrected', b['text_raw'])
                fontsize = b['font_size'] * scale
                
                # TextWriter로 텍스트 추가 (자동 한국어 지원)
                tw.append(
                    (x0, y0 + fontsize),  # 시작 위치
                    text,
                    fontsize=fontsize,
                    font=fitz.Font("cjk")  # CJK 폰트 사용
                )
            
            # 페이지에 투명하게 적용
            tw.write_text(page, opacity=0.01)  # 거의 투명하지만 선택 가능
        
        # 파일 크기 최적화
        doc.subset_fonts()  # 폰트 서브셋팅
        doc.ez_save(output_pdf)  # 압축 저장
        
        if progress_callback:
            progress_callback("PDF 오버레이 완료", 100)
        
        return True
