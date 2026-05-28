import os
import sys
import inspect
from datetime import datetime
from typing import Any, Dict, Tuple
from rich.console import Console

# 전역 콘솔 및 파일 핸들러 캐시
# Key: 로그 파일명, Value: (터미널 콘솔, 파일 콘솔, 파일 객체)
_consoles: Dict[str, Tuple[Console, Console, Any]] = {}

def get_console_for_caller() -> Tuple[Console, Console, Any]:
    """
    이 함수를 호출한 상위 호출자 파일의 이름을 동적으로 알아내어,
    해당 파일명 기준의 로그 파일과 터미널에 동시에 출력할 수 있는 Console 객체를 반환합니다.
    
    Returns:
        Tuple[Console, Console, Any]: (터미널용 콘솔, 파일용 콘솔, 오픈된 파일 객체)
    """
    try:
        # 호출 스택을 탐색하여 print()를 호출한 소스 파일명을 가져옴
        # stack[0]: get_console_for_caller()
        # stack[1]: print() (아래 정의된 래퍼 함수)
        # stack[2]: 실제 로그를 기록하려는 파일 (예: main.py, calculator.py)
        frame = inspect.stack()[2]
        caller_file = frame.filename
        caller_name = os.path.splitext(os.path.basename(caller_file))[0]
    except Exception:
        # 스택 탐색 실패 시 기본값 지정
        caller_name = "app"
        
    # 날짜 포맷팅 (YYMMDD 형식)
    today = datetime.now().strftime("%y%m%d")
    log_filename = f"{caller_name}_{today}.log"
    
    # 캐시된 콘솔이 없는 경우 새로 생성
    if log_filename not in _consoles:
        # 1. 터미널 출력용 Rich Console 생성
        terminal_console = Console()
        
        # 2. 파일 저장용 Console 생성 (ANSI 이스케이프 태그 파싱을 비활성화하여 순수 텍스트로 저장)
        log_file = open(log_filename, "a", encoding="utf-8")
        file_console = Console(file=log_file, force_terminal=False, color_system=None)
        
        _consoles[log_filename] = (terminal_console, file_console, log_file)
        
    return _consoles[log_filename]

def print(*args: Any, **kwargs: Any) -> None:
    """
    rich 라이브러리의 print 문처럼 터미널에 포맷팅하여 출력하고,
    동시에 호출한 '코드파일명_YYMMDD.log' 파일에 타임스탬프와 함께 동일한 로그를 기록합니다.
    """
    # 호출자에 맞는 콘솔 객체 획득
    terminal, file_console, log_file = get_console_for_caller()
    
    # 로그 타임스탬프 생성
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    
    # 1. 터미널 출력 (풍부한 스타일 적용을 위해 앞부분에 회색조 타임스탬프 적용)
    terminal.print(f"[dim]{timestamp}[/dim]", *args, **kwargs)
    
    # 2. 파일 출력 (파일에는 마크업 기호나 스타일을 제거하여 텍스트만 기록되도록 함)
    file_console.print(timestamp, *args, **kwargs)
    
    # 즉시 파일에 쓰도록 flush
    log_file.flush()
