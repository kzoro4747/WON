import os
import io
from datetime import datetime
from typing import List, Dict, Tuple, Any
from PIL import Image, ImageDraw, ImageFont
from logger_utils import print  # 규칙에 따라 rich 기반의 커스텀 로거 임포트

def generate_settlement_image(
    families: Dict[str, Any],
    expenses: List[Dict[str, Any]],
    transfers: List[Tuple[str, str, int]],
    total_spent: int
) -> bytes:
    """
    정산 결과 요약과 송금 경로를 시각화하여 고화질의 PNG 카드 이미지(Bytes)로 생성합니다.
    (해상도를 4배로 키우기 위해 모든 크기 단위를 2배로 확장 적용)
    """
    print("[blue]이미지 생성 시작: 정산 결과 데이터 파싱 중...[/blue]")
    
    # 1. 폰트 로드 및 설정 (Windows 기본 맑은 고딕 사용, 에러 대비 fallback 마련)
    font_title = None
    font_sec_title = None
    font_bold = None
    font_regular = None
    font_small = None
    
    # Windows 표준 한글 폰트 경로 목록
    bold_paths = [
        r"C:\Windows\Fonts\malgunbd.ttf",  # 맑은 고딕 Bold
        r"C:\Windows\Fonts\NanumGothicBold.ttf",
        r"C:\Windows\Fonts\batang.ttc"
    ]
    reg_paths = [
        r"C:\Windows\Fonts\malgun.ttf",    # 맑은 고딕 Regular
        r"C:\Windows\Fonts\NanumGothic.ttf",
        r"C:\Windows\Fonts\batang.ttc"
    ]
    
    # 볼드 폰트 적용 (글자 크기 2배 스케일링)
    for path in bold_paths:
        if os.path.exists(path):
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
        if os.path.exists(path):
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
    families_h = 170
    expenses_title_h = 90
    transfers_title_h = 90
    transfers_list_h = max(len(transfers) * 110 + 40, 120)
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
    box_bottom = box_top + 130
    draw.rounded_rectangle([(80, box_top), (width - 80, box_bottom)], radius=16, fill=(30, 41, 59), outline=(51, 65, 85), width=2)
    
    draw.text((110, box_top + 24), "참여 가족 구성 정보", font=font_bold, fill=(56, 189, 248))
    
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
    
    # 7. 지출 목록 섹션
    current_y = box_bottom + 50
    draw.text((80, current_y), "지출 항목 내역", font=font_sec_title, fill=(248, 250, 252))
    # 제목 밑 지시선
    draw.line([(80, current_y + 50), (340, current_y + 50)], fill=(56, 189, 248), width=4)
    
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
            
            # 가족 그룹 헤더 그리기 (예: "가율 (총 2건)")
            group_header = f"● {name} (총 {len(list_of_exps)}건)"
            draw.text((80, current_y), group_header, font=font_bold, fill=(56, 189, 248))
            
            group_total_str = f"{fam_total:,}원"
            try:
                bbox = font_bold.getbbox(group_total_str)
                w = bbox[2] - bbox[0]
            except AttributeError:
                w = 160
            draw.text((width - 80 - w, current_y), group_total_str, font=font_bold, fill=(56, 189, 248))
            
            # 헤더 아래 구분선
            draw.line([(80, current_y + 35), (width - 80, current_y + 35)], fill=(51, 65, 85), width=2)
            current_y += 45
            
            # 개별 지출 항목 그리기
            for exp in list_of_exps:
                memo_val = exp.get("memo", "")
                memo_str = f" [{memo_val}]" if memo_val else ""
                
                if exp.get("custom_shares") is not None and len(exp["custom_shares"]) > 0:
                    split_desc = "비율분담"
                else:
                    split_desc = "인원수비례" if exp.get("split_by_member", False) else "1/N"
                    
                item_text = f"  - {exp['item_name']}{memo_str} ({split_desc})"
                draw.text((80, current_y), item_text, font=font_regular, fill=(226, 232, 240))
                
                amt_str = f"{exp['amount']:,}원"
                try:
                    bbox = font_regular.getbbox(amt_str)
                    w = bbox[2] - bbox[0]
                except AttributeError:
                    w = 160
                draw.text((width - 110 - w, current_y), amt_str, font=font_regular, fill=(16, 185, 129))
                
                # 항목 구분 얇은 실선
                draw.line([(100, current_y + 32), (width - 100, current_y + 32)], fill=(30, 41, 59), width=1)
                current_y += 42
                
            # 가족 그룹 완료 후 여백 추가
            current_y += 15
            
    # 8. 송금 경로 안내 섹션
    current_y += 30
    draw.text((80, current_y), "최적 송금 가이드 (총무 중심 1방향 정산)", font=font_sec_title, fill=(56, 189, 248))
    # 제목 밑 지시선
    draw.line([(80, current_y + 50), (640, current_y + 50)], fill=(56, 189, 248), width=4)
    
    current_y += 80
    if not transfers:
        draw.text((110, current_y), "모든 정산 상태가 완료되어 송금할 내역이 없습니다.", font=font_bold, fill=(16, 185, 129))
        current_y += 70
    else:
        for debtor, creditor, amount in transfers:
            # 송금 카드 박스 그리기 (높이 45 -> 90)
            card_top = current_y
            card_bottom = card_top + 90
            draw.rounded_rectangle([(80, card_top), (width - 80, card_bottom)], radius=12, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
            
            # 채무자 (보내는 이)
            draw.text((110, card_top + 30), debtor, font=font_bold, fill=(244, 63, 94))
            
            # 보내기 화살표
            draw.text((300, card_top + 30), "보내기  ->", font=font_regular, fill=(148, 163, 184))
            
            # 채권자 (받는 이)
            draw.text((500, card_top + 30), creditor, font=font_bold, fill=(56, 189, 248))
            
            # 송금액
            amt_str = f"{amount:,} 원"
            try:
                bbox = font_bold.getbbox(amt_str)
                w = bbox[2] - bbox[0]
            except AttributeError:
                w = 160
            draw.text((width - 110 - w, card_top + 30), amt_str, font=font_bold, fill=(16, 185, 129))
            
            current_y += 100
            
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
