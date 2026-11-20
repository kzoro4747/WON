import streamlit as st
import pandas as pd
import json
from typing import List, Dict, Any
from datetime import datetime
from rich.markup import escape  # 사용자 입력(가족명·항목명 등)이 rich 마크업으로 해석되지 않도록 이스케이프
from calculator import Family, Expense, SettlementCalculator
from logger_utils import print  # 규칙에 따라 rich 기반의 커스텀 로거 임포트
from image_generator import generate_settlement_image
from auth import check_password, render_logout_button  # 접속 비밀번호 인증 모듈 임포트
from help_dialog import render_help_button  # 사이드바 맨 위 도움말 버튼 + 팝업


# 사용자 지정 비율 합계가 100%에서 이만큼(%p) '미만'으로 벗어나면 저장 허용.
# 예: 3가족 균등 33.3% × 3 = 99.9%. 비율은 계산기에서 정규화되고, 원 단위 반올림 차액은 최다 지출 가족(동점 시 총무)이 떠안습니다.
SHARE_SUM_TOLERANCE = 1.0


# -----------------------------------------------------------------------------
# 0. 가족 목록 ↔ 지출 내역 정합성 유지 헬퍼
#    지출 dict는 가족을 '이름'으로만 참조하므로, 가족 이름이 바뀌거나 가족이 삭제되면
#    지출 쪽도 함께 맞춰 주지 않으면 정산 계산에서 지출이 빠지거나 KeyError가 발생합니다.
# -----------------------------------------------------------------------------
def apply_family_renames(expenses: List[Dict[str, Any]], rename_map: Dict[str, str]) -> int:
    """
    가족 이름 변경 내역을 지출 목록 전체에 반영합니다. (리스트 안의 dict를 제자리에서 수정)

    갱신 대상:
        - payer_name   : 지불한 가족
        - participants : 참여 가족 목록
        - custom_shares: 사용자 지정 비율의 키(가족명)

    Args:
        expenses (List[Dict[str, Any]]): st.session_state.expenses_data
        rename_map (Dict[str, str]): {예전 이름: 새 이름}. 한 번의 rerun에서 바뀐 이름들을 동시에 적용하므로
            A→B, B→A처럼 서로 맞바꾸는 경우에도 연쇄 치환이 일어나지 않습니다.

    Returns:
        int: 이름이 하나라도 치환된 지출 건수 (로그 확인용)
    """
    changed_count = 0
    for exp in expenses:
        if exp["payer_name"] not in rename_map and not any(p in rename_map for p in exp["participants"]):
            continue
        exp["payer_name"] = rename_map.get(exp["payer_name"], exp["payer_name"])
        exp["participants"] = [rename_map.get(p, p) for p in exp["participants"]]
        if exp.get("custom_shares"):
            exp["custom_shares"] = {rename_map.get(k, k): v for k, v in exp["custom_shares"].items()}
        changed_count += 1
    return changed_count


def find_expenses_using_family(expenses: List[Dict[str, Any]], family_name: str) -> List[str]:
    """
    특정 가족이 지불자 또는 참여자로 들어 있는 지출의 항목명 목록을 돌려줍니다.
    가족 삭제 전에 호출하여, 사용 중인 가족이 삭제되어 지출이 정산에서 빠지는 일을 막는 데 씁니다.

    Args:
        expenses (List[Dict[str, Any]]): st.session_state.expenses_data
        family_name (str): 확인할 가족명

    Returns:
        List[str]: 해당 가족을 참조하는 지출의 item_name 목록 (없으면 빈 리스트)
    """
    return [
        exp["item_name"]
        for exp in expenses
        if exp["payer_name"] == family_name or family_name in exp["participants"]
    ]


def revert_invalid_family_renames(old_families: List[Dict[str, Any]], new_families: List[Dict[str, Any]]) -> List[str]:
    """
    사이드바에서 바뀐 가족 이름 중 허용되지 않는 변경을 원래 이름으로 되돌립니다. (new_families를 제자리에서 수정)

    거부 대상:
        - 빈 이름
        - 다른 가족과 같은 이름: 지출은 가족을 이름으로만 참조하므로, 허용하면 두 가족의 지출이 합쳐지고
          이름을 다시 바꿔도 한쪽으로 몰려 되돌릴 수 없게 됩니다.

    Args:
        old_families (List[Dict[str, Any]]): 이번 rerun 전의 st.session_state.families_data
        new_families (List[Dict[str, Any]]): 입력칸 값으로 새로 만든 가족 목록 (같은 순서·같은 길이)

    Returns:
        List[str]: 사용자에게 보여 줄 안내 문구 목록 (되돌린 변경이 없으면 빈 리스트)
    """
    errors: List[str] = []
    for i, (old_fam, new_fam) in enumerate(zip(old_families, new_families)):
        if new_fam["name"] == old_fam["name"]:
            continue
        other_names = [f["name"] for j, f in enumerate(new_families) if j != i]
        if not new_fam["name"]:
            errors.append(f"'{old_fam['name']}' 가족의 이름은 비워 둘 수 없어 원래 이름으로 되돌렸습니다.")
        elif new_fam["name"] in other_names:
            errors.append(f"'{new_fam['name']}'은(는) 이미 있는 가족 이름이라 '{old_fam['name']}'(으)로 되돌렸습니다.")
        else:
            continue
        new_fam["name"] = old_fam["name"]
    return errors


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
# 화면 왼쪽 상단(사이드바 맨 위)에 도움말 버튼 배치 → 누르면 세부 도움말 팝업
render_help_button()

st.sidebar.title("👥 가족 구성원 관리")
st.sidebar.write("가족 목록을 수정, 추가 또는 삭제할 수 있습니다.")

# 직전 실행에서 이름 변경을 되돌렸다면 그 이유를 한 번 표시 (되돌린 뒤 st.rerun()하므로 1회성 메시지로 전달)
rename_error_notice = st.session_state.pop("family_rename_error", None)
if rename_error_notice:
    st.sidebar.error(rename_error_notice)

# 가족 삭제 작업 처리
to_delete = None
updated_families = []
rename_map: Dict[str, str] = {}  # 이번 rerun에서 이름이 바뀐 가족 {예전 이름: 새 이름}

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
    
    # 앞뒤 공백은 이름으로 치지 않음 (새 가족 추가 폼과 같은 기준)
    updated_families.append({"name": fam_name.strip(), "member_count": fam_count})

# 빈 이름·다른 가족과 같은 이름으로의 변경은 원래 이름으로 되돌림 (지출이 합쳐져 복구할 수 없게 되는 것 방지)
rename_errors = revert_invalid_family_renames(st.session_state.families_data, updated_families)

# 검증을 통과한 이름 변경만 {예전 이름: 새 이름}으로 모음
for old_fam, new_fam in zip(st.session_state.families_data, updated_families):
    if new_fam["name"] != old_fam["name"]:
        rename_map[old_fam["name"]] = new_fam["name"]

# 변경된 리스트 실시간 반영
st.session_state.families_data = updated_families

# 가족 이름이 바뀐 경우 지출 내역(지불자/참여자/비율)에도 새 이름을 반영
if rename_map:
    renamed_expense_count = apply_family_renames(st.session_state.expenses_data, rename_map)
    if st.session_state.last_payer in rename_map:
        st.session_state.last_payer = rename_map[st.session_state.last_payer]
    # 직접 지정해 둔 대표 수납자(총무)도 새 이름을 따라가도록 갱신 (위젯 생성 전이므로 값 변경 가능)
    if st.session_state.get("select_settlement_manager") in rename_map:
        st.session_state.select_settlement_manager = rename_map[st.session_state.select_settlement_manager]
    print(f"[green]사용자 조작으로 가족 이름 변경됨:[/green] {escape(str(rename_map))} (지출 {renamed_expense_count}건에 반영)")

# 되돌린 이름 변경이 있으면 입력칸도 원래 이름으로 다시 그리도록 위젯을 새로 만들고, 안내는 rerun 뒤 1회 표시
if rename_errors:
    st.session_state.family_rename_error = " ".join(rename_errors)
    st.session_state.family_widget_key += 1
    print(f"[yellow]가족 이름 변경 거부:[/yellow] {escape(' '.join(rename_errors))}")
    st.rerun()

# 삭제 버튼이 클릭되었을 때의 처리
if to_delete is not None:
    target_name = st.session_state.families_data[to_delete]["name"]
    used_in = find_expenses_using_family(st.session_state.expenses_data, target_name)
    if len(st.session_state.families_data) <= 1:
        # 가족이 0팀이 되면 지출 입력 영역의 st.columns(0) 등에서 앱이 멈추므로 최소 1팀은 남겨 둡니다.
        st.sidebar.error("가족은 최소 1팀 이상 있어야 하므로 마지막 남은 가족은 삭제할 수 없습니다. 새 가족을 먼저 추가해 주세요.")
        print(f"[yellow]가족 삭제 차단 (마지막 남은 가족):[/yellow] {escape(target_name)}")
    elif used_in:
        # 지출에서 사용 중인 가족을 지우면 해당 지출이 정산에서 빠지거나 KeyError가 나므로 삭제를 막습니다.
        st.sidebar.error(
            f"'{target_name}' 가족은 지출 {len(used_in)}건({', '.join(used_in)})에 지불자나 참여자로 들어 있어 삭제할 수 없습니다. "
            "해당 지출을 먼저 수정하거나 삭제해 주세요."
        )
        print(f"[yellow]가족 삭제 차단 (지출에서 사용 중):[/yellow] {escape(target_name)} → {escape(', '.join(used_in))}")
    else:
        deleted_fam = st.session_state.families_data.pop(to_delete)
        # 가족 입력 위젯 key가 목록 위치(i) 기반이라, key를 갱신하지 않으면 삭제된 가족의 값이
        # 같은 위치의 다음 가족 칸에 남아 다시 저장됩니다(엉뚱한 가족이 지워지는 버그). 위젯을 새로 만들도록 key 세대를 올립니다.
        st.session_state.family_widget_key += 1
        print(f"[yellow]사용자 조작으로 가족 삭제됨:[/yellow] {escape(deleted_fam['name'])}")
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
            print(f"[green]사용자 조작으로 가족 추가됨:[/green] {escape(add_name)} ({add_count}명)")
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

# 직전 실행에서 복원을 마쳤다면 완료 안내를 한 번 표시 (복원 직후 st.rerun()으로 화면이 다시 그려지므로 1회성 메시지로 전달)
restored_name = st.session_state.pop("backup_restore_notice", None)
if restored_name:
    st.sidebar.success(f"'{restored_name}' 파일로 복원했습니다.")

if uploaded_file is not None:
    st.sidebar.caption("⚠️ 복원하면 현재 입력된 가족·지출 내역이 이 파일의 내용으로 바뀝니다.")
    
    # 파일을 올리는 것만으로는 덮어쓰지 않고, '복원' 버튼을 누른 실행에서만 불러옵니다.
    # (버튼 값은 누른 그 실행에서만 True라 무한 rerun 방지용 플래그가 필요 없고, 같은 파일도 몇 번이든 다시 복원 가능)
    if st.sidebar.button("♻️ 이 파일로 복원", key="restore_backup_btn", use_container_width=True):
        try:
            uploaded_file.seek(0)  # 이전 실행에서 읽은 위치가 남아 있을 수 있으므로 처음부터 읽음
            loaded_data = json.load(uploaded_file)
            if "families" in loaded_data and "expenses" in loaded_data and not loaded_data["families"]:
                # 가족 목록이 빈 백업을 불러오면 가족 0팀 상태가 되어 앱이 멈추므로 불러오지 않습니다.
                st.sidebar.error("가족 목록이 비어 있는 백업 파일은 불러올 수 없습니다. 가족이 1팀 이상 들어 있는 파일을 선택해 주세요.")
                print(f"[yellow]빈 가족 목록 백업 파일 불러오기 거부:[/yellow] {escape(uploaded_file.name)}")
            elif "families" in loaded_data and "expenses" in loaded_data:
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
                
                # rerun 뒤 화면에 복원 완료 안내를 띄우기 위한 1회성 메시지
                st.session_state.backup_restore_notice = uploaded_file.name
                
                print(f"[green]백업 데이터 복원 성공 (파일명: {escape(uploaded_file.name)})[/green]")
                st.rerun()
            else:
                # 버튼을 눌렀는데 아무 반응이 없지 않도록, 필요한 항목이 없는 파일도 알려 줍니다.
                st.sidebar.error("올바르지 않은 백업 파일 형식입니다. (families·expenses 항목이 없습니다)")
                print(f"[yellow]백업 파일 형식 오류 (families/expenses 없음):[/yellow] {escape(uploaded_file.name)}")
        except Exception as e:
            st.sidebar.error("올바르지 않은 백업 파일 형식입니다.")
            print(f"[red]백업 로드 에러:[/red] {escape(str(e))}")

# 로그아웃 버튼 배치
render_logout_button()


# -----------------------------------------------------------------------------
# 4. 메인 화면 UI 레이아웃
# -----------------------------------------------------------------------------
st.title("💸 모임 지출 정산 프로그램")
st.markdown("가족들의 모임 지출을 쉽고 투명하게 계산하고, 송금 경로를 최소화하여 깔끔한 결과를 얻으세요!")

# 계산기 인스턴스 생성 및 세션 상태에 저장된 지출 내역 복원
calculator = SettlementCalculator(families_list)
skipped_expenses: List[str] = []  # 존재하지 않는 가족을 참조해 정산 계산에서 빠진 지출 항목명
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
        skipped_expenses.append(str(exp_dict.get("item_name", "?")))
        print(f"[red]지출 복원 에러:[/red] {escape(str(e))}")

# 백업 파일 등으로 목록에 없는 가족을 참조하는 지출이 들어온 경우, 조용히 빠지지 않도록 화면에 알림
if skipped_expenses:
    st.warning(
        f"⚠️ 가족 목록에 없는 가족이 들어 있는 지출 {len(skipped_expenses)}건({', '.join(skipped_expenses)})은 "
        "정산 계산에서 제외되었습니다. 해당 지출을 수정하거나 삭제해 주세요."
    )

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
            # 단, 참여 가족 구성이 저장 당시와 같을 때만 사용 (구성이 바뀌면 남은 비율의 합이 맞지 않으므로 균등값으로 다시 채움)
            if is_edit_mode and edit_exp.get("custom_shares") and set(edit_exp["custom_shares"]) == set(selected_participants):
                saved_shares = edit_exp["custom_shares"]
            # 참여 가족 구성이 바뀌면 비율 입력칸 key도 바뀌어 새 위젯(균등값)으로 다시 만들어지도록 하는 접미사
            # (예전에는 key가 순번·이름 기반이라 체크 해제 후 남은 가족이 예전 값 20%씩을 유지해 합계 80%가 됨)
            participants_sig = "|".join(selected_participants)
                
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
                        key=f"share_pct_val_{name}_{participants_sig}_{st.session_state.expense_widget_key}",
                        format="%.1f"
                    )
                    custom_shares[name] = val
            
            # 입력된 비율의 실시간 합계 출력
            current_sum = sum(custom_shares.values())
            sum_gap = abs(current_sum - 100.0)
            if sum_gap < 0.01:
                st.success(f"현재 비율 합계: **{current_sum:.1f}%** (정산 가능합니다! ✅)")
            elif sum_gap < SHARE_SUM_TOLERANCE:
                st.info(
                    f"현재 비율 합계: **{current_sum:.1f}%** (정산 가능합니다. 비율대로 환산해 원 단위로 나누고, "
                    "남거나 넘치는 몇 원은 모임 전체에서 가장 많이 지출한 참여 가족(동점이면 총무)이 부담합니다.)"
                )
            else:
                st.warning(f"현재 비율 합계: **{current_sum:.1f}%** (합계가 100%와 {SHARE_SUM_TOLERANCE:g}%p 미만으로 차이 나야 합니다. ⚠️)")
                    
        submitted = st.button("수정 완료 💾" if is_edit_mode else "추가하기 💳", use_container_width=True)
        
        if submitted:
            if not item_name.strip():
                st.error("지출 항목명을 입력해주세요.")
            elif amount <= 0:
                st.error("올바른 지출 금액을 입력해주세요.")
            elif not selected_participants:
                st.error("최소 한 팀 이상의 참여 가족을 지정해야 합니다.")
            elif split_method == "사용자 지정 비율 분담 (%)" and abs(sum(custom_shares.values()) - 100.0) >= SHARE_SUM_TOLERANCE:
                st.error(f"비율의 합이 {sum(custom_shares.values()):.1f}% 입니다. 사용자 지정 비율 분담 시 비율의 총합은 100%와 {SHARE_SUM_TOLERANCE:g}%p 미만으로 차이 나야 합니다.")
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
                    print(f"[green]사용자 조작으로 지출 내역 수정 완료:[/green] {escape(str(new_expense))}")
                    st.success("지출 내역이 성공적으로 수정되었습니다!")
                else:
                    st.session_state.expenses_data.append(new_expense)
                    st.session_state.last_payer = payer_name # 마지막 지불자 콤보박스 유지
                    print(f"[green]사용자 입력으로 지출 등록됨:[/green] {escape(str(new_expense))}")
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
                print(f"[yellow]사용자 조작으로 지출 삭제됨:[/yellow] {escape(str(removed))}")
                st.warning(f"'{removed['item_name']}' 지출 내역이 삭제되었습니다.")
                
                # 에디팅 모드 인덱스 유효성 조정
                if st.session_state.editing_index == target_idx:
                    st.session_state.editing_index = None
                    # 수정 중이던 지출을 지운 경우, 입력칸에 남은 그 값으로 '추가하기'를 눌러 되살아나지 않도록
                    # 위젯 key 세대를 올려 입력폼을 비웁니다. ('수정 모드 취소' 버튼과 같은 방식)
                    st.session_state.expense_widget_key += 1
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
        # (계산기가 받아들인 지출만 집계: 목록에 없는 가족을 참조하는 지출은 KeyError 없이 제외되며 위에서 경고 표시)
        payer_summary = {name: 0 for name in family_names}
        for exp_obj in calculator.expenses:
            payer_summary[exp_obj.payer_name] += exp_obj.amount
            
        # 대표 수납자(총무) 결정 → 순 잔액(Net Balance) 계산
        # 비율 분담의 원 단위 차액은 최다 지출 가족이 동점이면 총무에게 가므로, 잔액보다 총무를 먼저 정합니다.
        # (총무 선택 위젯은 아래 탭에 있지만, 직전 선택값이 이미 session_state에 있으므로 미리 읽을 수 있음)
        auto_manager = calculator.pick_auto_manager()
        selected_manager_opt = st.session_state.get("select_settlement_manager", "자동 선정")
        active_manager = selected_manager_opt if selected_manager_opt in family_names else auto_manager
        balances = calculator.calculate_balances(manager_name=active_manager)

        # 송금 경로와 총무 정산 숫자는 탭 1·2, 카카오톡 공지, 이미지가 함께 쓰므로 탭을 그리기 전에 한 번만 계산
        optimal_transfers = calculator.get_optimal_transfers(manager_name=active_manager)
        manager_received = sum(amt for _, cred, amt in optimal_transfers if cred == active_manager)
        manager_paid_out = sum(amt for debt, _, amt in optimal_transfers if debt == active_manager)
        manager_remaining = manager_received - manager_paid_out
        manager_spent = payer_summary.get(active_manager, 0)  # 총무의 기지출액
        manager_share = int(round(manager_spent - balances.get(active_manager, 0.0)))  # 총무 본인 분담금
        # 끝전: 총무에게 보낼 돈은 올림·돌려줄 돈은 내림으로 정하면서 총무에게 더 남는 금액 (항상 0 이상)
        manager_tail = manager_remaining - (manager_spent - manager_share)

        # 가족별 실제 정산 금액 (탭 1 상태 표시용): 총무 외 가족은 송금 카드 금액, 총무는 최종 남는 금액
        settle_amounts: Dict[str, int] = {name: 0 for name in family_names}
        for debtor, creditor, amt in optimal_transfers:
            if creditor == active_manager:
                settle_amounts[debtor] = -amt   # 총무에게 보냄
            else:
                settle_amounts[creditor] = amt  # 총무에게서 돌려받음
        settle_amounts[active_manager] = manager_remaining

        # 정산 참고 안내문 (해당하는 지출이 있을 때만 화면·공지 텍스트·이미지 '참고' 영역에 표시)
        #  - 사용자 지정 비율 분담의 원 단위 반올림 차액
        #  - 비율 합이 0%라 기본 분담으로 대신 나눈 지출 (백업 파일로만 유입 가능)
        settlement_notes: List[str] = []
        for fallback in calculator.get_zero_share_fallbacks():
            settlement_notes.append(
                f"'{fallback['item_name']}' 비율 분담: 비율 합이 0%라 {fallback['fallback']}로 나눔"
            )
        for note in calculator.get_share_rounding_notes(manager_name=active_manager):
            if note["remainder"] > 0:
                settlement_notes.append(
                    f"'{note['item_name']}' 비율 분담: 원 단위로 나누고 남은 {note['remainder']:,}원은 "
                    f"가장 많이 지출한 {note['receiver']} 가족이 부담"
                )
            else:
                settlement_notes.append(
                    f"'{note['item_name']}' 비율 분담: 원 단위로 나누고 넘친 {-note['remainder']:,}원은 "
                    f"가장 많이 지출한 {note['receiver']} 가족 분담금에서 차감"
                )
        if manager_tail > 0:
            settlement_notes.append(
                f"끝전 {manager_tail:,}원은 총무({active_manager})에게 남음: 총무에게 보낼 돈은 원 단위 올림, 돌려줄 돈은 내림"
            )
            print(f"[cyan]송금액 원 단위 끝전:[/cyan] {manager_tail:,}원 → 총무 {escape(active_manager)}")

        # UI 레이아웃으로 상세 정보 표시
        tab1, tab2 = st.tabs(["💰 가족별 지출/정산 요약", "💸 최적 송금 경로 결과"])
        
        with tab1:
            st.markdown("#### **가족별 상세 정산 내역**")
            summary_data = []
            for name in family_names:
                # 송금 카드와 같은 금액을 보여 주도록 실제 정산 금액 사용 (보낼 돈 올림·돌려받을 돈 내림 반영)
                net = settle_amounts[name]
                status_text = ""
                if net > 0:
                    status_text = f"🟢 {net:,}원 돌려받기"
                elif net < 0:
                    status_text = f"🔴 {-net:,}원 보내기"
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
            # 선택값은 위(잔액 계산 전)에서 session_state로 이미 읽어 active_manager에 반영되어 있음
            manager_options = ["자동 선정"] + family_names
            selected_manager_opt = st.selectbox(
                "👑 대표 수납자(총무) 지정",
                options=manager_options,
                index=0,
                format_func=lambda opt: f"자동 선정 ({auto_manager} - 최대 채권자)" if opt == "자동 선정" else opt,
                key="select_settlement_manager",
                help="지정한 가족이 정산금을 모두 수납받은 뒤, 더 많은 금액을 지출한(돌려받아야 할) 가족에게 다시 송금합니다."
            )
            
            # optimal_transfers와 총무 정산 숫자(manager_*)는 탭을 그리기 전에 위에서 계산해 둠
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
                
                # 정산 참고 안내 (원 단위 차액, 비율 합 0% 대체 등 해당할 때만)
                for note_text in settlement_notes:
                    st.caption(f"※ {note_text}")

                # 총무(대표 수납자) 기준 받는 금액 / 돌려주는 금액 / 최종 남는 금액 표시 (숫자는 탭 위에서 계산)
                # 끝전이 있으면 설명의 계산(선결제 - 분담금)과 최종 남는 금액이 그만큼 다르므로 함께 밝힘
                tail_html = f" 여기에 원 단위 끝전 <strong>{manager_tail:,}원</strong>이 더해졌습니다." if manager_tail > 0 else ""
                if manager_remaining >= 0:
                    explanation_html = f"💡 <strong>최종 남는 금액 설명:</strong> 총무({active_manager}) 가족이 선결제한 금액(<strong>{manager_spent:,}원</strong>)에서 본인 분담금(<strong>{manager_share:,}원</strong>)을 제외하고 <strong>최종적으로 돌려받는(회수하는) 본인 몫의 정산금</strong>입니다.{tail_html}"
                else:
                    explanation_html = f"💡 <strong>부족 금액 설명:</strong> 총무({active_manager}) 가족의 본인 분담금(<strong>{manager_share:,}원</strong>)에서 기지출액(<strong>{manager_spent:,}원</strong>)을 제외한 차액(<strong>{manager_share - manager_spent:,}원</strong>)이 수납금 환급 과정에서 충당 완료되었습니다.{tail_html}"
                
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
                            manager_name=active_manager,
                            notes=settlement_notes
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
                        print(f"[red]이미지 생성 오류:[/red] {escape(str(e))}")
                
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
                
                if settlement_notes:
                    notice_text += "※ 정산 참고:\n"
                    for note_text in settlement_notes:
                        notice_text += f" - {note_text}\n"
                    notice_text += "\n"

                notice_text += f"💸 송금 요청 내역 ({active_manager} 수납 중심):\n"
                for debtor, creditor, amt in optimal_transfers:
                    notice_text += f" 👉 {debtor} ➔ {creditor} : {amt:,}원\n"
                notice_text += "\n"
                notice_text += f"📌 총무({active_manager}) 최종 정산 요약:\n"
                notice_text += f" - 받는 금액 합계: {manager_received:,}원\n"
                notice_text += f" - 돌려주는 금액 합계: {manager_paid_out:,}원\n"
                notice_text += f" - 총무에게 최종 남는 금액: {manager_remaining:,}원\n"
                tail_text = f" 원 단위 끝전 {manager_tail:,}원 포함." if manager_tail > 0 else ""
                if manager_remaining >= 0:
                    notice_text += f"   (💡 총무가 선결제한 비용 {manager_spent:,}원에서 본인 분담금 {manager_share:,}원을 제외하고 최종 회수하는 정산금입니다.{tail_text})\n"
                else:
                    notice_text += f"   (💡 총무 본인 분담금 {manager_share:,}원에서 선결제액 {manager_spent:,}원을 제외한 차액 {manager_share - manager_spent:,}원이 충당 완료되었습니다.{tail_text})\n"
                notice_text += f"━━━━━━━━━━━━━━━━━━━━━\n"
                notice_text += f"정산 내역을 확인해 주시고 이상이 없을 시 송금 부탁드립니다. 감사합니다! 🙏"
                
                st.text_area("공지 텍스트 복사하기 (아래 박스 전체 복사)", value=notice_text, height=250)
                st.info("💡 위의 텍스트 영역을 클릭해 전체 복사(Ctrl+A -> Ctrl+C)하여 단톡방에 올리시면 정산 안내가 한 번에 끝납니다!")
