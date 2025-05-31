"""
GUI 애플리케이션 실행 테스트
"""
try:
    from gui_app import main
    print("GUI 애플리케이션을 시작합니다...")
    main()
except ImportError as e:
    print(f"모듈 임포트 오류: {e}")
    print("필요한 패키지가 설치되어 있는지 확인하세요.")
except Exception as e:
    print(f"실행 중 오류: {e}")
    import traceback
    traceback.print_exc()
