"""
메인 GUI 애플리케이션
OCR PDF 처리를 위한 GUI 인터페이스
"""
import os
import json
import fitz  # PyMuPDF for page counting in completion checks
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import threading
from config_manager import ConfigManager
from ocr_processor import OCRProcessor
from api_processor import APIProcessor
from pdf_processor import PDFProcessor


class OCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PDF OCR 처리기")
        self.root.geometry("800x700")
        
        # 설정 관리자 초기화
        self.config_manager = ConfigManager()
        
        # 프로세서 초기화
        self.ocr_processor = OCRProcessor(self.config_manager)
        self.api_processor = APIProcessor(self.config_manager)
        self.pdf_processor = PDFProcessor(self.config_manager)        # 변수 초기화
        self.input_pdf_path = tk.StringVar()
        self.input_pdf_paths = []  # 복수 PDF 파일 경로 저장
        self.output_folder_path = tk.StringVar(value=self.config_manager.get_setting('output_folder', ''))
        self.start_page = tk.IntVar(value=1)
        self.end_page = tk.IntVar(value=1)
        self.all_pages = tk.BooleanVar(value=False)
        self.debug_mode = tk.BooleanVar(value=True)
        self.api_key = ""
        self.processing_cancelled = False
        
        self.setup_ui()
        self.load_settings()
    
    def setup_ui(self):
        """UI 설정"""
        # 메인 프레임
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 탭 생성
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # 메인 탭
        self.main_tab = ttk.Frame(notebook)
        notebook.add(self.main_tab, text="메인")
        
        # 설정 탭
        self.settings_tab = ttk.Frame(notebook)
        notebook.add(self.settings_tab, text="설정")
        
        self.setup_main_tab()
        self.setup_settings_tab()
    
    def setup_main_tab(self):
        """메인 탭 설정"""
        # 파일 선택 섹션
        file_frame = ttk.LabelFrame(self.main_tab, text="파일 선택", padding=10)
        file_frame.pack(fill=tk.X, pady=(0, 10))        # PDF 파일 선택
        ttk.Label(file_frame, text="입력 PDF:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(file_frame, textvariable=self.input_pdf_path, width=50).grid(row=0, column=1, padx=(5, 5), pady=2)
        ttk.Button(file_frame, text="단일 선택", command=self.select_single_pdf).grid(row=0, column=2, pady=2)
        ttk.Button(file_frame, text="복수 선택", command=self.select_multiple_pdfs).grid(row=0, column=3, padx=(5, 0), pady=2)
        
        # 페이지 범위 섹션
        page_frame = ttk.LabelFrame(self.main_tab, text="페이지 범위", padding=10)
        page_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 전체 페이지 체크박스
        self.all_pages_check = ttk.Checkbutton(
            page_frame, 
            text="전체 페이지", 
            variable=self.all_pages, 
            command=self.toggle_page_range
        )
        self.all_pages_check.grid(row=0, column=0, sticky=tk.W, pady=2, columnspan=2)
        
        # 페이지 범위 입력
        ttk.Label(page_frame, text="시작 페이지:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.start_spinbox = ttk.Spinbox(page_frame, from_=1, to=9999, textvariable=self.start_page, width=10)
        self.start_spinbox.grid(row=1, column=1, padx=(5, 20), pady=2)
        
        ttk.Label(page_frame, text="끝 페이지:").grid(row=1, column=2, sticky=tk.W, pady=2)
        self.end_spinbox = ttk.Spinbox(page_frame, from_=1, to=9999, textvariable=self.end_page, width=10)
        self.end_spinbox.grid(row=1, column=3, padx=(5, 0), pady=2)
        
        # API 키 섹션
        self.api_frame = ttk.LabelFrame(self.main_tab, text="API 키", padding=10)
        self.api_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.update_api_key_ui()
        
        # 진행률 섹션
        progress_frame = ttk.LabelFrame(self.main_tab, text="진행률", padding=10)
        progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.progress_var = tk.StringVar(value="대기 중...")
        self.progress_label = ttk.Label(progress_frame, textvariable=self.progress_var)
        self.progress_label.pack(anchor=tk.W)
        
        self.progress_bar = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))        # 실행 버튼
        button_frame = ttk.Frame(self.main_tab)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.start_button = ttk.Button(button_frame, text="OCR 처리 시작", command=self.start_processing)
        self.start_button.pack(side=tk.LEFT)
        
        self.stop_button = ttk.Button(button_frame, text="중지", command=self.stop_processing, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=(10, 0))
        
        # 디버그 모드 체크박스
        self.debug_check = ttk.Checkbutton(
            button_frame, 
            text="디버그 모드", 
            variable=self.debug_mode, 
            command=self.toggle_debug_mode
        )
        self.debug_check.pack(side=tk.RIGHT)
        
        # 디버그 로그 창
        self.debug_frame = ttk.LabelFrame(self.main_tab, text="디버그 로그", padding=10)
        self.debug_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # 스크롤 가능한 텍스트 위젯
        log_text_frame = ttk.Frame(self.debug_frame)
        log_text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_text_frame, height=10, width=80, state=tk.DISABLED)
        log_scrollbar = ttk.Scrollbar(log_text_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 로그 지우기 버튼
        clear_log_btn = ttk.Button(self.debug_frame, text="로그 지우기", command=self.clear_debug_log)
        clear_log_btn.pack(anchor=tk.E, pady=(5, 0))
    
    def setup_settings_tab(self):
        """설정 탭 설정"""
        # OCR 설정
        ocr_frame = ttk.LabelFrame(self.settings_tab, text="OCR 설정", padding=10)
        ocr_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(ocr_frame, text="DPI:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.dpi_var = tk.IntVar(value=self.config_manager.get_setting('dpi', 300))
        ttk.Spinbox(ocr_frame, from_=150, to=600, textvariable=self.dpi_var, width=10).grid(row=0, column=1, padx=(5, 0), pady=2)
        
        # API 설정
        api_settings_frame = ttk.LabelFrame(self.settings_tab, text="API 설정", padding=10)
        api_settings_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(api_settings_frame, text="일일 토큰 제한:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.token_limit_var = tk.IntVar(value=self.config_manager.get_setting('daily_token_limit', 2000000))
        ttk.Entry(api_settings_frame, textvariable=self.token_limit_var, width=15).grid(row=0, column=1, padx=(5, 0), pady=2)
        
        ttk.Label(api_settings_frame, text="배치 크기:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.batch_size_var = tk.IntVar(value=self.config_manager.get_setting('batch_size', 5))
        ttk.Spinbox(api_settings_frame, from_=1, to=20, textvariable=self.batch_size_var, width=10).grid(row=1, column=1, padx=(5, 0), pady=2)
        
        ttk.Label(api_settings_frame, text="최대 재시도:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.max_retries_var = tk.IntVar(value=self.config_manager.get_setting('max_retries', 3))
        ttk.Spinbox(api_settings_frame, from_=1, to=10, textvariable=self.max_retries_var, width=10).grid(row=2, column=1, padx=(5, 0), pady=2)
        
        ttk.Label(api_settings_frame, text="타임아웃(초):").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.timeout_var = tk.IntVar(value=self.config_manager.get_setting('timeout_seconds', 60))
        ttk.Spinbox(api_settings_frame, from_=30, to=300, textvariable=self.timeout_var, width=10).grid(row=3, column=1, padx=(5, 0), pady=2)

        ttk.Label(api_settings_frame, text="모델명:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.model_var = tk.StringVar(value=self.config_manager.get_setting('base_model', 'gpt-5-mini'))
        ttk.Entry(api_settings_frame, textvariable=self.model_var, width=20).grid(row=4, column=1, padx=(5, 0), pady=2)
        
        # 출력 폴더 설정
        output_frame = ttk.LabelFrame(self.settings_tab, text="출력 설정", padding=10)
        output_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(output_frame, text="출력 폴더:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(output_frame, textvariable=self.output_folder_path, width=50).grid(row=0, column=1, padx=(5, 5), pady=2)
        ttk.Button(output_frame, text="찾아보기", command=self.select_output_folder).grid(row=0, column=2, pady=2)
        
        # 출력 폴더가 설정되지 않은 경우 현재 스크립트 폴더의 result 폴더를 기본값으로 설정
        if not self.output_folder_path.get():
            default_output = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'result')
            self.output_folder_path.set(default_output)
        
        # 설정 저장 버튼
        ttk.Button(self.settings_tab, text="설정 저장", command=self.save_settings).pack(pady=10)
    
    def update_api_key_ui(self):
        """API 키 섹션 UI 업데이트"""
        # 기존 위젯들 제거
        for widget in self.api_frame.winfo_children():
            widget.destroy()        # API 키 상태에 따라 UI 생성
        if self.config_manager.has_api_key():
            ttk.Label(self.api_frame, text="API 키가 저장되어 있습니다.").pack(anchor=tk.W)
            ttk.Button(self.api_frame, text="API 키 변경", command=self.change_api_key).pack(anchor=tk.W, pady=(5, 0))
        else:
            ttk.Label(self.api_frame, text="API 키가 설정되지 않았습니다.").pack(anchor=tk.W)
            ttk.Button(self.api_frame, text="API 키 설정", command=self.set_api_key).pack(anchor=tk.W, pady=(5, 0))
    
    def load_settings(self):
        """설정 로드"""
        output_folder = self.config_manager.get_setting('output_folder', '')
        if not output_folder:
            # 기본 출력 폴더를 현재 스크립트 폴더의 result 폴더로 설정
            output_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'result')
        self.output_folder_path.set(output_folder)
    
    def save_settings(self):
        """설정 저장"""
        self.config_manager.set_setting('dpi', self.dpi_var.get())
        self.config_manager.set_setting('daily_token_limit', self.token_limit_var.get())
        self.config_manager.set_setting('batch_size', self.batch_size_var.get())
        self.config_manager.set_setting('max_retries', self.max_retries_var.get())
        self.config_manager.set_setting('timeout_seconds', self.timeout_var.get())
        self.config_manager.set_setting('output_folder', self.output_folder_path.get())
        self.config_manager.set_setting('base_model', self.model_var.get())
        messagebox.showinfo("설정", "설정이 저장되었습니다.")
    
    def select_single_pdf(self):
        """단일 PDF 파일 선택"""
        last_folder = self.config_manager.get_setting('last_pdf_folder', '')
        file_path = filedialog.askopenfilename(
            title="PDF 파일 선택",
            filetypes=[("PDF Files", "*.pdf")],
            initialdir=last_folder
        )
        if file_path:
            self.input_pdf_path.set(file_path)
            self.input_pdf_paths = [file_path]  # 단일 파일도 리스트로 저장
            self.config_manager.set_setting('last_pdf_folder', os.path.dirname(file_path))
            # 단일 선택 시 페이지 범위 활성화
            self.enable_page_range()
            self.log_debug_message(f"단일 PDF 선택: {os.path.basename(file_path)}")
    
    def select_multiple_pdfs(self):
        """복수 PDF 파일 선택"""
        last_folder = self.config_manager.get_setting('last_pdf_folder', '')
        file_paths = filedialog.askopenfilenames(
            title="PDF 파일들 선택 (복수 선택 가능)",
            filetypes=[("PDF Files", "*.pdf")],
            initialdir=last_folder
        )
        if file_paths:
            self.input_pdf_paths = list(file_paths)
            # 복수 선택 시 첫 번째 파일명과 개수를 표시
            display_text = f"{os.path.basename(file_paths[0])} 외 {len(file_paths)-1}개 파일"
            self.input_pdf_path.set(display_text)
            self.config_manager.set_setting('last_pdf_folder', os.path.dirname(file_paths[0]))
            # 복수 선택 시 페이지 범위 비활성화 및 전체 페이지로 설정
            self.disable_page_range_for_multiple()
            self.log_debug_message(f"복수 PDF 선택: {len(file_paths)}개 파일")
    
    def select_input_pdf(self):
        """기존 메서드 - 단일 선택으로 리다이렉트"""
        self.select_single_pdf()
    
    def enable_page_range(self):
        """페이지 범위 입력 활성화"""
        self.all_pages_check.config(state='normal')
        if not self.all_pages.get():
            self.start_spinbox.config(state='normal')
            self.end_spinbox.config(state='normal')
    
    def disable_page_range_for_multiple(self):
        """복수 파일 선택 시 페이지 범위 비활성화 및 전체 페이지로 설정"""
        self.all_pages.set(True)  # 전체 페이지로 강제 설정
        self.all_pages_check.config(state='disabled')  # 체크박스 비활성화
        self.start_spinbox.config(state='disabled')
        self.end_spinbox.config(state='disabled')
    
    def select_output_folder(self):
        """출력 폴더 선택"""
        folder_path = filedialog.askdirectory(
            title="출력 폴더 선택",
            initialdir=self.output_folder_path.get()
        )
        if folder_path:
            self.output_folder_path.set(folder_path)
    
    def set_api_key(self):
        """API 키 설정"""
        dialog = APIKeyDialog(self.root, "API 키 설정")
        if dialog.result:
            api_key = dialog.result  # 이제 API 키만 받음
            if self.config_manager.get_setting('api_key', api_key):
                messagebox.showinfo("성공", "API 키가 저장되었습니다.")
                self.update_api_key_ui()  # API 키 섹션만 업데이트
            else:
                messagebox.showerror("오류", "API 키 저장에 실패했습니다.")
    
    def change_api_key(self):
        """API 키 변경"""
        self.set_api_key()
    
    def get_api_key(self):
        """API 키 가져오기"""
        if not self.config_manager.has_api_key():
            messagebox.showerror("오류", "API 키가 설정되지 않았습니다.")
            return None
        api_key = self.config_manager.get_setting('api_key')
        if api_key:
            return api_key
        else:
            messagebox.showerror("오류", "API 키 가져오기에 실패했습니다.")
            return None

    def validate_inputs(self):
        """입력값 검증"""
        if not self.input_pdf_paths:  # 복수 파일 리스트 확인
            messagebox.showerror("오류", "PDF 파일을 선택해주세요.")
            return False
        
        # 출력 폴더 검증 및 자동 생성
        output_folder = self.output_folder_path.get()
        if not output_folder:
            # 출력 폴더가 설정되지 않은 경우 기본 폴더 사용
            default_output = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'result')
            self.output_folder_path.set(default_output)
            output_folder = default_output
        
        # 출력 폴더가 존재하지 않으면 생성
        try:
            os.makedirs(output_folder, exist_ok=True)
        except Exception as e:
            messagebox.showerror("오류", f"출력 폴더를 생성할 수 없습니다:\n{output_folder}\n\n오류: {str(e)}")
            return False
        
        # 단일 파일이고 전체 페이지가 아닌 경우에만 페이지 범위 검증
        if len(self.input_pdf_paths) == 1 and not self.all_pages.get():
            if self.start_page.get() > self.end_page.get():
                messagebox.showerror("오류", "시작 페이지가 끝 페이지보다 클 수 없습니다.")
                return False
        
        if not self.config_manager.has_api_key():
            messagebox.showerror("오류", "API 키를 설정해주세요.")
            return False
        
        return True
    
    def update_progress(self, message, percentage):
        """진행률 업데이트"""
        self.progress_var.set(message)
        self.progress_bar['value'] = percentage
        self.root.update_idletasks()
    
    def start_processing(self):
        """OCR 처리 시작"""
        if not self.validate_inputs():
            return
        
        # API 키 가져오기
        api_key = self.get_api_key()
        if not api_key:
            return
        
        # 토큰 제한 확인
        if not self.api_processor.check_token_limit():
            messagebox.showwarning("경고", "일일 토큰 제한을 초과했습니다.")
            return
          # UI 상태 변경
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.processing_cancelled = False
        
        # 별도 스레드에서 처리
        self.processing_thread = threading.Thread(target=self.process_ocr, args=(api_key,))
        self.processing_thread.daemon = True
        self.processing_thread.start()
    
    def stop_processing(self):
        """처리 중지"""
        self.processing_cancelled = True
        self.update_progress("처리 중지 중...", 0)
    
    def process_ocr(self, api_key):
        """OCR 처리 메인 함수 - 단일/복수 파일 처리 지원"""
        try:
            output_folder = self.output_folder_path.get()
            
            # 복수 파일 처리
            if len(self.input_pdf_paths) > 1:
                self.log_debug_message(f"복수 파일 처리 시작: {len(self.input_pdf_paths)}개 파일")
                self.process_multiple_pdfs(api_key, output_folder)
            else:
                # 단일 파일 처리
                input_pdf = self.input_pdf_paths[0]
                self.log_debug_message(f"단일 파일 처리 시작: {os.path.basename(input_pdf)}")
                self.process_single_pdf(api_key, input_pdf, output_folder)
                
        except Exception as e:
            if not self.processing_cancelled:
                self.handle_processing_error(e)
        finally:
            # UI 상태 복원
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
    
    def process_single_pdf(self, api_key, input_pdf, output_folder):
        """단일 PDF 파일 처리"""
        start_page, end_page = self.get_page_range()
        
        base_name = os.path.splitext(os.path.basename(input_pdf))[0]
        raw_json = os.path.join(output_folder, f"{base_name}_ocr_raw.json")
        corr_json = os.path.join(output_folder, f"{base_name}_ocr_corr.json")
        output_pdf = os.path.join(output_folder, f"{base_name}_recovered.pdf")
        
        # 1단계: OCR (완료 여부 확인 후 스킵 가능)
        if self.processing_cancelled:
            return

        if self.is_ocr_complete(input_pdf, raw_json, start_page, end_page):
            self.update_progress("기존 OCR 결과 재사용...", 15)
            self.log_debug_message("이미 완료된 OCR 결과를 스킵합니다.")
            with open(raw_json, 'r', encoding='utf-8') as f:
                blocks = json.load(f)
        else:
            self.update_progress("OCR 전처리 시작...", 10)
            self.log_debug_message("OCR 전처리 단계 시작")
            blocks = self.ocr_processor.preprocess_pdf(
                input_pdf, raw_json, start_page, end_page,
                progress_callback=lambda msg, pct: self.update_progress(msg, 10 + pct * 0.3)
            )
        
        # 2단계: API 교정 (완료 여부 확인 후 스킵 가능)
        if self.processing_cancelled:
            return
        if self.is_correction_complete(raw_json, corr_json):
            self.update_progress("기존 교정 결과 재사용...", 55)
            self.log_debug_message("이미 완료된 LLM 교정 결과를 스킵합니다.")
            with open(corr_json, 'r', encoding='utf-8') as f:
                corrected_blocks = json.load(f)
        else:
            reason = getattr(self, '_last_correction_incomplete_reason', None)
            if reason:
                self.log_debug_message(f"교정 재실행 사유: {reason}")
            self.update_progress("API 교정 시작...", 40)
            self.log_debug_message("API 교정 단계 시작")
            corrected_blocks = self.api_processor.recover_text_with_api(
                raw_json, corr_json, api_key,
                progress_callback=lambda msg, pct: self.update_progress(msg, 40 + pct * 0.4),
                log_callback=self.log_debug_message
            )
        
        # 3단계: PDF 오버레이 (이미 결과 PDF가 있고 교정 결과 길이 >0 이면 스킵)
        if self.processing_cancelled:
            return
        if os.path.exists(output_pdf) and corrected_blocks:
            self.update_progress("기존 PDF 오버레이 결과 존재 - 스킵", 90)
            self.log_debug_message("이미 생성된 PDF를 재사용합니다.")
        else:
            self.update_progress("PDF 오버레이 시작...", 80)
            self.log_debug_message("PDF 오버레이 단계 시작")
            self.pdf_processor.overlay_with_fitz(
                input_pdf, corrected_blocks, output_pdf,
                progress_callback=lambda msg, pct: self.update_progress(msg, 80 + pct * 0.2)
            )
        
        self.update_progress("처리 완료!", 100)
        self.log_debug_message(f"단일 파일 처리 완료: {output_pdf}")
        messagebox.showinfo("완료", f"OCR 처리가 완료되었습니다.\n\n출력 파일: {output_pdf}")
    
    def process_multiple_pdfs(self, api_key, output_folder):
        """복수 PDF 파일 처리"""
        total_files = len(self.input_pdf_paths)
        completed_files = []
        
        for i, input_pdf in enumerate(self.input_pdf_paths):
            if self.processing_cancelled:
                break
                
            file_progress_start = (i / total_files) * 100
            file_progress_range = (1 / total_files) * 100
            
            base_name = os.path.splitext(os.path.basename(input_pdf))[0]
            self.update_progress(f"파일 {i+1}/{total_files} 처리 중: {base_name}", file_progress_start)
            self.log_debug_message(f"파일 {i+1}/{total_files} 처리 시작: {base_name}")
            
            try:
                raw_json = os.path.join(output_folder, f"{base_name}_ocr_raw.json")
                corr_json = os.path.join(output_folder, f"{base_name}_ocr_corr.json")
                output_pdf = os.path.join(output_folder, f"{base_name}_recovered.pdf")
                
                # OCR 전처리 (전체 페이지) - 완료 시 스킵
                if self.is_ocr_complete(input_pdf, raw_json, None, None):
                    self.log_debug_message(f"{base_name}: 기존 OCR 결과 스킵")
                    with open(raw_json, 'r', encoding='utf-8') as f:
                        blocks = json.load(f)
                else:
                    self.log_debug_message(f"{base_name}: OCR 전처리 시작")
                    blocks = self.ocr_processor.preprocess_pdf(
                        input_pdf, raw_json, None, None,  # 전체 페이지
                        progress_callback=lambda msg, pct: self.update_progress(
                            f"파일 {i+1}/{total_files} OCR: {base_name}", 
                            file_progress_start + pct * 0.3 * file_progress_range / 100
                        )
                    )
                
                if self.processing_cancelled:
                    break
                  # API 교정
                if self.is_correction_complete(raw_json, corr_json):
                    self.log_debug_message(f"{base_name}: 기존 교정 결과 스킵")
                    with open(corr_json, 'r', encoding='utf-8') as f:
                        corrected_blocks = json.load(f)
                else:
                    reason = getattr(self, '_last_correction_incomplete_reason', None)
                    if reason:
                        self.log_debug_message(f"{base_name}: 교정 재실행 사유: {reason}")
                    self.log_debug_message(f"{base_name}: API 교정 시작")
                    corrected_blocks = self.api_processor.recover_text_with_api(
                        raw_json, corr_json, api_key,
                        progress_callback=lambda msg, pct: self.update_progress(
                            f"파일 {i+1}/{total_files} API: {base_name}", 
                            file_progress_start + (0.3 + pct * 0.4) * file_progress_range / 100
                        ),
                        log_callback=self.log_debug_message
                    )
                
                if self.processing_cancelled:
                    break
                
                # PDF 오버레이
                if os.path.exists(output_pdf) and corrected_blocks:
                    self.log_debug_message(f"{base_name}: 기존 PDF 결과 스킵")
                else:
                    self.log_debug_message(f"{base_name}: PDF 오버레이 시작")
                    self.pdf_processor.overlay_with_fitz(
                        input_pdf, corrected_blocks, output_pdf,
                        progress_callback=lambda msg, pct: self.update_progress(
                            f"파일 {i+1}/{total_files} PDF: {base_name}", 
                            file_progress_start + (0.7 + pct * 0.3) * file_progress_range / 100
                        )
                    )
                
                completed_files.append(output_pdf)
                self.log_debug_message(f"{base_name}: 처리 완료")
                
            except Exception as e:
                self.log_debug_message(f"{base_name}: 처리 중 오류 - {str(e)}")
                if "API_KEY_ERROR:" in str(e) or "QUOTA_ERROR:" in str(e):
                    # 심각한 오류는 전체 처리 중단
                    raise e
                # 그 외 오류는 해당 파일만 스킵
                continue
        
        if completed_files:
            self.update_progress("복수 파일 처리 완료!", 100)
            self.log_debug_message(f"복수 파일 처리 완료: {len(completed_files)}개 파일")
            messagebox.showinfo("완료", 
                              f"OCR 처리가 완료되었습니다.\n\n"
                              f"처리 완료: {len(completed_files)}개 파일\n"
                              f"출력 폴더: {output_folder}")
        else:
            self.update_progress("처리 실패", 0)
            self.log_debug_message("복수 파일 처리 실패")
    
    def handle_processing_error(self, e):
        """처리 중 오류 핸들링"""
        error_msg = str(e)
        
        # 다양한 API 오류 타입별 처리
        if "API_KEY_ERROR:" in error_msg:
            clean_msg = error_msg.replace("API_KEY_ERROR: ", "")
            messagebox.showerror("API 키 오류", clean_msg)
            self.update_progress("API 키 오류로 작업 중단", 0)
            self.log_debug_message(f"API 키 오류: {clean_msg}")
        elif "QUOTA_ERROR:" in error_msg:
            clean_msg = error_msg.replace("QUOTA_ERROR: ", "")
            messagebox.showerror("사용량 한도 초과", clean_msg)
            self.update_progress("사용량 한도 초과로 작업 중단", 0)
            self.log_debug_message(f"사용량 한도 초과: {clean_msg}")
        elif "MODEL_ERROR:" in error_msg:
            clean_msg = error_msg.replace("MODEL_ERROR: ", "")
            messagebox.showerror("모델 오류", clean_msg)
            self.update_progress("모델 오류로 작업 중단", 0)
            self.log_debug_message(f"모델 오류: {clean_msg}")
        elif "TOKEN_LIMIT_ERROR:" in error_msg:
            clean_msg = error_msg.replace("TOKEN_LIMIT_ERROR: ", "")
            messagebox.showerror("토큰 한도 초과", clean_msg)
            self.update_progress("토큰 한도 초과로 작업 중단", 0)
            self.log_debug_message(f"토큰 한도 초과: {clean_msg}")
        elif "NETWORK_ERROR:" in error_msg:
            clean_msg = error_msg.replace("NETWORK_ERROR: ", "")
            messagebox.showerror("네트워크 오류", clean_msg)
            self.update_progress("네트워크 오류로 작업 중단", 0)
            self.log_debug_message(f"네트워크 오류: {clean_msg}")
        elif "SERVER_ERROR:" in error_msg:
            clean_msg = error_msg.replace("SERVER_ERROR: ", "")
            messagebox.showerror("서버 오류", clean_msg)
            self.update_progress("서버 오류로 작업 중단", 0)
            self.log_debug_message(f"서버 오류: {clean_msg}")
        elif "UNKNOWN_API_ERROR:" in error_msg:
            clean_msg = error_msg.replace("UNKNOWN_API_ERROR: ", "")
            messagebox.showerror("API 오류", clean_msg)
            self.update_progress("알 수 없는 API 오류로 작업 중단", 0)
            self.log_debug_message(f"알 수 없는 API 오류: {clean_msg}")
        else:
            messagebox.showerror("오류", f"처리 중 오류가 발생했습니다:\n{error_msg}")
            self.update_progress("오류 발생", 0)
            self.log_debug_message(f"일반 오류: {error_msg}")

    def toggle_page_range(self):
        """전체 페이지 체크박스 토글 시 페이지 범위 입력 필드 활성화/비활성화"""
        if self.all_pages.get():
            # 전체 페이지 선택 시 입력 필드 비활성화
            self.start_spinbox.config(state='disabled')
            self.end_spinbox.config(state='disabled')
        else:
            # 전체 페이지 해제 시 입력 필드 활성화
            self.start_spinbox.config(state='normal')
            self.end_spinbox.config(state='normal')

    def get_page_range(self):
        """페이지 범위 가져오기 (전체 페이지인 경우 None, None 반환)"""
        if self.all_pages.get():
            return None, None  # 전체 페이지
        else:
            return self.start_page.get(), self.end_page.get()

    def toggle_debug_mode(self):
        """디버그 모드 토글 - 체크박스 상태에 따라 로그 창 표시/숨김"""
        if self.debug_mode.get():
            # 디버그 모드 활성화 - 로그 창 표시
            self.debug_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
            self.log_debug_message("디버그 모드가 활성화되었습니다.")
        else:
            # 디버그 모드 비활성화 - 로그 창 숨김
            self.debug_frame.pack_forget()
    
    def clear_debug_log(self):
        """디버그 로그 지우기"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def log_debug_message(self, message):
        """디버그 로그에 메시지 추가"""
        if self.debug_mode.get():
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}\n"
            
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, formatted_message)
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
            self.root.update_idletasks()

    # ====== 신규: 완료 여부 판단 유틸 ======
    def is_ocr_complete(self, input_pdf_path, raw_json_path, start_page, end_page):
        """이미 OCR이 완료되었는지 검사.
        기준:
          - raw_json 파일 존재 & 올바른 JSON (list)
          - 요청한 페이지 범위 내 모든 페이지 번호가 최소 1회 이상 등장 (빈 페이지는 예외적으로 빠질 수 있으니 허용 옵션 필요할 수 있으나 우선 엄격)
        """
        try:
            if not os.path.exists(raw_json_path):
                return False
            with open(raw_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, list) or len(data) == 0:
                return False
            doc = fitz.open(input_pdf_path)
            total_pages = len(doc)
            if start_page is None and end_page is None:
                expected_pages = set(range(1, total_pages + 1))
            else:
                s = start_page if start_page else 1
                e = end_page if end_page else total_pages
                expected_pages = set(range(s, e + 1))
            pages_present = {b.get('page') for b in data if isinstance(b, dict) and 'page' in b}
            missing = expected_pages - pages_present
            # 허용: 한 페이지도 블록이 없는 경우(완전히 빈 페이지) -> 일단 기본 정책으론 미싱 페이지 있으면 미완료
            if missing:
                self.log_debug_message(f"OCR 재실행: 누락 페이지 {sorted(list(missing))}")
                return False
            return True
        except Exception as e:
            self.log_debug_message(f"OCR 완료 판정 오류 -> 재실행: {e}")
            return False

    def is_correction_complete(self, raw_json_path, corr_json_path):
        """LLM 교정 완료 여부 판정.
        기준:
          - 두 파일 존재
          - 두 파일 모두 list
          - 길이 동일
          - 모든 항목에 text_corrected 키 존재
        """
        try:
            self._last_correction_incomplete_reason = None
            if not (os.path.exists(raw_json_path) and os.path.exists(corr_json_path)):
                self._last_correction_incomplete_reason = "결과 파일 없음"
                return False
            with open(raw_json_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            with open(corr_json_path, 'r', encoding='utf-8') as f:
                corr_data = json.load(f)
            if not (isinstance(raw_data, list) and isinstance(corr_data, list)):
                self._last_correction_incomplete_reason = "JSON 구조(list 아님)"
                return False
            if len(raw_data) == 0 or len(raw_data) != len(corr_data):
                self._last_correction_incomplete_reason = f"길이 불일치 raw={len(raw_data)} corr={len(corr_data)}"
                return False
            missing_key_count = sum(1 for b in corr_data if 'text_corrected' not in b)
            if missing_key_count:
                self._last_correction_incomplete_reason = f"text_corrected 누락 {missing_key_count}개"
                return False
            return True
        except Exception as e:
            self.log_debug_message(f"교정 완료 판정 오류 -> 재실행: {e}")
            self._last_correction_incomplete_reason = f"예외: {e}"
            return False

class APIKeyDialog:
    def __init__(self, parent, title):
        self.result = None
        
        # 다이얼로그 창 생성
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x150")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # 중앙에 위치
        self.dialog.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        
        # UI 구성
        frame = ttk.Frame(self.dialog, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="OpenAI API 키:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        self.api_key_entry = ttk.Entry(frame, width=50, show='*')
        self.api_key_entry.grid(row=1, column=0, pady=(0, 10))
        
        info_label = ttk.Label(frame, text="※ API 키는 평문으로 저장되므로, \nconfig.json 파일을 안전하게 보관하고 \n네트워크 공격에 노출된 곳에서 사용하지 마세요.", 
                              foreground="blue", font=("", 8))
        info_label.grid(row=2, column=0, sticky=tk.W, pady=(0, 15))
        
        # 버튼
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=3, column=0, sticky=tk.EW)
        
        ttk.Button(button_frame, text="확인", command=self.ok_clicked).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_frame, text="취소", command=self.cancel_clicked).pack(side=tk.RIGHT)
        
        # 엔터키 바인딩
        self.dialog.bind('<Return>', lambda e: self.ok_clicked())
        self.dialog.bind('<Escape>', lambda e: self.cancel_clicked())
        
        # 포커스 설정
        self.api_key_entry.focus()
        
        # 모달 대기
        self.dialog.wait_window()
    
    def ok_clicked(self):
        api_key = self.api_key_entry.get().strip()
        
        if not api_key:
            messagebox.showerror("오류", "API 키를 입력해주세요.", parent=self.dialog)
            return
        
        self.result = api_key  # 이제 API 키만 반환
        self.dialog.destroy()
    
    def cancel_clicked(self):
        self.dialog.destroy()


def main():
    root = tk.Tk()
    app = OCRApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
