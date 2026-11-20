# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

가족 모임 지출을 정산하는 Streamlit 웹앱. 지출 등록 → 가족별 순 잔액 계산 → 대표 수납자(총무) 중심 송금 가이드 → PNG 요약 카드 / 카카오톡 공지 텍스트 생성. UI 텍스트·주석·로그 메시지는 모두 한국어로 작성되어 있다. Streamlit Community Cloud(`kzoro4747/WON`, `master`, `main.py`)에 배포된다.

## 명령어

로컬 환경은 Windows + `.venv` (Python 3.12). devcontainer는 Python 3.11 이미지를 사용한다.

```powershell
pip install -r requirements.txt
.venv\Scripts\streamlit.exe run main.py           # 앱 실행 (0-실행법.txt와 동일)

.venv\Scripts\python.exe -m unittest test_calculator                       # 전체 테스트
.venv\Scripts\python.exe -m unittest test_calculator.TestSettlementCalculator.test_custom_ratio_split   # 단일 테스트
.venv\Scripts\python.exe test_image.py            # 이미지 생성 스모크 스크립트 (unittest 아님)
```

린터/포매터 설정은 없다. 테스트는 `calculator.py`만 다루며 `main.py`/`image_generator.py`/`auth.py`에는 자동 테스트가 없다.

UI 동작은 `streamlit.testing.v1.AppTest`로 확인할 수 있다(`at.session_state["authenticated"] = True`로 로그인 화면을 건너뜀). AppTest는 앱 폴더를 `sys.path`에 넣지 않으므로 다른 폴더에서 실행할 때는 `sys.path.insert(0, <저장소 경로>)`를 먼저 해야 한다. 안 하면 실행 폴더에 있는 같은 이름의 다른 모듈이 import된다. 로그 파일이 현재 작업 디렉터리에 생기므로 저장소 밖에서 실행하는 편이 낫다. 또 `st.rerun()` 직후 사라진 위젯이 AppTest 요소 목록에 남아 같은 객체로 다음 `run()`을 하면 `KeyError`가 날 수 있으므로, 그 뒤 상태는 `session_state`에 데이터를 미리 넣은 새 AppTest로 확인한다.

## 아키텍처

### Streamlit rerun 모델과 상태의 원천
- `main.py`는 위에서 아래로 매 상호작용마다 전체 재실행된다. **진실의 원천은 `st.session_state`의 plain dict 리스트**(`families_data`, `expenses_data`)이며, `Family`/`Expense`/`SettlementCalculator` 객체는 매 rerun마다 이 dict들로부터 새로 만들어지는 일회성 객체다. 상태를 바꿀 때는 session_state의 dict를 수정하고 `st.rerun()`을 호출한다.
- 위젯 초기화는 `expense_widget_key` / `family_widget_key` 카운터를 증가시켜 위젯 key를 바꾸는 방식으로 한다 (key에 카운터가 접미사로 붙어 있음). 지출 수정 모드는 `editing_index`로 제어한다.
- 지출 입력 영역은 의도적으로 `st.form`이 아닌 `st.container`를 사용한다. "사용자 지정 비율 분담 (%)" 선택 시 비율 입력 칸이 즉시 나타나려면 위젯 변경마다 rerun이 필요하기 때문이다 (커밋 a0dd589). form으로 되돌리지 말 것.
- `auth.check_password()`가 `False`면 `main.py`가 `st.stop()`으로 이후 렌더링을 막는다. 비밀번호는 `st.secrets["APP_PASSWORD"]`(또는 `password`)에서 읽고, 없으면 `1234`를 쓴다. Streamlit 1.57에서는 `secrets.toml`이 없으면 `"키" in st.secrets`만으로 `StreamlitSecretNotFoundError`(`FileNotFoundError` 하위)가 나므로 secrets 조회는 `auth._get_configured_password()`를 거친다. `.streamlit/` 디렉터리 전체가 gitignore 대상이라 새로 clone한 환경에는 이 파일이 없다.
- 지출 dict는 가족을 **이름으로만** 참조한다. 사이드바에서 이름을 바꾸면 `apply_family_renames()`가 지출의 지불자·참여자·`custom_shares` 키와 `last_payer`·총무 선택값을 새 이름으로 바꾸고, 지출에서 쓰는 가족은 `find_expenses_using_family()`로 확인해 삭제를 막는다. 빈 이름이나 다른 가족과 같은 이름으로 바꾸면 `revert_invalid_family_renames()`가 원래 이름으로 되돌린다(같은 이름을 허용하면 두 가족의 지출이 합쳐져 복구할 수 없음). 마지막 남은 가족은 삭제할 수 없다. 가족 입력 위젯 key는 목록 위치 기반이므로 가족 목록에서 항목을 빼면 반드시 `family_widget_key`를 올려야 한다.

### 지출 dict 스키마 (session_state · JSON 백업 공통)
```python
{"item_name": str, "payer_name": str, "amount": int, "participants": [str],
 "split_by_member": bool, "memo": str, "custom_shares": {name: pct} | None}
```
- 분담 방식 우선순위: `custom_shares`가 비어있지 않으면 비율 분담(가중치를 참여자 합으로 정규화) → `split_by_member`면 인원수 비례 → 그 외 1/N.
- 이 분담 방식 판별 로직이 **네 곳에 중복**되어 있다: `main.py`의 수정 모드 기본값 파싱(`default_split`), 지출 목록 테이블, 카카오톡 공지 텍스트, `image_generator.py`의 지출 항목 렌더링. 필드를 추가/변경하면 이 네 곳과 함께 `main.py`의 저장 dict 생성부(`new_expense`), JSON 백업 로더(구버전 파일의 누락 필드 보정), `Expense` 복원 코드도 같이 수정해야 한다.

### 송금 알고리즘 (`calculator.py`)
- `calculate_balances()`: 지불액 − 분담액 = 순 잔액 (양수=받을 돈, 음수=낼 돈, float).
- `get_optimal_transfers(manager_name)`: 최소 송금 그리디가 아니라 **총무 허브 방식**이다. 총무(미지정 시 최대 채권자)를 제외한 모든 가족이 총무와 정확히 1회 거래한다. 반환값은 `(보내는 사람, 받는 사람, 금액)` 리스트로, 총무에게 입금하는 건이 먼저, 총무가 환급하는 건이 뒤에 온다. 1/N·인원수 비례 분담은 잔액이 float 그대로이고, 송금액은 **총무에게 보낼 돈은 올림, 총무가 돌려줄 돈은 내림**(`math.ceil`/`math.floor`, float 오차 보정 `TRANSFER_EPSILON`)으로 정한다. 총무는 걷어서 나눠 주는 역할이라 끝전이 총무에게 남게 하려는 사용자 요구이며, 1/N이면 다른 가족이 모두 같은 금액을 보낸다. 끝전(`manager_tail` = 최종 남는 금액 − (총무 지출액 − 총무 분담금))은 `main.py`와 `image_generator.py`가 같은 식으로 계산해 총무 설명문과 '※ 정산 참고'에 표시한다. 탭 1의 가족별 상태도 반올림 잔액이 아니라 실제 송금액(`settle_amounts`)을 보여 준다.
- 사용자 지정 비율 분담(`split_custom_shares()`)은 비율을 참여 가족 비율 합으로 정규화한 뒤 원 단위로 반올림(0.5 올림)하고, 차액은 `find_remainder_receiver()` 규칙(참여 가족 중 모임 전체 총 지불액 최대 → 동점이면 총무 → 가족 목록 순서)에 따라 한 가족에게 몰아준다. 그래서 **잔액이 총무에 따라 달라질 수 있다.** `main.py`는 총무를 먼저 정하고(`pick_auto_manager()` 또는 session_state의 직전 선택값), 같은 `manager_name`으로 `calculate_balances`·`get_optimal_transfers`·`get_share_rounding_notes`를 호출한다. 참여 가족 비율 합이 0% 이하인 지출(백업 파일로만 유입 가능)은 기본 분담(인원수 비례 또는 1/N)으로 대신 나눈다(`get_zero_share_fallbacks()`). 이 두 안내는 `main.py`의 `settlement_notes`로 모여 화면 caption, 카카오톡 공지("※ 정산 참고"), 이미지 `notes`(푸터 위 '참고' 영역)에 표시된다.
- 입력 화면의 비율 합계는 100%와 `SHARE_SUM_TOLERANCE`(1%p) 미만으로 차이 나면 저장을 허용한다. 비율 입력칸 key에 참여 가족 구성이 들어 있어, 구성이 바뀌면 균등값으로 다시 채워진다.
- `test_complex_settlement`의 docstring은 옛 그리디 알고리즘을 설명하지만, 실제 assertion은 총무 허브 결과를 검증한다.

### 도움말 (`help_dialog.py`)
- 사이드바 맨 위 '❓ 도움말' 버튼 → `st.dialog` 팝업. 문구는 `HELP_TABS`에 탭별 마크다운으로 모여 있으므로, 화면 동작(삭제 규칙, 분담 방식, 백업 복원 등)을 바꾸면 이 설명도 함께 고친다.

### 이미지 생성 (`image_generator.py`)
- Pillow로 1600px 폭, 내용에 따라 높이가 동적으로 계산되는 PNG를 그려 bytes로 반환한다. 높이 계산 블록과 실제 그리기 블록이 분리되어 있어, 레이아웃(행 높이·섹션)을 바꾸면 두 곳을 함께 맞춰야 잘리지 않는다.
- 폰트: `fonts/Pretendard-*.ttf`(저장소에 포함, 없으면 jsDelivr에서 다운로드) → Windows 시스템 한글 폰트 → PIL 기본 폰트 순으로 fallback.
- Pretendard에는 이모지가 없어 그대로 그리면 빈 네모가 된다. `draw`는 `_GlyphSafeDraw`로 감싸져 있어 `text()`/`textlength()`에서 폰트에 없는 글자와 ZWJ 같은 서식 문자를 빼고 그린다(화면·공지 텍스트는 원문 유지). 코드에 넣는 고정 문구에도 이모지 대신 `※`, `●`처럼 폰트에 있는 기호를 쓴다.

## 코딩 규칙

- **앱 모듈과 `test_calculator.py`는 `from logger_utils import print`로 내장 `print`를 덮어쓴다** (`test_image.py`만 내장 print 사용). rich 마크업(`[green]...[/green]`)을 그대로 쓸 수 있고, 터미널 출력과 동시에 `<호출 파일명>_YYMMDD.log`에 기록된다. 로그 파일은 스크립트 위치가 아닌 **현재 작업 디렉터리**에 생성되며 `*.log`는 gitignore 대상이다. 새 모듈에서도 이 import를 유지할 것.
- 인자가 rich 마크업으로 해석되므로, 사용자 입력(항목명·메모·가족명)이나 예외 메시지를 f-string에 넣을 때는 `rich.markup.escape()`로 감싼다. 빠뜨려도 `logger_utils.print`의 안전망이 `MarkupError`를 잡아 마크업 해석 없이 원문으로 다시 출력하므로 앱은 멈추지 않지만, 그 줄은 `[green]` 같은 태그까지 글자로 찍힌다.
- 코드 주석, docstring, UI 문구, 로그 메시지는 기존과 같이 한국어로 작성한다.
