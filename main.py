import streamlit as st
import pandas as pd
import json
from typing import List, Dict, Any
from datetime import datetime
from calculator import Family, Expense, SettlementCalculator
from logger_utils import print  # 규칙에 따라 rich 기반의 커스텀 로거 임포트
from image_generator import generate_settlement_image
from auth import check_password, render_logout_button  # 접속 비밀번호 인증 모듈 임포트

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 현대적인 스타일 정의
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="모임 지출 정산 프로그램 💸",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Premium UI 스타일링을 위한 Custom CSS 주입
st.markdown("""
<style>
    /* 전체 배경 및 폰트 스타일 */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Noto+Sans+KR:wght@300;400;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', 'Noto Sans KR', sans-serif;
    }
    
    /* 카드 디자인 */
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
        color: #f8fafc;
        margin-bottom: 20px;
    }
    .metric-card-title {
        font-size: 14px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 8px;
    }
    .metric-card-value {
        font-size: 32px;
        font-weight: 800;
        color: #38bdf8;
    }
    
    /* 송금 카드 */
    .transfer-card {
        background: rgba(56, 189, 248, 0.08);
        border-left: 5px solid #38bdf8;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .transfer-arrow {
        color: #f43f5e;
        font-weight: bold;
        margin: 0 10px;
    }
    .transfer-amount {
        font-size: 18px;
        font-weight: 700;
        color: #10b981;
    }
    
    /* 버튼 둥글게 */
    div.stButton > button {
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    div.stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(56, 189, 248, 0.2);
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 1.1. 비밀번호 인증 검사 (비공개 정산 내역 보호)
# -----------------------------------------------------------------------------
if not check_password():
    st.stop()


# -----------------------------------------------------------------------------
# 2. 세션 상태 (Session State) 초기화
# -----------------------------------------------------------------------------
if "expense_widget_key" not in st.session_state:
    st.session_state.expense_widget_key = 0
if "family_widget_key" not in st.session_state:
    st.session_state.family_widget_key = 0

# 기본값으로 사용자 요청에 맞추어 5가족 기본 데이터 로드 (가율, 소율, 서아, 시윤, 은율)
if "families_data" not in st.session_state:
    st.session_state.families_data = [
        {"name": "가율", "member_count": 4},
        {"name": "소율", "member_count": 3},
        {"name": "서아", "member_count": 4},
        {"name": "시윤", "member_count": 4},
        {"name": "은율", "member_count": 4}
    ]

if "expenses_data" not in st.session_state:
    st.session_state.expenses_data = []

if "editing_index" not in st.session_state:
    st.session_state.editing_index = None

if "last_payer" not in st.session_state:
    st.session_state.last_payer = "가율"

print("[green]main.py 실행 - 세션 상태 로드 완료[/green]")


# -----------------------------------------------------------------------------
# 3. 사이드바: 가족 구성 및 데이터 관리
# -----------------------------------------------------------------------------
st.sidebar.title("👥 가족 구성원 관리")
st.sidebar.write("가족 목록을 수정, 추가 또는 삭제할 수 있습니다.")

# 가족 삭제 작업 처리
to_delete = None
updated_families = []

for i, fam in enumerate(st.session_state.families_data):
    col1, col2, col3 = st.sidebar.columns([3.2, 2.2, 1.2])
    with col1:
        # 가족 이름 설정 (동적 바인딩)
        fam_name = st.text_input(f"가족 {i+1}", value=fam["name"], key=f"fam_name_{i}_{st.session_state.family_widget_key}")
    with col2:
        # 가족별 인원수 설정
        fam_count = st.number_input(f"인원수", min_value=1, max_value=20, value=fam["member_count"], key=f"fam_count_{i}_{st.session_state.family_widget_key}")
    with col3:
        # 공간 패딩용 빈 공간 출력 후 ❌ 버튼 배치 (수직 및 수평 정렬을 정밀하게 맞추기 위해 마진 설정)
        st.markdown("<div style='margin-top: 18px; margin-left: -10px;'></div>", unsafe_allow_html=True)
        if st.button("❌", key=f"fam_del_{i}", help=f"{fam['name']} 가족 삭제"):
            to_delete = i
    
    updated_families.append({"name": fam_name, "member_count": fam_count})

# 변경된 리스트 실시간 반영
st.session_state.families_data = updated_families

# 삭제 버튼이 클릭되었을 때의 처리
if to_delete is not None:
    deleted_fam = st.session_state.families_data.pop(to_delete)
    print(f"[yellow]사용자 조작으로 가족 삭제됨:[/yellow] {deleted_fam['name']}")
    st.rerun()

# 새 가족 추가 폼
st.sidebar.markdown("---")
st.sidebar.write("➕ **새로운 가족 추가**")
with st.sidebar.form("add_family_form", clear_on_submit=True):
    add_name = st.text_input("새 가족 이름", placeholder="예: 개똥이")
    add_count = st.number_input("가족 인원수", min_value=1, max_value=20, value=4)
    add_btn = st.form_submit_button("가족 추가 👤")
    
    if add_btn:
        if not add_name.strip():
            st.sidebar.error("이름을 입력해주세요.")
        elif any(f["name"] == add_name.strip() for f in st.session_state.families_data):
            st.sidebar.error("이미 존재하는 가족 이름입니다.")
        else:
            st.session_state.families_data.append({
                "name": add_name.strip(),
                "member_count": int(add_count)
            })
            print(f"[green]사용자 조작으로 가족 추가됨:[/green] {add_name} ({add_count}명)")
            st.rerun()

# 계산기 도메인용 객체 리스트 생성
families_list = [Family(f["name"], f["member_count"]) for f in st.session_state.families_data]
family_names = [f.name for f in families_list]

st.sidebar.markdown("---")
st.sidebar.title("💾 데이터 저장 및 불러오기")

# JSON 다운로드 기능 (현재 데이터 백업)
backup_data = {
    "families": st.session_state.families_data,
    "expenses": st.session_state.expenses_data
}
json_string = json.dumps(backup_data, ensure_ascii=False, indent=4)
st.sidebar.download_button(
    label="📥 정산 내역 백업 파일 다운로드",
    file_name=f"settlement_backup_{datetime.now().strftime('%Y%m%d')}.json",
    mime="application/json",
    data=json_string
)

# JSON 업로드 기능 (이전 정산 내역 로드)
uploaded_file = st.sidebar.file_uploader("📂 이전 정산 파일 가져오기", type="json")
if uploaded_file is not None:
    # 무한 rerun 루프를 방지하기 위해 파일의 고유 식별 키 생성
    file_load_key = f"loaded_{uploaded_file.name}_{uploaded_file.size}"
    
    # 이 파일을 아직 로드하지 않은 상태일 때만 불러오기 수행
    if file_load_key not in st.session_state:
        try:
            loaded_data = json.load(uploaded_file)
            if "families" in loaded_data and "expenses" in loaded_data:
                # 1. UI 위젯 캐시 충돌 방지를 위해 위젯 키 재생성 플래그 증가
                st.session_state.family_widget_key += 1
                st.session_state.expense_widget_key += 1
                
                # 2. 구버전 백업 파일의 누락된 필드(memo, split_by_member 등) 안전 보정
                for exp in loaded_data["expenses"]:
                    if "memo" not in exp:
                        exp["memo"] = ""
                    if "split_by_member" not in exp:
                        exp["split_by_member"] = False
                        
                st.session_state.families_data = loaded_data["families"]
                st.session_state.expenses_data = loaded_data["expenses"]
                st.session_state.editing_index = None
                
                # 로드 성공 시 세션 상태에 플래그 기록 (다음 프레임에서 무한 로딩 차단)
                st.session_state[file_load_key] = True
                
                print(f"[green]백업 데이터 로드 성공 및 무한 리런 방지 세팅 완료 (파일명: {uploaded_file.name})[/green]")
                st.sidebar.success("성공적으로 복구되었습니다! 화면을 새로고침 중입니다.")
                st.rerun()
        except Exception as e:
            st.sidebar.error("올바르지 않은 백업 파일 형식입니다.")
            print(f"[red]백업 로드 에러:[/red] {str(e)}")

# 로그아웃 버튼 배치
render_logout_button()


# -----------------------------------------------------------------------------
# 4. 메인 화면 UI 레이아웃
# -----------------------------------------------------------------------------
st.title("💸 모임 지출 정산 프로그램")
st.markdown("가족들의 모임 지출을 쉽고 투명하게 계산하고, 송금 경로를 최소화하여 깔끔한 결과를 얻으세요!")

# 계산기 인스턴스 생성 및 세션 상태에 저장된 지출 내역 복원
calculator = SettlementCalculator(families_list)
for exp_dict in st.session_state.expenses_data:
    try:
        expense = Expense(
            item_name=exp_dict["item_name"],
            payer_name=exp_dict["payer_name"],
            amount=exp_dict["amount"],
            participants=exp_dict["participants"],
            split_by_member=exp_dict.get("split_by_member", False),
            memo=exp_dict.get("memo", ""),  # 메모 복원 추가
            custom_shares=exp_dict.get("custom_shares", None)  # 사용자 지정 비율 복원 추가
        )
        calculator.add_expense(expense)
    except Exception as e:
        print(f"[red]지출 복원 에러:[/red] {str(e)}")

# 좌우 레이아웃 분할
col_left, col_right = st.columns([5, 6])

# -----------------------------------------------------------------------------
# 4.1. 왼쪽 컬럼: 신규 지출 등록 / 수정 및 지출 내역 목록
# -----------------------------------------------------------------------------
with col_left:
    # 수정 모드 체크 및 타이틀/기본값 로드
    editing_idx = st.session_state.editing_index
    is_edit_mode = editing_idx is not None and editing_idx < len(st.session_state.expenses_data)
    
    if is_edit_mode:
        st.subheader(f"📝 지출 내역 수정 (번호: {editing_idx + 1})")
        # 수정 모드일 때 취소할 수 있는 버튼 제공
        if st.button("수정 모드 취소 ❌"):
            st.session_state.editing_index = None
            st.session_state.expense_widget_key += 1
            st.rerun()
            
        edit_exp = st.session_state.expenses_data[editing_idx]
        default_item = edit_exp["item_name"]
        default_payer = edit_exp["payer_name"] if edit_exp["payer_name"] in family_names else family_names[0]
        default_amount = int(edit_exp["amount"])
        
        # 분담 유형 파싱
        if edit_exp.get("custom_shares") is not None and len(edit_exp["custom_shares"]) > 0:
            default_split = "사용자 지정 비율 분담 (%)"
        elif edit_exp.get("split_by_member", False):
            default_split = "참여 인원수 비례 분담"
        else:
            default_split = "가족수 기준 균등 분담 (N분의 1)"
            
        default_participants = edit_exp["participants"]
        default_memo = edit_exp.get("memo", "")
    else:
        st.subheader("➕ 신규 지출 내역 추가")
        default_item = ""
        if "last_payer" in st.session_state and st.session_state.last_payer in family_names:
            default_payer = st.session_state.last_payer
        else:
            default_payer = family_names[0] if family_names else ""
        default_amount = 0
        default_split = "가족수 기준 균등 분담 (N분의 1)"
        default_participants = family_names
        default_memo = ""

    # st.form 대신 일반 container를 사용하여 위젯 상태 변경에 따른 실시간 화면 Rerun이 가능하도록 합니다.
    # 이를 통해 '사용자 지정 비율 분담 (%)'을 선택했을 때 비율 입력 칸이 즉시 하단에 활성화됩니다.
    with st.container():
        col_item, col_payer = st.columns(2)
        with col_item:
            item_name = st.text_input("지출 항목명", value=default_item, placeholder="예: 첫날 장보기, 숙박비, 카페", key=f"expense_input_item_name_{st.session_state.expense_widget_key}")
        with col_payer:
            # 기본값 인덱스 계산
            payer_index = family_names.index(default_payer) if default_payer in family_names else 0
            payer_name = st.selectbox("지불한 가족", options=family_names, index=payer_index, key=f"expense_input_payer_name_{st.session_state.expense_widget_key}")
            
        col_amount, col_split = st.columns(2)
        with col_amount:
            amount = st.number_input("지출 금액 (원)", min_value=0, step=1000, value=default_amount, format="%d", key=f"expense_input_amount_{st.session_state.expense_widget_key}")
        with col_split:
            if default_split == "가족수 기준 균등 분담 (N분의 1)":
                split_index = 0
            elif default_split == "참여 인원수 비례 분담":
                split_index = 1
            else:
                split_index = 2
                
            split_method = st.radio(
                "분담 기준",
                options=["가족수 기준 균등 분담 (N분의 1)", "참여 인원수 비례 분담", "사용자 지정 비율 분담 (%)"],
                index=split_index,
                key=f"expense_input_split_method_{st.session_state.expense_widget_key}",
                help="가족별로 직접 비율(%)을 지정하려면 '사용자 지정 비율 분담 (%)'을 선택하세요."
            )
            split_by_member = (split_method == "참여 인원수 비례 분담")
            
        # 메모 입력 칸 추가
        memo = st.text_input("메모 (세부내역 등)", value=default_memo, placeholder="예: A동 302호 예약금, 마트 소고기 구입 등", key=f"expense_input_memo_{st.session_state.expense_widget_key}")
        
        st.write("🎯 **지출에 참여한 가족 선택:**")
        # 체크박스 상태 바인딩 (key 충돌 및 혼선 방지를 위해 key 형태 보정)
        checkbox_cols = st.columns(len(family_names))
        selected_participants = []
        for idx, name in enumerate(family_names):
            with checkbox_cols[idx]:
                # 수정 모드라면 해당 지출에 들어있던 멤버인지 여부를 기본값으로 제공
                is_checked = name in default_participants
                if st.checkbox(name, value=is_checked, key=f"check_part_box_{idx}_{name}_{st.session_state.expense_widget_key}"):
                    selected_participants.append(name)
                    
        # 사용자 지정 비율 분담을 위한 % 값 입력 위젯
        custom_shares = {}
        if split_method == "사용자 지정 비율 분담 (%)" and len(selected_participants) > 0:
            st.markdown("##### 📊 **가족별 분담 비율 (%) 직접 입력**")
            
            # 이전 저장된 비율 데이터 딕셔너리 불러오기
            saved_shares = {}
            if is_edit_mode and edit_exp.get("custom_shares"):
                saved_shares = edit_exp["custom_shares"]
                
            # 한 줄에 2개씩 배치하여 충분한 가로폭을 확보하고, squish 현상을 방지합니다.
            cols_per_row = 2
            row_cols = None
            for idx, name in enumerate(selected_participants):
                if idx % cols_per_row == 0:
                    row_cols = st.columns(cols_per_row)
                with row_cols[idx % cols_per_row]:
                    # 기본값은 공평하게 균등 분할
                    even_split = round(100.0 / len(selected_participants), 1)
                    init_share = float(saved_shares.get(name, even_split))
                    
                    val = st.number_input(
                        f"{name} (%)",
                        min_value=0.0,
                        max_value=100.0,
                        step=1.0,
                        value=init_share,
                        key=f"share_pct_val_{idx}_{name}_{st.session_state.expense_widget_key}",
                        format="%.1f"
                    )
                    custom_shares[name] = val
            
            # 입력된 비율의 실시간 합계 출력
            current_sum = sum(custom_shares.values())
            if abs(current_sum - 100.0) < 0.01:
                st.success(f"현재 비율 합계: **{current_sum:.1f}%** (정산 가능합니다! ✅)")
            else:
                st.warning(f"현재 비율 합계: **{current_sum:.1f}%** (합계가 정확히 100.0%가 되어야 합니다. ⚠️)")
                    
        submitted = st.button("수정 완료 💾" if is_edit_mode else "추가하기 💳", use_container_width=True)
        
        if submitted:
            if not item_name.strip():
                st.error("지출 항목명을 입력해주세요.")
            elif amount <= 0:
                st.error("올바른 지출 금액을 입력해주세요.")
            elif not selected_participants:
                st.error("최소 한 팀 이상의 참여 가족을 지정해야 합니다.")
            elif split_method == "사용자 지정 비율 분담 (%)" and abs(sum(custom_shares.values()) - 100.0) > 0.01:
                st.error(f"비율의 합이 {sum(custom_shares.values()):.1f}% 입니다. 사용자 지정 비율 분담 시 비율의 총합은 반드시 정확히 100.0%가 되어야 합니다.")
            else:
                new_expense = {
                    "item_name": item_name.strip(),
                    "payer_name": payer_name,
                    "amount": int(amount),
                    "participants": selected_participants,
                    "split_by_member": split_by_member,
                    "memo": memo.strip(),
                    "custom_shares": custom_shares if split_method == "사용자 지정 비율 분담 (%)" else None
                }
                
                if is_edit_mode:
                    st.session_state.expenses_data[editing_idx] = new_expense
                    st.session_state.editing_index = None # 에디트 모드 종료
                    st.session_state.last_payer = payer_name # 마지막 지불자 콤보박스 유지
                    print(f"[green]사용자 조작으로 지출 내역 수정 완료:[/green] {new_expense}")
                    st.success("지출 내역이 성공적으로 수정되었습니다!")
                else:
                    st.session_state.expenses_data.append(new_expense)
                    st.session_state.last_payer = payer_name # 마지막 지불자 콤보박스 유지
                    print(f"[green]사용자 입력으로 지출 등록됨:[/green] {new_expense}")
                    st.success(f"'{item_name}' 지출 내역이 성공적으로 추가되었습니다!")
                
                # 위젯 상태 클리어를 위해 key를 재생성 (새로운 위젯으로 인식시켜 초기화)
                st.session_state.expense_widget_key += 1
                        
                st.rerun()

    st.markdown("---")
    st.subheader("📋 등록된 지출 목록")
    
    if not st.session_state.expenses_data:
        st.info("등록된 지출 내역이 없습니다. 지출을 추가해 주세요.")
    else:
        # 데이터프레임 형식으로 지출 내역 시각화 (메모 컬럼 추가)
        display_list = []
        for idx, exp in enumerate(st.session_state.expenses_data):
            if exp.get("custom_shares") is not None and len(exp["custom_shares"]) > 0:
                shares_dict = exp["custom_shares"]
                shares_str = ", ".join(f"{p} {float(shares_dict.get(p, 0)):g}%" for p in exp["participants"])
                split_desc = f"비율분담 ({shares_str})"
            else:
                split_desc = "인원수비례" if exp.get("split_by_member", False) else "1/N"
                
            display_list.append({
                "번호": idx + 1,
                "항목명": exp["item_name"],
                "메모": exp.get("memo", ""),  # 메모 컬럼
                "지불자": exp["payer_name"],
                "금액": f"{exp['amount']:,}원",
                "참여가족": ", ".join(exp["participants"]),
                "정산기준": split_desc
            })
            
        df = pd.DataFrame(display_list)
        st.dataframe(df.set_index("번호"), use_container_width=True)
        
        # 지출 수정 및 삭제 관리 섹션
        st.write("🛠️ **지출 내역 관리:**")
        manage_col1, manage_col2, manage_col3 = st.columns([3, 1, 1])
        with manage_col1:
            # 관리 대상 지출 선택 드롭다운
            selected_target = st.selectbox(
                "대상 지출 선택",
                options=[(idx, f"{idx+1}. {exp['item_name']} ({exp['amount']:,}원)") for idx, exp in enumerate(st.session_state.expenses_data)],
                format_func=lambda x: x[1],
                key="expense_manager_select"
            )
        with manage_col2:
            if st.button("수정", key="edit_btn_active", use_container_width=True):
                st.session_state.editing_index = selected_target[0]
                st.session_state.expense_widget_key += 1
                st.rerun()
        with manage_col3:
            if st.button("삭제", key="del_btn_active", use_container_width=True):
                target_idx = selected_target[0]
                removed = st.session_state.expenses_data.pop(target_idx)
                print(f"[yellow]사용자 조작으로 지출 삭제됨:[/yellow] {removed}")
                st.warning(f"'{removed['item_name']}' 지출 내역이 삭제되었습니다.")
                
                # 에디팅 모드 인덱스 유효성 조정
                if st.session_state.editing_index == target_idx:
                    st.session_state.editing_index = None
                elif st.session_state.editing_index is not None and st.session_state.editing_index > target_idx:
                    st.session_state.editing_index -= 1
                    
                st.rerun()


# -----------------------------------------------------------------------------
# 4.2. 오른쪽 컬럼: 정산 결과 대시보드 및 복사용 공지 텍스트
# -----------------------------------------------------------------------------
with col_right:
    st.subheader("📊 정산 결과 대시보드")
    
    total_spent = sum(exp["amount"] for exp in st.session_state.expenses_data)
    
    # 1. 요약 메트릭 카드 렌더링
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-card-title">모임 총 지출액</div>
        <div class="metric-card-value">{total_spent:,} 원</div>
    </div>
    """, unsafe_allow_html=True)
    
    if not st.session_state.expenses_data:
        st.info("지출 내역을 입력하시면 정산 요약 대시보드가 활성화됩니다.")
    else:
        # 가족별 총 지불액 계산
        payer_summary = {name: 0 for name in family_names}
        for exp in st.session_state.expenses_data:
            payer_summary[exp["payer_name"]] += exp["amount"]
            
        # 순 잔액(Net Balance) 계산
        balances = calculator.calculate_balances()
        
        # UI 레이아웃으로 상세 정보 표시
        tab1, tab2 = st.tabs(["💰 가족별 지출/정산 요약", "💸 최적 송금 경로 결과"])
        
        with tab1:
            st.markdown("#### **가족별 상세 정산 내역**")
            summary_data = []
            for name in family_names:
                net = balances[name]
                status_text = ""
                if net > 0:
                    status_text = f"🟢 {int(round(net)):,}원 돌려받기"
                elif net < 0:
                    status_text = f"🔴 {int(round(-net)):,}원 보내기"
                else:
                    status_text = "⚪ 정산 완료"
                    
                summary_data.append({
                    "가족명": name,
                    "인원수": f"{calculator.families[name].member_count}명",
                    "실제 지출액": f"{payer_summary[name]:,}원",
                    "최종 정산 상태": status_text
                })
            
            summary_df = pd.DataFrame(summary_data)
            st.table(summary_df.set_index("가족명"))
            
            # 순 잔액 차트 시각화
            st.markdown("#### **가족별 순 잔액 (채권/채무 분포)**")
            balance_chart_data = pd.DataFrame({
                "가족": list(balances.keys()),
                "순 잔액 (원)": list(balances.values())
            })
            st.bar_chart(balance_chart_data.set_index("가족"), color="#38bdf8")

        with tab2:
            st.markdown("#### **최적 송금 가이드 (대표 수납자 중심)**")
            
            # 대표 수납자(총무) 지정 셀렉트박스 (자동 선정 또는 특정 가족 직접 지정)
            auto_manager = max(balances, key=lambda k: balances[k]) if balances else ""
            manager_options = ["자동 선정"] + family_names
            selected_manager_opt = st.selectbox(
                "👑 대표 수납자(총무) 지정",
                options=manager_options,
                index=0,
                format_func=lambda opt: f"자동 선정 ({auto_manager} - 최대 채권자)" if opt == "자동 선정" else opt,
                key="select_settlement_manager",
                help="지정한 가족이 정산금을 모두 수납받은 뒤, 더 많은 금액을 지출한(돌려받아야 할) 가족에게 다시 송금합니다."
            )
            
            # 실제 수납자 이름 결정
            active_manager = auto_manager if selected_manager_opt == "자동 선정" else selected_manager_opt
            optimal_transfers = calculator.get_optimal_transfers(manager_name=active_manager)
            
            if not optimal_transfers:
                st.success("🎉 모든 가족의 정산 상태가 균형을 이루고 있습니다! 송금할 내역이 없습니다.")
            else:
                st.caption(f"💡 현재 **[{active_manager}]** 가족이 대표 수납자로 지정되어 정산을 진행합니다.")
                for debtor, creditor, amt in optimal_transfers:
                    role_badge = "📥 수납자에게 입금" if creditor == active_manager else "📤 초과 지출자 환급"
                    st.markdown(f"""
                    <div class="transfer-card">
                        <div>
                            <span style="font-size: 12px; color: #94a3b8; margin-right: 8px;">[{role_badge}]</span>
                            <strong>{debtor}</strong> 
                            <span class="transfer-arrow">➔</span> 
                            <strong>{creditor}</strong>
                        </div>
                        <div class="transfer-amount">{amt:,} 원</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # 총무(대표 수납자) 기준 받는 금액 / 돌려주는 금액 / 최종 남는 금액 계산 및 표시
                manager_received = sum(amt for _, cred, amt in optimal_transfers if cred == active_manager)
                manager_paid_out = sum(amt for debt, _, amt in optimal_transfers if debt == active_manager)
                manager_remaining = manager_received - manager_paid_out
                
                # 총무의 기지출액 및 분담금
                manager_spent = payer_summary.get(active_manager, 0)
                manager_share = int(round(payer_summary.get(active_manager, 0) - balances.get(active_manager, 0.0)))
                
                if manager_remaining >= 0:
                    explanation_html = f"💡 <strong>최종 남는 금액 설명:</strong> 총무({active_manager}) 가족이 선결제한 금액(<strong>{manager_spent:,}원</strong>)에서 본인 분담금(<strong>{manager_share:,}원</strong>)을 제외하고 <strong>최종적으로 돌려받는(회수하는) 본인 몫의 정산금</strong>입니다."
                else:
                    explanation_html = f"💡 <strong>부족 금액 설명:</strong> 총무({active_manager}) 가족의 본인 분담금(<strong>{manager_share:,}원</strong>)에서 기지출액(<strong>{manager_spent:,}원</strong>)을 제외한 차액(<strong>{-manager_remaining:,}원</strong>)이 수납금 환급 과정에서 충당 완료되었습니다."
                
                st.markdown(f"""
                <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid #10b981; border-radius: 10px; padding: 16px; margin-top: 12px;">
                    <div style="font-size: 15px; font-weight: 700; color: #38bdf8; margin-bottom: 8px;">
                        👑 총무({active_manager}) 최종 정산 요약
                    </div>
                    <div style="font-size: 14px; color: #e2e8f0; line-height: 1.7;">
                        • 총 받는 금액 (수납): <strong>{manager_received:,} 원</strong><br>
                        • 총 돌려주는 금액 (환급): <strong>{manager_paid_out:,} 원</strong><br>
                        • 총무에게 최종으로 남는 금액: <strong style="color: #10b981; font-size: 17px;">{manager_remaining:,} 원</strong>
                    </div>
                    <div style="font-size: 12px; color: #94a3b8; margin-top: 10px; border-top: 1px dashed #334155; padding-top: 8px; line-height: 1.5;">
                        {explanation_html}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # -------------------------------------------------------------
                # 5. 정산 결과 이미지 카드 생성 및 다운로드
                # -------------------------------------------------------------
                st.markdown("---")
                st.markdown("#### 📸 **정산 결과 이미지 카드 생성**")
                st.write("단톡방이나 메신저에 한눈에 보이는 요약 카드로 공유하고 싶으시다면 아래 버튼을 눌러 이미지를 생성하세요.")
                
                # 이미지 생성 버튼
                if st.button("📸 정산 결과 이미지 카드 생성하기", key="btn_generate_image", use_container_width=True):
                    try:
                        # 이미지 생성 호출
                        allocated_summary = {name: payer_summary[name] - balances[name] for name in family_names}
                        img_bytes = generate_settlement_image(
                            families=calculator.families,
                            expenses=st.session_state.expenses_data,
                            transfers=optimal_transfers,
                            total_spent=total_spent,
                            allocated_summary=allocated_summary,
                            manager_name=active_manager
                        )
                        
                        # 화면에 생성된 이미지 미리보기 노출
                        st.image(img_bytes, caption="생성된 정산 결과 요약 카드 (우클릭하여 복사 가능)", use_container_width=True)
                        
                        # 다운로드 버튼 제공
                        st.download_button(
                            label="💾 이미지 파일 다운로드 (.png)",
                            data=img_bytes,
                            file_name=f"settlement_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                            mime="image/png",
                            use_container_width=True
                        )
                        st.success("🎉 이미지가 성공적으로 생성되었습니다! 다운로드 버튼을 눌러 저장해 주세요.")
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        st.error(f"이미지 생성 중 오류가 발생했습니다: {str(e)}")
                        print(f"[red]이미지 생성 오류:[/red] {str(e)}")
                
                # -------------------------------------------------------------
                # 6. 카카오톡/메신저 공유용 텍스트 자동 생성
                # -------------------------------------------------------------
                st.markdown("---")
                st.markdown("#### 💬 **카카오톡 공유용 공지 텍스트**")
                
                # 텍스트 포맷 생성
                notice_text = f"📢 [{len(calculator.families)}가족 모임 정산 결과 안내]\n"
                notice_text += f"━━━━━━━━━━━━━━━━━━━━━\n"
                notice_text += f"📅 정산일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                notice_text += f"💵 총 지출액: {total_spent:,}원\n"
                notice_text += f"👑 대표 수납자(총무): {active_manager}\n\n"
                
                notice_text += f"👤 가족 구성 정보:\n"
                for name, fam in calculator.families.items():
                    notice_text += f" - {name}: {fam.member_count}명\n"
                notice_text += "\n"
                
                notice_text += f"📊 지출 항목 요약:\n"
                for idx, exp in enumerate(st.session_state.expenses_data):
                    memo_str = f" [{exp.get('memo')}]" if exp.get("memo") else ""
                    participants_list = exp.get("participants", [])
                    participants_str = ", ".join(participants_list)
                    if exp.get("custom_shares") is not None and len(exp["custom_shares"]) > 0:
                        shares_dict = exp["custom_shares"]
                        shares_str = ", ".join(f"{p} {float(shares_dict.get(p, 0)):g}%" for p in participants_list)
                        split_info = f"비율분담: {shares_str}" if shares_str else "비율분담"
                    elif exp.get("split_by_member", False):
                        member_str = ", ".join(f"{p}({calculator.families[p].member_count}명)" for p in participants_list if p in calculator.families)
                        split_info = f"인원수비례: {member_str}" if member_str else "인원수비례"
                    else:
                        split_info = f"1/N: {participants_str}" if participants_str else "1/N"
                    notice_text += f" {idx+1}. {exp['item_name']}{memo_str} ({exp['payer_name']} 지불 / {split_info}): {exp['amount']:,}원\n"
                notice_text += "\n"
                
                notice_text += f"💸 송금 요청 내역 ({active_manager} 수납 중심):\n"
                for debtor, creditor, amt in optimal_transfers:
                    notice_text += f" 👉 {debtor} ➔ {creditor} : {amt:,}원\n"
                notice_text += "\n"
                notice_text += f"📌 총무({active_manager}) 최종 정산 요약:\n"
                notice_text += f" - 받는 금액 합계: {manager_received:,}원\n"
                notice_text += f" - 돌려주는 금액 합계: {manager_paid_out:,}원\n"
                notice_text += f" - 총무에게 최종 남는 금액: {manager_remaining:,}원\n"
                if manager_remaining >= 0:
                    notice_text += f"   (💡 총무가 선결제한 비용 {manager_spent:,}원에서 본인 분담금 {manager_share:,}원을 제외하고 최종 회수하는 정산금입니다.)\n"
                else:
                    notice_text += f"   (💡 총무 본인 분담금 {manager_share:,}원에서 선결제액 {manager_spent:,}원을 제외한 차액 {-manager_remaining:,}원이 충당 완료되었습니다.)\n"
                notice_text += f"━━━━━━━━━━━━━━━━━━━━━\n"
                notice_text += f"정산 내역을 확인해 주시고 이상이 없을 시 송금 부탁드립니다. 감사합니다! 🙏"
                
                st.text_area("공지 텍스트 복사하기 (아래 박스 전체 복사)", value=notice_text, height=250)
                st.info("💡 위의 텍스트 영역을 클릭해 전체 복사(Ctrl+A -> Ctrl+C)하여 단톡방에 올리시면 정산 안내가 한 번에 끝납니다!")
