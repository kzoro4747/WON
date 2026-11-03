import os
import io
import urllib.request
from datetime import datetime
from typing import List, Dict, Tuple, Any
from PIL import Image, ImageDraw, ImageFont
from logger_utils import print  # 규칙에 따라 rich 기반의 커스텀 로거 임포트

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

def _ensure_modern_font() -> Tuple[str, str]:
    """
    요즘 최신 UI/UX 트렌드 오픈소스 한글 폰트인 'Pretendard(프리텐다드)'를 확인하고,
    로컬에 없을 경우 안정적인 CDN에서 자동 다운로드하여 (볼드 경로, 일반 경로)를 반환합니다.
    """
    os.makedirs(FONTS_DIR, exist_ok=True)
    bold_path = os.path.join(FONTS_DIR, "Pretendard-Bold.ttf")
    reg_path = os.path.join(FONTS_DIR, "Pretendard-Regular.ttf")
    
    headers = {"User-Agent": "Mozilla/5.0"}
    bold_url = "https://cdn.jsdelivr.net/gh/orioncactus/pretendard/packages/pretendard/dist/public/static/alternative/Pretendard-Bold.ttf"
    reg_url = "https://cdn.jsdelivr.net/gh/orioncactus/pretendard/packages/pretendard/dist/public/static/alternative/Pretendard-Regular.ttf"
    
    if not os.path.exists(bold_path) or os.path.getsize(bold_path) == 0:
        try:
            print("[blue]최신 트렌드 폰트(Pretendard Bold) 다운로드 시도 중...[/blue]")
            req = urllib.request.Request(bold_url, headers=headers)
            with urllib.request.urlopen(req, timeout=4) as resp, open(bold_path, "wb") as f:
                f.write(resp.read())
            print(f"[green]Pretendard Bold 폰트 다운로드 성공:[/green] {bold_path}")
        except Exception as e:
            print(f"[yellow]Pretendard Bold 다운로드 실패 (시스템 기본 폰트로 대체):[/yellow] {str(e)}")
            
    if not os.path.exists(reg_path) or os.path.getsize(reg_path) == 0:
        try:
            print("[blue]최신 트렌드 폰트(Pretendard Regular) 다운로드 시도 중...[/blue]")
            req = urllib.request.Request(reg_url, headers=headers)
            with urllib.request.urlopen(req, timeout=4) as resp, open(reg_path, "wb") as f:
                f.write(resp.read())
            print(f"[green]Pretendard Regular 폰트 다운로드 성공:[/green] {reg_path}")
        except Exception as e:
            print(f"[yellow]Pretendard Regular 다운로드 실패 (시스템 기본 폰트로 대체):[/yellow] {str(e)}")
            
    return bold_path, reg_path

def _get_text_width(draw_obj: ImageDraw.ImageDraw, text: str, font: Any) -> int:
    """
    주어진 텍스트와 폰트의 정확한 렌더링 가로 폭(px)을 반환합니다.
    """
    try:
        return int(draw_obj.textlength(text, font=font))
    except AttributeError:
        try:
            return int(font.getlength(text))
        except AttributeError:
            if hasattr(font, "getbbox"):
                bbox = font.getbbox(text)
                return int(bbox[2] - bbox[0])
            return len(text) * 20


def generate_settlement_image(
    families: Dict[str, Any],
    expenses: List[Dict[str, Any]],
    transfers: List[Tuple[str, str, int]],
    total_spent: int,
    allocated_summary: Dict[str, float] = None,
    manager_name: str = None
) -> bytes:
    """
    정산 결과 요약과 송금 경로를 시각화하여 고화질의 PNG 카드 이미지(Bytes)로 생성합니다.
    (해상도를 4배로 키우기 위해 모든 크기 단위를 2배로 확장 적용)
    """
    print("[blue]이미지 생성 시작: 정산 결과 데이터 파싱 중...[/blue]")
    
    # 1. 최신 트렌드 폰트(Pretendard) 우선 로드 및 Windows 폰트 Fallback 마련
    font_title = None
    font_sec_title = None
    font_bold = None
    font_regular = None
    font_small = None
    
    # 최신 트렌드 폰트 파일 확보
    pt_bold, pt_reg = _ensure_modern_font()
    
    # 볼드 / 일반 폰트 우선순위 목록
    bold_paths = [
        pt_bold,                                # 1순위: Pretendard Bold (최신 트렌드 UI 폰트)
        r"C:\Windows\Fonts\NanumSquareB.ttf",    # 2순위: 나눔스퀘어 Bold
        r"C:\Windows\Fonts\NanumGothicBold.ttf", # 3순위: 나눔고딕 Bold
        r"C:\Windows\Fonts\malgunbd.ttf",       # 4순위: 맑은 고딕 Bold
        r"C:\Windows\Fonts\batang.ttc"
    ]
    reg_paths = [
        pt_reg,                                 # 1순위: Pretendard Regular
        r"C:\Windows\Fonts\NanumSquareR.ttf",    # 2순위: 나눔스퀘어 Regular
        r"C:\Windows\Fonts\NanumGothic.ttf",    # 3순위: 나눔고딕 Regular
        r"C:\Windows\Fonts\malgun.ttf",         # 4순위: 맑은 고딕 Regular
        r"C:\Windows\Fonts\batang.ttc"
    ]
    
    # 볼드 폰트 적용 (글자 크기 2배 스케일링)
    for path in bold_paths:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            try:
                font_title = ImageFont.truetype(path, 60)       # 30 -> 60
                font_sec_title = ImageFont.truetype(path, 36)   # 18 -> 36
                font_bold = ImageFont.truetype(path, 28)        # 14 -> 28
                print(f"[green]볼드 폰트 로드 성공 (2배 스케일):[/green] {path}")
                break
            except Exception as e:
                print(f"[red]볼드 폰트 로딩 실패:[/red] {path} ({str(e)})")
                
    # 일반 폰트 적용 (글자 크기 2배 스케일링)
    for path in reg_paths:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            try:
                font_regular = ImageFont.truetype(path, 26)     # 13 -> 26
                font_small = ImageFont.truetype(path, 22)       # 11 -> 22
                print(f"[green]일반 폰트 로드 성공 (2배 스케일):[/green] {path}")
                break
            except Exception as e:
                print(f"[red]일반 폰트 로딩 실패:[/red] {path} ({str(e)})")
                
    # 시스템에 폰트가 없는 경우 기본 폰트로 Fallback
    if font_title is None:
        font_title = ImageFont.load_default()
    if font_sec_title is None:
        font_sec_title = ImageFont.load_default()
    if font_bold is None:
        font_bold = ImageFont.load_default()
    if font_regular is None:
        font_regular = ImageFont.load_default()
    if font_small is None:
        font_small = ImageFont.load_default()
        
    # 2. 동적 높이 계산 (가족별로 그룹화하여 지출 목록 높이 산정)
    width = 1600
    
    # 가족별로 지출 내역 그룹화
    grouped_expenses = {name: [] for name in families.keys()}
    for exp in expenses:
        payer = exp["payer_name"]
        if payer in grouped_expenses:
            grouped_expenses[payer].append(exp)
        else:
            grouped_expenses[payer] = [exp]
            
    # 동적 지출 목록 높이 계산
    expenses_list_h = 20  # 기본 패딩
    has_any_expense = False
    for name, list_of_exps in grouped_expenses.items():
        if list_of_exps:
            has_any_expense = True
            expenses_list_h += 60  # 가족 그룹 타이틀 영역 높이
            expenses_list_h += len(list_of_exps) * 45  # 개별 지출 항목당 높이
            expenses_list_h += 20  # 그룹 간 마진 여백
            
    if not has_any_expense:
        expenses_list_h = 100
    else:
        expenses_list_h = max(expenses_list_h, 100)
        
    header_h = 320
    families_h = 220
    expenses_title_h = 90
    transfers_title_h = 90
    transfers_list_h = max(len(transfers) * 110 + (200 if manager_name and transfers else 40), 120)
    footer_h = 160
    
    total_height = header_h + families_h + expenses_title_h + expenses_list_h + transfers_title_h + transfers_list_h + footer_h
    print(f"[blue]동적 이미지 규격 설정 (4배 해상도):[/blue] {width}x{total_height} (지출 {len(expenses)}건, 송금 {len(transfers)}건)")
    
    # 3. 그라데이션 배경 생성
    image = Image.new("RGB", (width, total_height))
    draw = ImageDraw.Draw(image)
    
    for y in range(total_height):
        r = int(15 + (30 - 15) * (y / total_height))
        g = int(23 + (41 - 23) * (y / total_height))
        b = int(42 + (59 - 42) * (y / total_height))
        draw.line([(0, y), (width, y)], fill=(r, g, b))
        
    # 4. 카드 내부 테두리 그리기 (두께 2 -> 4)
    draw.rectangle([(20, 20), (width - 20, total_height - 20)], outline=(51, 65, 85), width=4)
    
    # 5. 헤더 섹션 (제목 및 메타 정보)
    draw.text((80, 70), "모임 지출 정산 결과", font=font_title, fill=(56, 189, 248))
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    meta_text = f"정산일시: {now_str}  |  총 지출액: {total_spent:,}원"
    draw.text((80, 170), meta_text, font=font_regular, fill=(148, 163, 184))
    
    # 헤더 구분선 (두께 1 -> 2)
    draw.line([(80, 240), (width - 80, 240)], fill=(51, 65, 85), width=2)
    
    # 6. 가족 구성원 요약 박스
    box_top = 270
    box_bottom = box_top + 180
    draw.rounded_rectangle([(80, box_top), (width - 80, box_bottom)], radius=16, fill=(30, 41, 59), outline=(51, 65, 85), width=2)
    
    draw.text((110, box_top + 24), "참여 가족 구성 및 사용(적용) 금액", font=font_bold, fill=(56, 189, 248))
    
    # 가족 목록 문자열화
    fam_strs = []
    for name, fam in families.items():
        if hasattr(fam, "member_count"):
            member_count = fam.member_count
        elif isinstance(fam, dict):
            member_count = fam.get("member_count", 0)
        else:
            member_count = 0
        fam_strs.append(f"{name}({member_count}명)")
    fam_info_text = ",  ".join(fam_strs)
    
    draw.text((110, box_top + 70), fam_info_text, font=font_regular, fill=(248, 250, 252))
    
    if allocated_summary:
        alloc_strs = [f"{name}: {int(round(amt)):,}원" for name, amt in allocated_summary.items()]
        alloc_info_text = "  |  ".join(alloc_strs)
        draw.text((110, box_top + 120), alloc_info_text, font=font_regular, fill=(16, 185, 129))
    
    # 7. 지출 목록 섹션
    right_align_x = width - 110  # 모든 우측 금액(그룹 합계, 개별 내역, 송금액, 최종 요약)의 수직 정렬 기준선 통일
    current_y = box_bottom + 50
    exp_sec_title = "지출 항목 내역"
    draw.text((80, current_y), exp_sec_title, font=font_sec_title, fill=(248, 250, 252))
    # 제목 텍스트 길이에 정확히 맞춘 밑줄 지시선
    exp_title_w = _get_text_width(draw, exp_sec_title, font_sec_title)
    draw.line([(80, current_y + 50), (80 + exp_title_w, current_y + 50)], fill=(56, 189, 248), width=4)
    
    current_y += 70
    if not expenses:
        draw.text((110, current_y), "등록된 지출 내역이 없습니다.", font=font_regular, fill=(148, 163, 184))
        current_y += 50
    else:
        for name, list_of_exps in grouped_expenses.items():
            if not list_of_exps:
                continue
                
            # 가족 그룹의 총 지출 합계 계산
            fam_total = sum(e["amount"] for e in list_of_exps)
            
            # 가족 그룹 헤더 그리기 (예: "● 가율 (총 2건)")
            group_header = f"● {name} (총 {len(list_of_exps)}건)"
            draw.text((80, current_y), group_header, font=font_bold, fill=(56, 189, 248))
            
            group_total_str = f"{fam_total:,}원"
            w = _get_text_width(draw, group_total_str, font_bold)
            draw.text((right_align_x - w, current_y), group_total_str, font=font_bold, fill=(56, 189, 248))
            
            # 헤더 아래 구분선
            draw.line([(80, current_y + 38), (width - 80, current_y + 38)], fill=(51, 65, 85), width=2)
            current_y += 48
            
            # 개별 지출 항목 그리기
            for exp in list_of_exps:
                memo_val = exp.get("memo", "")
                participants_list = exp.get("participants", [])
                participants_str = ", ".join(participants_list)
                
                if exp.get("custom_shares") is not None and len(exp["custom_shares"]) > 0:
                    shares_dict = exp["custom_shares"]
                    shares_str = ", ".join(f"{p} {float(shares_dict.get(p, 0)):g}%" for p in participants_list)
                    split_desc = f"비율분담: {shares_str}" if shares_str else "비율분담"
                elif exp.get("split_by_member", False):
                    member_parts = []
                    for p in participants_list:
                        fam_obj = families.get(p)
                        m_cnt = getattr(fam_obj, "member_count", fam_obj.get("member_count", 0) if isinstance(fam_obj, dict) else 0)
                        member_parts.append(f"{p}({m_cnt}명)")
                    split_desc = f"인원수비례: {', '.join(member_parts)}" if member_parts else "인원수비례"
                else:
                    split_desc = f"1/N: {participants_str}" if participants_str else "1/N"
                    
                # 항목명, 메모(붉은색), 분담기준 순으로 이어서 렌더링
                base_x = 110
                
                # 1. 항목명
                item_name_str = f"- {exp['item_name']}"
                draw.text((base_x, current_y), item_name_str, font=font_regular, fill=(226, 232, 240))
                base_x += _get_text_width(draw, item_name_str, font_regular)
                
                # 2. 메모 (존재할 경우 붉은색)
                if memo_val:
                    memo_str = f" [{memo_val}]"
                    draw.text((base_x, current_y), memo_str, font=font_regular, fill=(251, 113, 133))
                    base_x += _get_text_width(draw, memo_str, font_regular)
                    
                # 3. 분담 기준
                split_str = f" ({split_desc})"
                draw.text((base_x, current_y), split_str, font=font_regular, fill=(226, 232, 240))
                
                amt_str = f"{exp['amount']:,}원"
                w = _get_text_width(draw, amt_str, font_regular)
                draw.text((right_align_x - w, current_y), amt_str, font=font_regular, fill=(16, 185, 129))
                
                # 항목 구분 밑줄 (배경색에 묻히지 않도록 선명한 슬레이트 톤 적용)
                draw.line([(110, current_y + 36), (width - 80, current_y + 36)], fill=(51, 65, 85), width=1)
                current_y += 45
                
            # 가족 그룹 완료 후 여백 추가
            current_y += 15
            
    # 8. 송금 경로 안내 섹션
    current_y += 30
    trans_sec_title = "최적 송금 가이드 (총무 중심 1방향 정산)"
    draw.text((80, current_y), trans_sec_title, font=font_sec_title, fill=(56, 189, 248))
    # 제목 텍스트 전체 길이에 맞춘 밑줄 지시선 (누락 방지)
    trans_title_w = _get_text_width(draw, trans_sec_title, font_sec_title)
    draw.line([(80, current_y + 50), (80 + trans_title_w, current_y + 50)], fill=(56, 189, 248), width=4)
    
    current_y += 80
    if not transfers:
        draw.text((110, current_y), "모든 정산 상태가 완료되어 송금할 내역이 없습니다.", font=font_bold, fill=(16, 185, 129))
        current_y += 70
    else:
        for debtor, creditor, amount in transfers:
            # 송금 카드 박스 그리기 (높이 90)
            card_top = current_y
            card_bottom = card_top + 90
            draw.rounded_rectangle([(80, card_top), (width - 80, card_bottom)], radius=12, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
            
            # 채무자 (보내는 이)
            draw.text((110, card_top + 28), debtor, font=font_bold, fill=(244, 63, 94))
            
            # 보내기 화살표
            draw.text((300, card_top + 30), "보내기  ->", font=font_regular, fill=(148, 163, 184))
            
            # 채권자 (받는 이)
            draw.text((500, card_top + 28), creditor, font=font_bold, fill=(56, 189, 248))
            
            # 송금액 (우측 정렬 기준선 right_align_x 에 통일)
            amt_str = f"{amount:,}원"
            w = _get_text_width(draw, amt_str, font_bold)
            draw.text((right_align_x - w, card_top + 28), amt_str, font=font_bold, fill=(16, 185, 129))
            
            current_y += 100
            
        # 총무 수납/환급 및 최종 남는 금액 요약 박스 렌더링
        if manager_name:
            manager_received = sum(amt for _, cred, amt in transfers if cred == manager_name)
            manager_paid_out = sum(amt for debt, _, amt in transfers if debt == manager_name)
            manager_remaining = manager_received - manager_paid_out
            
            # 총무의 지출액 및 분담금 계산
            manager_spent = sum(e["amount"] for e in grouped_expenses.get(manager_name, []))
            manager_share = int(round(allocated_summary.get(manager_name, 0))) if allocated_summary else 0
            
            current_y += 10
            sum_top = current_y
            sum_bottom = sum_top + 130
            draw.rounded_rectangle([(80, sum_top), (width - 80, sum_bottom)], radius=12, fill=(30, 41, 59), outline=(56, 189, 248), width=3)
            
            # 1행: 수납/환급 내역 및 최종 남는 금액
            sum_label = f"총무({manager_name}) 정산 요약  |  받는 돈 {manager_received:,}원  -  돌려주는 돈 {manager_paid_out:,}원"
            draw.text((110, sum_top + 28), sum_label, font=font_bold, fill=(226, 232, 240))
            
            remain_str = f"최종 남는 금액: {manager_remaining:,}원"
            w = _get_text_width(draw, remain_str, font_bold)
            draw.text((right_align_x - w, sum_top + 28), remain_str, font=font_bold, fill=(56, 189, 248))
            
            # 박스 내부 구분선
            draw.line([(110, sum_top + 72), (width - 110, sum_top + 72)], fill=(51, 65, 85), width=1)
            
            # 2행: 최종 남는 금액에 대한 친절한 설명 문구
            if manager_remaining >= 0:
                desc_text = f"💡 최종 남는 금액 설명: 총무({manager_name})가 선결제한 비용({manager_spent:,}원)에서 본인 분담금({manager_share:,}원)을 제외하고 최종 회수(환급)받는 본인 몫입니다."
            else:
                desc_text = f"💡 부족 금액 설명: 총무({manager_name}) 본인 분담금({manager_share:,}원)에서 기지출액({manager_spent:,}원)을 제외한 {-manager_remaining:,}원이 충당 완료되었습니다."
            draw.text((110, sum_top + 86), desc_text, font=font_small, fill=(148, 163, 184))
            
            current_y += 145
            
    # 9. 푸터 섹션
    current_y += 20
    draw.line([(80, current_y), (width - 80, current_y)], fill=(51, 65, 85), width=2)
    
    footer_text = "정산 내역을 확인해 주시고 이상이 없을 시 송금 부탁드립니다. 감사합니다!"
    try:
        bbox = font_small.getbbox(footer_text)
        w = bbox[2] - bbox[0]
    except AttributeError:
        w = 600
    draw.text(((width - w) // 2, current_y + 30), footer_text, font=font_small, fill=(148, 163, 184))
    
    # 10. 이미지 바이트 반환
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format="PNG")
    print("[green]이미지 생성 성공 및 PNG 변환 완료![/green]")
    return img_byte_arr.getvalue()
