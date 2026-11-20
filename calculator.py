import math
from typing import Any, List, Dict, Tuple, Optional
from rich.markup import escape  # 가족명·항목명 등 사용자 입력이 rich 마크업으로 해석되지 않도록 이스케이프
from logger_utils import print  # 규칙에 따라 rich 기반의 커스텀 로거 임포트

class Family:
    """
    모임에 참여하는 가족 정보를 저장하는 클래스입니다.
    """
    def __init__(self, name: str, member_count: int):
        self.name: str = name  # 가족명 (예: '철수네', '길동이네')
        self.member_count: int = member_count  # 가족 구성원 수
        
    def __repr__(self) -> str:
        return f"Family(name={self.name}, members={self.member_count})"


class Expense:
    """
    모임 도중 발생한 개별 지출 내역을 저장하는 클래스입니다.
    """
    def __init__(self, item_name: str, payer_name: str, amount: int, participants: List[str], split_by_member: bool = False, memo: str = "", custom_shares: Dict[str, float] = None):
        self.item_name: str = item_name  # 지출 항목 (예: '숙박비', '첫날 저녁')
        self.payer_name: str = payer_name  # 실제로 돈을 지불한 가족명
        self.amount: int = amount  # 지출 금액 (원)
        self.participants: List[str] = participants  # 이 지출에 참여한 가족들의 이름 목록
        self.split_by_member: bool = split_by_member  # True 이면 참여 인원수 비율로 분담, False 이면 가족수 N분의 1로 분담
        self.memo: str = memo  # 세부 내역 메모
        self.custom_shares: Dict[str, float] = custom_shares  # 사용자 지정 분담 비율 가중치 (가족명 -> 비율가중치)
        
    def __repr__(self) -> str:
        return f"Expense(item={self.item_name}, payer={self.payer_name}, amount={self.amount}, split_by_member={self.split_by_member}, memo={self.memo}, custom_shares={self.custom_shares})"


class SettlementCalculator:
    """
    가족들의 지출 및 분담 내역을 기반으로 최종 정산(송금 관계)을 계산하는 클래스입니다.
    """
    def __init__(self, families: List[Family]):
        self.families: Dict[str, Family] = {f.name: f for f in families}
        self.expenses: List[Expense] = []
        print(f"[green]SettlementCalculator 초기화 완료:[/green] 참여 가족 {len(families)}가구")
        
    def add_expense(self, expense: Expense) -> None:
        """
        지출 내역을 추가합니다.
        """
        if expense.payer_name not in self.families:
            raise ValueError(f"존재하지 않는 가족명(지불자): {expense.payer_name}")
        for p in expense.participants:
            if p not in self.families:
                raise ValueError(f"존재하지 않는 가족명(참여자): {p}")
                
        self.expenses.append(expense)
        print(f"[blue]지출 추가됨:[/blue] {escape(expense.item_name)} | 지불자: {escape(expense.payer_name)} | 금액: {expense.amount:,}원 | 참여가족: {len(expense.participants)}가구")

    def remove_expense(self, index: int) -> None:
        """
        특정 인덱스의 지출 내역을 삭제합니다.
        """
        if 0 <= index < len(self.expenses):
            removed = self.expenses.pop(index)
            print(f"[yellow]지출 삭제됨:[/yellow] {escape(removed.item_name)} ({removed.amount:,}원)")
        else:
            raise IndexError("유효하지 않은 지출 인덱스입니다.")

    def get_total_paid(self) -> Dict[str, int]:
        """
        가족별로 모임 전체에서 실제로 지불한 총액(원)을 계산합니다.
        비율 분담의 원 단위 차액을 받을 '가장 많이 지출한 가족'을 고르는 기준으로 쓰입니다.

        Returns:
            Dict[str, int]: {가족명: 총 지불액}. 지출이 없는 가족은 0원.
        """
        paid: Dict[str, int] = {name: 0 for name in self.families}
        for exp in self.expenses:
            paid[exp.payer_name] += exp.amount
        return paid

    def find_remainder_receiver(self, participants: List[str], manager_name: Optional[str] = None) -> str:
        """
        비율 분담을 원 단위로 반올림한 뒤 남거나 넘친 금액을 떠안을 가족을 고릅니다.

        선정 규칙:
            1. 해당 지출의 참여 가족 중 모임 전체 총 지불액이 가장 큰 가족
            2. 동점이면, 총무(manager_name)가 동점자 안에 있을 때 총무
            3. 그래도 정해지지 않으면 가족 목록 순서상 가장 앞에 있는 가족

        Args:
            participants (List[str]): 해당 지출의 참여 가족 목록 (비어 있으면 안 됨)
            manager_name (Optional[str]): 대표 수납자(총무) 가족명. 동점 처리에만 사용.

        Returns:
            str: 차액을 반영할 가족명
        """
        paid = self.get_total_paid()
        top_amount = max(paid.get(p, 0) for p in participants)
        # 가족 목록(self.families) 순서를 유지한 채 동점자를 모음
        tied = [name for name in self.families if name in participants and paid.get(name, 0) == top_amount]
        if manager_name is not None and manager_name in tied:
            return manager_name
        return tied[0]

    def split_custom_shares(self, exp: "Expense", manager_name: Optional[str] = None) -> Tuple[Dict[str, int], int, Optional[str]]:
        """
        사용자 지정 비율 분담 지출의 가족별 분담액을 원 단위로 계산합니다.

        계산 순서:
            1. 각 참여 가족의 비율을 참여 가족 비율 합으로 나눠 정규화
               (합이 99.9%처럼 100%에서 조금 벗어나도 비율대로 지출액 전체를 나눔)
            2. 가족별 분담액을 원 단위로 반올림(0.5원 이상 올림)
            3. 반올림 때문에 생긴 차액(지출액 - 반올림한 분담액 합)을
               find_remainder_receiver()가 고른 가족의 분담액에 더함 (차액이 음수면 빼짐)

        Args:
            exp (Expense): custom_shares가 있는 지출
            manager_name (Optional[str]): 대표 수납자(총무). 차액 받을 가족이 동점일 때 사용.

        Returns:
            Tuple[Dict[str, int], int, Optional[str]]:
                (가족별 분담액(차액 반영 후), 차액(원, 음수 가능), 차액을 반영한 가족 또는 None(차액 0원))
                참여 가족 비율 합이 0 이하이면 ({}, 0, None)을 돌려주어 아무에게도 분담하지 않습니다(기존 동작 유지).
        """
        shares_cfg = exp.custom_shares or {}
        total_shares = sum(shares_cfg.get(p, 0.0) for p in exp.participants)
        if total_shares <= 0:
            return {}, 0, None

        shares: Dict[str, int] = {
            p: math.floor(shares_cfg.get(p, 0.0) / total_shares * exp.amount + 0.5)
            for p in exp.participants
        }
        remainder = exp.amount - sum(shares.values())
        if remainder == 0:
            return shares, 0, None

        receiver = self.find_remainder_receiver(exp.participants, manager_name)
        shares[receiver] += remainder
        print(f"[cyan]비율 분담 원 단위 차액 반영:[/cyan] {escape(exp.item_name)} | 차액 {remainder:+,}원 → {escape(receiver)} (최다 지출 가족, 동점 시 총무)")
        return shares, remainder, receiver

    def get_share_rounding_notes(self, manager_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        원 단위 반올림 차액이 생긴 비율 분담 지출 목록을 돌려줍니다. (화면 안내·카카오톡 공지·이미지 주석용)

        Args:
            manager_name (Optional[str]): 대표 수납자(총무). 정산 계산과 같은 값을 넘겨야 결과가 일치합니다.

        Returns:
            List[Dict[str, Any]]: [{"item_name": 항목명, "remainder": 차액(원, 음수 가능), "receiver": 반영한 가족}, ...]
        """
        notes: List[Dict[str, Any]] = []
        for exp in self.expenses:
            if not exp.participants or not exp.custom_shares:
                continue
            _, remainder, receiver = self.split_custom_shares(exp, manager_name)
            if remainder != 0 and receiver is not None:
                notes.append({"item_name": exp.item_name, "remainder": remainder, "receiver": receiver})
        return notes

    def pick_auto_manager(self) -> str:
        """
        총무를 '자동 선정'할 때 쓸 가족(순 잔액이 가장 큰 채권자)을 고릅니다.
        총무가 아직 없는 상태로 1차 잔액을 계산해 고르므로, 비율 분담 차액의 동점 처리는 가족 목록 순서를 따릅니다.

        Returns:
            str: 자동 선정된 총무 가족명 (가족이 없으면 빈 문자열)
        """
        balances = self.calculate_balances()
        if not balances:
            return ""
        return max(balances, key=lambda k: balances[k])

    def calculate_balances(self, manager_name: Optional[str] = None) -> Dict[str, float]:
        """
        각 가족이 총 지출한 금액에서 분담해야 할 금액을 빼서 순 잔액(Net Balance)을 계산합니다.
        - 결과값이 양수(> 0)이면 돌려받아야 하는 돈(채권)이 있는 가족입니다.
        - 결과값이 음수(< 0)이면 더 내야 하는 돈(채무)이 있는 가족입니다.

        Args:
            manager_name (Optional[str]): 대표 수납자(총무). 사용자 지정 비율 분담의 원 단위 차액을 받을 가족이
                동점일 때만 영향을 줍니다. 화면 표시와 송금 계산에 같은 값을 넘겨야 결과가 일치합니다.
        """
        # 모든 가족의 순 잔액 초기화 (0.0 원)
        balances: Dict[str, float] = {name: 0.0 for name in self.families}
        
        # 1. 지불한 금액 가산
        for exp in self.expenses:
            balances[exp.payer_name] += exp.amount
            
        # 2. 분담해야 할 금액 감산
        for exp in self.expenses:
            if not exp.participants:
                continue
                
            # 2.1. 사용자 지정 비율 분담이 정의되어 있는 경우 우선 분배
            #      원 단위로 나누고, 남거나 넘친 금액은 최다 지출 가족(동점 시 총무)에게 반영 (split_custom_shares 참고)
            if exp.custom_shares and len(exp.custom_shares) > 0:
                shares, _, _ = self.split_custom_shares(exp, manager_name)
                for p, share in shares.items():
                    balances[p] -= share
                continue
                
            # 2.2. 기존 기본 분담 로직
            if exp.split_by_member:
                # 인원수 비례 분담 방식
                total_members = sum(self.families[p].member_count for p in exp.participants)
                if total_members == 0:
                    continue
                for p in exp.participants:
                    member_share = (self.families[p].member_count / total_members) * exp.amount
                    balances[p] -= member_share
            else:
                # 가족수 균등(N분의 1) 분담 방식
                family_share = exp.amount / len(exp.participants)
                for p in exp.participants:
                    balances[p] -= family_share
                    
        print(f"[magenta]가족별 순 잔액 계산 완료:[/magenta] {escape(str(balances))}")
        return balances

    def get_optimal_transfers(self, manager_name: Optional[str] = None) -> List[Tuple[str, str, int]]:
        """
        대표 수납자(총무) 중심의 1방향 송금 가이드를 도출합니다.
        사용자가 대표 수납자(manager_name)를 직접 지정할 수 있으며,
        지정하지 않은 경우(None) 순 잔액이 가장 높은 채권자를 자동으로 '대표 수납자'로 선정합니다.
        
        - 돈을 보내야 하는 모든 사람(채무자)은 '대표 수납자'에게 1번만 송금합니다.
        - 돈을 돌려받아야 하는 다른 채권자들은 '대표 수납자'로부터 1번만 돌려받습니다.
        - 결과적으로 총무를 제외한 모든 가족은 정확히 '단 1회'의 거래로 정산이 완료됩니다.
        
        Args:
            manager_name (Optional[str]): 지정할 대표 수납자(총무) 가족명. None이면 자동 선정.
            
        Returns:
            List[Tuple[str, str, int]]: (보내는 사람, 받는 사람, 금액)의 리스트
        """
        if not self.families:
            return []

        # 사용자가 지정한 수납자가 유효한 가족명인지 확인 후 설정, 아니면 최대 채권자로 자동 지정
        # (총무가 정해진 뒤에 잔액을 계산해야 비율 분담 차액의 동점 처리가 총무 기준으로 맞춰짐)
        if manager_name and manager_name in self.families:
            selected_manager = manager_name
            balances = self.calculate_balances(selected_manager)
            manager_bal = balances[selected_manager]
            print(f"[cyan]대표 수납자(총무) 수동 지정됨:[/cyan] {escape(selected_manager)} (잔액: {manager_bal:,.1f}원)")
        else:
            selected_manager = self.pick_auto_manager()
            balances = self.calculate_balances(selected_manager)
            manager_bal = balances[selected_manager]
            print(f"[cyan]대표 수납자(총무) 자동 지정됨:[/cyan] {escape(selected_manager)} (잔액: {manager_bal:,.1f}원)")
        
        incoming_transfers: List[Tuple[str, str, int]] = []
        outgoing_transfers: List[Tuple[str, str, int]] = []
        
        # 다른 모든 멤버들의 정산 가이드 작성 (수납 입금 내역 먼저, 이후 환급 내역 순으로 정렬)
        for name, bal in balances.items():
            if name == selected_manager:
                continue
                
            # 원 단위 반올림 처리
            amount = int(round(bal))
            
            if amount < 0:
                # 음수 잔액인 경우: 총무(수납자)에게 송금
                incoming_transfers.append((name, selected_manager, -amount))
                print(f"[cyan]정산 송금 가이드 (수납자에게 입금):[/cyan] {escape(name)} -> {escape(selected_manager)} : {-amount:,}원")
            elif amount > 0:
                # 양수 잔액인 경우: 총무(수납자)에게서 돌려받음 (수납자가 더 쓴 사람에게 환급)
                outgoing_transfers.append((selected_manager, name, amount))
                print(f"[cyan]정산 송금 가이드 (수납자가 환급):[/cyan] {escape(selected_manager)} -> {escape(name)} : {amount:,}원")
                
        return incoming_transfers + outgoing_transfers
