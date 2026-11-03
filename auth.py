import hmac
import streamlit as st
from logger_utils import print  # 규칙에 따라 rich 기반의 커스텀 로거 임포트

def check_password() -> bool:
    """
    모임 정산 프로그램의 접근 보안을 위한 비밀번호 인증 함수입니다.
    
    동작 방식:
    1. Streamlit 세션 상태(st.session_state)에 인증 완료('authenticated' == True) 상태가 있으면 True 반환.
    2. 미인증 상태인 경우 깔끔한 로그인 카드 UI를 표시하고 st.stop()을 유도하기 위해 False 반환.
    3. 비밀번호는 .streamlit/secrets.toml 또는 Streamlit Cloud 대시보드의 Secrets(APP_PASSWORD)에서 읽어옵니다.
    
    Returns:
        bool: 인증 성공 여부 (True: 통과, False: 미인증 화면 표시 중)
    """
    # 1. 이미 로그인 인증된 세션인지 확인
    if st.session_state.get("authenticated", False):
        return True

    # 2. 설정된 비밀번호 획득 (Streamlit Secrets 우선, 없을 시 기본값 1234)
    target_password = None
    if "APP_PASSWORD" in st.secrets:
        target_password = str(st.secrets["APP_PASSWORD"])
    elif "password" in st.secrets:
        target_password = str(st.secrets["password"])
    else:
        # secrets 설정이 없을 경우 기본 비밀번호 안내
        target_password = "1234"

    # 3. 로그인 화면 렌더링 (화면 중앙 정렬 카드 디자인)
    _, center_col, _ = st.columns([1, 1.8, 1])
    
    with center_col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                    border: 1px solid #334155; border-radius: 16px; padding: 32px 28px;
                    text-align: center; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);">
            <div style="font-size: 40px; margin-bottom: 12px;">🔒</div>
            <h2 style="color: #38bdf8; margin: 0 0 8px 0; font-size: 24px;">모임 정산 프로그램</h2>
            <p style="color: #94a3b8; font-size: 14px; margin: 0 0 20px 0;">
                비공개 정산 내역 보호를 위해 비밀번호를 입력해주세요.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 비밀번호 입력 폼
        with st.form("login_form", clear_on_submit=False):
            input_pw = st.text_input("접속 비밀번호", type="password", placeholder="비밀번호를 입력하세요", key="login_pw_input")
            login_btn = st.form_submit_button("접속하기 🚀", use_container_width=True)
            
            if login_btn:
                # 타이밍 공격 방지를 위한 안전한 문자열 비교(hmac.compare_digest)
                if hmac.compare_digest(input_pw.strip(), target_password.strip()):
                    st.session_state["authenticated"] = True
                    print("[green]비밀번호 인증 성공: 메인 화면으로 진입합니다.[/green]")
                    st.rerun()
                else:
                    st.session_state["authenticated"] = False
                    print(f"[red]비밀번호 인증 실패:[/red] 잘못된 비밀번호 입력 시도")
                    st.error("❌ 비밀번호가 올바르지 않습니다. 다시 입력해주세요.")
                    
        if "APP_PASSWORD" not in st.secrets and "password" not in st.secrets:
            st.info("💡 기본 비밀번호는 **`1234`** 로 설정되어 있습니다. (온라인 배포 시 Secrets에서 변경 가능)")
            
    return False

def render_logout_button() -> None:
    """
    사이드바 하단에 배치할 수 있는 로그아웃 버튼입니다.
    클릭 시 인증 세션을 초기화하고 로그인 화면으로 복귀합니다.
    """
    if st.session_state.get("authenticated", False):
        st.sidebar.markdown("---")
        if st.sidebar.button("로그아웃 🔒", use_container_width=True, help="접속 세션을 종료하고 잠금 화면으로 돌아갑니다."):
            st.session_state["authenticated"] = False
            print("[yellow]사용자가 로그아웃하였습니다.[/yellow]")
            st.rerun()

