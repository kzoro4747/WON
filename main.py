import streamlit as st
import pandas as pd
import json
from typing import List, Dict, Any
from datetime import datetime
from calculator import Family, Expense, SettlementCalculator
from logger_utils import print  # 규칙에 따라 rich 기반의 커스텀 로거 임포트

# -----------------------------------------------------------------------------
# 1. 페이지 설정 및 현대적인 스타일 정의
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="5가족 모임 정산 계산기 💸",
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
# 2. 세션 상태 (Session State) 초기화
# -----------------------------------------------------------------------------
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
    col1, col2, col3 = st.sidebar.columns([3, 2, 1])
    with col1:
        # 가족 이름 설정 (동적 바인딩)
        fam_name = st.text_input(f"가족 {i+1}", value=fam["name"], key=f"fam_name_{i}")
    with col2:
        # 가족별 인원수 설정
        fam_count = st.number_input(f"인원수", min_value=1, max_value=20, value=fam["member_count"], key=f"fam_count_{i}")
    with col3:
        # 공간 패딩용 빈 공간 출력 후 ❌ 버튼 배치 (수직 정렬을 정밀하게 맞추기 위해 마진 설정)
        st.markdown("<div style='margin-top: 18px;'></div>", unsafe_allow_html=True)
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
    add_name = st.text_input("새 가족 이름", placeholder="예: 지원")
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
                # 1. UI 위젯 캐시 충돌 방지를 위해 기존 sidebar 관련 세션 키 일괄 제거
                for key in list(st.session_state.keys()):
                    if key.startswith("fam_name_") or key.startswith("fam_count_") or key.startswith("check_part_"):
                        del st.session_state[key]
                
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


# -----------------------------------------------------------------------------
# 4. 메인 화면 UI 레이아웃
# -----------------------------------------------------------------------------
st.title(f"💸 {len(families_list)}가족 모임 지출 정산 프로그램")
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
            memo=exp_dict.get("memo", "")  # 메모 복원 추가
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
            st.rerun()
            
        edit_exp = st.session_state.expenses_data[editing_idx]
        default_item = edit_exp["item_name"]
        default_payer = edit_exp["payer_name"] if edit_exp["payer_name"] in family_names else family_names[0]
        default_amount = int(edit_exp["amount"])
        default_split = "참여 인원수 비례 분담" if edit_exp.get("split_by_member", False) else "가족수 기준 균등 분담 (N분의 1)"
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

    with st.form("expense_input_form", clear_on_submit=True):
        col_item, col_payer = st.columns(2)
        with col_item:
            item_name = st.text_input("지출 항목명", value=default_item, placeholder="예: 첫날 장보기, 숙박비, 카페")
        with col_payer:
            # 기본값 인덱스 계산
            payer_index = family_names.index(default_payer) if default_payer in family_names else 0
            payer_name = st.selectbox("지불한 가족", options=family_names, index=payer_index)
            
        col_amount, col_split = st.columns(2)
        with col_amount:
            amount = st.number_input("지출 금액 (원)", min_value=0, step=1000, value=default_amount, format="%d")
        with col_split:
            split_index = 0 if default_split == "가족수 기준 균등 분담 (N분의 1)" else 1
            split_method = st.radio(
                "분담 기준",
                options=["가족수 기준 균등 분담 (N분의 1)", "참여 인원수 비례 분담"],
                index=split_index,
                help="인원수 비례 분담을 선택하면 각 가족의 머릿수에 비례하여 금액을 책정합니다."
            )
            split_by_member = (split_method == "참여 인원수 비례 분담")
            
        # 메모 입력 칸 추가
        memo = st.text_input("메모 (세부내역 등)", value=default_memo, placeholder="예: A동 302호 예약금, 마트 소고기 구입 등")
        
        st.write("🎯 **지출에 참여한 가족 선택:**")
        # 체크박스 상태 바인딩
        checkbox_cols = st.columns(len(family_names))
        selected_participants = []
        for idx, name in enumerate(family_names):
            with checkbox_cols[idx]:
                # 수정 모드라면 해당 지출에 들어있던 멤버인지 여부를 기본값으로 제공
                is_checked = name in default_participants
                if st.checkbox(name, value=is_checked, key=f"check_part_{name}"):
                    selected_participants.append(name)
                    
        submitted = st.form_submit_button("수정 완료 💾" if is_edit_mode else "추가하기 💳")
        
        if submitted:
            if not item_name.strip():
                st.error("지출 항목명을 입력해주세요.")
            elif amount <= 0:
                st.error("올바른 지출 금액을 입력해주세요.")
            elif not selected_participants:
                st.error("최소 한 팀 이상의 참여 가족을 지정해야 합니다.")
            else:
                new_expense = {
                    "item_name": item_name.strip(),
                    "payer_name": payer_name,
                    "amount": int(amount),
                    "participants": selected_participants,
                    "split_by_member": split_by_member,
                    "memo": memo.strip()
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
                st.rerun()

    st.markdown("---")
    st.subheader("📋 등록된 지출 목록")
    
    if not st.session_state.expenses_data:
        st.info("등록된 지출 내역이 없습니다. 지출을 추가해 주세요.")
    else:
        # 데이터프레임 형식으로 지출 내역 시각화 (메모 컬럼 추가)
        display_list = []
        for idx, exp in enumerate(st.session_state.expenses_data):
            display_list.append({
                "번호": idx + 1,
                "항목명": exp["item_name"],
                "메모": exp.get("memo", ""),  # 메모 컬럼
                "지불자": exp["payer_name"],
                "금액": f"{exp['amount']:,}원",
                "참여가족": ", ".join(exp["participants"]),
                "정산기준": "인원수비례" if exp.get("split_by_member", False) else "1/N"
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
            st.markdown("#### **최적 송금 가이드 (송금 최소화)**")
            
            optimal_transfers = calculator.get_optimal_transfers()
            
            if not optimal_transfers:
                st.success("🎉 모든 가족의 정산 상태가 균형을 이루고 있습니다! 송금할 내역이 없습니다.")
            else:
                for debtor, creditor, amt in optimal_transfers:
                    st.markdown(f"""
                    <div class="transfer-card">
                        <div>
                            <strong>{debtor}</strong> 
                            <span class="transfer-arrow">➔</span> 
                            <strong>{creditor}</strong>
                        </div>
                        <div class="transfer-amount">{amt:,} 원</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # -------------------------------------------------------------
                # 5. 카카오톡/메신저 공유용 텍스트 자동 생성
                # -------------------------------------------------------------
                st.markdown("#### 💬 **카카오톡 공유용 공지 텍스트**")
                
                # 텍스트 포맷 생성
                notice_text = f"📢 [{len(calculator.families)}가족 모임 정산 결과 안내]\n"
                notice_text += f"━━━━━━━━━━━━━━━━━━━━━\n"
                notice_text += f"📅 정산일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                notice_text += f"💵 총 지출액: {total_spent:,}원\n\n"
                
                notice_text += f"👤 가족 구성 정보:\n"
                for name, fam in calculator.families.items():
                    notice_text += f" - {name}: {fam.member_count}명\n"
                notice_text += "\n"
                
                notice_text += f"📊 지출 항목 요약:\n"
                for idx, exp in enumerate(st.session_state.expenses_data):
                    memo_str = f" [{exp.get('memo')}]" if exp.get("memo") else ""
                    notice_text += f" {idx+1}. {exp['item_name']}{memo_str} ({exp['payer_name']} 지불): {exp['amount']:,}원\n"
                notice_text += "\n"
                
                notice_text += f"💸 송금 요청 내역 (수수료 절약/최소 거래):\n"
                for debtor, creditor, amt in optimal_transfers:
                    notice_text += f" 👉 {debtor} ➔ {creditor} : {amt:,}원\n"
                notice_text += f"━━━━━━━━━━━━━━━━━━━━━\n"
                notice_text += f"정산 내역을 확인해 주시고 이상이 없을 시 송금 부탁드립니다. 감사합니다! 🙏"
                
                st.text_area("공지 텍스트 복사하기 (아래 박스 전체 복사)", value=notice_text, height=250)
                st.info("💡 위의 텍스트 영역을 클릭해 전체 복사(Ctrl+A -> Ctrl+C)하여 단톡방에 올리시면 정산 안내가 한 번에 끝납니다!")
