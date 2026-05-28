from typing import List, Dict, Tuple
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
    def __init__(self, item_name: str, payer_name: str, amount: int, participants: List[str], split_by_member: bool = False, memo: str = ""):
        self.item_name: str = item_name  # 지출 항목 (예: '숙박비', '첫날 저녁')
        self.payer_name: str = payer_name  # 실제로 돈을 지불한 가족명
        self.amount: int = amount  # 지출 금액 (원)
        self.participants: List[str] = participants  # 이 지출에 참여한 가족들의 이름 목록
        self.split_by_member: bool = split_by_member  # True 이면 참여 인원수 비율로 분담, False 이면 가족수 N분의 1로 분담
        self.memo: str = memo  # 세부 내역 메모
        
    def __repr__(self) -> str:
        return f"Expense(item={self.item_name}, payer={self.payer_name}, amount={self.amount}, split_by_member={self.split_by_member}, memo={self.memo})"


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
        print(f"[blue]지출 추가됨:[/blue] {expense.item_name} | 지불자: {expense.payer_name} | 금액: {expense.amount:,}원 | 참여가족: {len(expense.participants)}가구")

    def remove_expense(self, index: int) -> None:
        """
        특정 인덱스의 지출 내역을 삭제합니다.
        """
        if 0 <= index < len(self.expenses):
            removed = self.expenses.pop(index)
            print(f"[yellow]지출 삭제됨:[/yellow] {removed.item_name} ({removed.amount:,}원)")
        else:
            raise IndexError("유효하지 않은 지출 인덱스입니다.")

    def calculate_balances(self) -> Dict[str, float]:
        """
        각 가족이 총 지출한 금액에서 분담해야 할 금액을 빼서 순 잔액(Net Balance)을 계산합니다.
        - 결과값이 양수(> 0)이면 돌려받아야 하는 돈(채권)이 있는 가족입니다.
        - 결과값이 음수(< 0)이면 더 내야 하는 돈(채무)이 있는 가족입니다.
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
                    
        print(f"[magenta]가족별 순 잔액 계산 완료:[/magenta] {balances}")
        return balances

    def get_optimal_transfers(self) -> List[Tuple[str, str, int]]:
        """
        대표 수납자(총무) 중심의 1방향 송금 가이드를 도출합니다.
        가장 지출이 큰 사람(순 잔액이 가장 높은 채권자)을 자동으로 '대표 수납자'로 선정합니다.
        
        - 돈을 보내야 하는 모든 사람(채무자)은 '대표 수납자'에게 1번만 송금합니다.
        - 돈을 돌려받아야 하는 다른 채권자들은 '대표 수납자'로부터 1번만 돌려받습니다.
        - 결과적으로 총무를 제외한 모든 가족은 정확히 '단 1회'의 거래로 정산이 완료됩니다.
        
        Returns:
            List[Tuple[str, str, int]]: (보내는 사람, 받는 사람, 금액)의 리스트
        """
        balances = self.calculate_balances()
        
        if not balances:
            return []
            
        # 순 잔액이 가장 높은 사람을 대표 수납자(총무)로 자동 지정
        manager_name = max(balances, key=lambda k: balances[k])
        manager_bal = balances[manager_name]
        
        print(f"[cyan]대표 수납자(총무) 자동 지정됨:[/cyan] {manager_name} (잔액: {manager_bal:,.1f}원)")
        
        transfers: List[Tuple[str, str, int]] = []
        
        # 다른 모든 멤버들의 정산 가이드 작성
        for name, bal in balances.items():
            if name == manager_name:
                continue
                
            # 원 단위 반올림 처리
            amount = int(round(bal))
            
            if amount < 0:
                # 음수 잔액인 경우: 총무에게 송금
                transfers.append((name, manager_name, -amount))
                print(f"[cyan]정산 송금 가이드 (채무):[/cyan] {name} -> {manager_name} : {-amount:,}원")
            elif amount > 0:
                # 양수 잔액인 경우: 총무에게서 돌려받음 (총무가 뱉어내는 구조)
                transfers.append((manager_name, name, amount))
                print(f"[cyan]정산 송금 가이드 (채권):[/cyan] {manager_name} -> {name} : {amount:,}원")
                
        return transfers
