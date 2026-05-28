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
    def __init__(self, item_name: str, payer_name: str, amount: int, participants: List[str], split_by_member: bool = False):
        self.item_name: str = item_name  # 지출 항목 (예: '숙박비', '첫날 저녁')
        self.payer_name: str = payer_name  # 실제로 돈을 지불한 가족명
        self.amount: int = amount  # 지출 금액 (원)
        self.participants: List[str] = participants  # 이 지출에 참여한 가족들의 이름 목록
        self.split_by_member: bool = split_by_member  # True 이면 참여 인원수 비율로 분담, False 이면 가족수 N분의 1로 분담
        
    def __repr__(self) -> str:
        return f"Expense(item={self.item_name}, payer={self.payer_name}, amount={self.amount}, split_by_member={self.split_by_member})"


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
        그리디(Greedy) 알고리즘을 사용하여 송금 횟수를 최소화하는 최적의 송금 경로를 도출합니다.
        
        Returns:
            List[Tuple[str, str, int]]: (보내는 사람, 받는 사람, 금액)의 리스트
        """
        balances = self.calculate_balances()
        
        # 채무자(Debtor, 잔액 < 0)와 채권자(Creditor, 잔액 > 0) 분류
        debtors: List[Tuple[str, float]] = []
        creditors: List[Tuple[str, float]] = []
        
        # 소수점 오차 방지를 위해 아주 작은 값(1원 미만)은 0으로 처리
        for name, bal in balances.items():
            if bal < -0.1:
                # 계산 편의를 위해 채무액을 양수로 저장
                debtors.append((name, -bal))
            elif bal > 0.1:
                creditors.append((name, bal))
                
        # 빚이 많은 순서, 받아야 할 돈이 많은 순서로 정렬
        debtors.sort(key=lambda x: x[1], reverse=True)
        creditors.sort(key=lambda x: x[1], reverse=True)
        
        transfers: List[Tuple[str, str, int]] = []
        
        debt_idx = 0
        cred_idx = 0
        
        # 채무자와 채권자 목록이 바닥날 때까지 매칭 진행
        while debt_idx < len(debtors) and cred_idx < len(creditors):
            debtor_name, debt_amt = debtors[debt_idx]
            creditor_name, cred_amt = creditors[cred_idx]
            
            # 송금액은 채무액과 채권액 중 최소값으로 결정
            transfer_amount = min(debt_amt, cred_amt)
            # 원 단위 반올림 처리
            final_transfer = int(round(transfer_amount))
            
            if final_transfer > 0:
                transfers.append((debtor_name, creditor_name, final_transfer))
                print(f"[cyan]정산 송금 매칭:[/cyan] {debtor_name} -> {creditor_name} : {final_transfer:,}원")
                
            # 잔액 차감 및 인덱스 이동
            debt_amt -= transfer_amount
            cred_amt -= transfer_amount
            
            if debt_amt < 0.1:
                debt_idx += 1
            else:
                debtors[debt_idx] = (debtor_name, debt_amt)
                
            if cred_amt < 0.1:
                cred_idx += 1
            else:
                creditors[cred_idx] = (creditor_name, cred_amt)
                
        print(f"[green]최종 송금 경로 도출 완료:[/green] 총 {len(transfers)}건의 거래 발생")
        return transfers
