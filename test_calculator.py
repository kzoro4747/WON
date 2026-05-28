import unittest
from calculator import Family, Expense, SettlementCalculator
from logger_utils import print  # 룰에 맞춘 로깅 유틸리티 임포트

class TestSettlementCalculator(unittest.TestCase):
    """
    SettlementCalculator 클래스의 핵심 비즈니스 로직(정산금 계산 및 송금 경로 최적화)을
    검증하기 위한 단위 테스트 클래스입니다.
    """

    def setUp(self) -> None:
        """
        테스트 환경을 구성합니다. 5가족 정보를 생성하여 계산기를 초기화합니다.
        """
        print("[yellow]>>> 단위 테스트 셋업 시작 <<<[/yellow]")
        # 5가족 구성 (가족명, 인원수)
        self.families = [
            Family("김씨네", 4),
            Family("이씨네", 3),
            Family("박씨네", 2),
            Family("최씨네", 1),
            Family("정씨네", 5)
        ]
        self.calc = SettlementCalculator(self.families)

    def test_n_shares_split_equal(self) -> None:
        """
        1. 모든 가족이 동일하게 N분의 1(가족수 기준)로 나누어 내는 경우를 검증합니다.
        예: 김씨네가 100,000원을 내고 5가족이 다 참여. 각 가족은 20,000원씩 분담해야 함.
        """
        print("[magenta]테스트 시작: N분의 1 (가족수 기준) 균등 분담[/magenta]")
        
        expense = Expense(
            item_name="첫날 저녁식사",
            payer_name="김씨네",
            amount=100000,
            participants=["김씨네", "이씨네", "박씨네", "최씨네", "정씨네"],
            split_by_member=False
        )
        self.calc.add_expense(expense)
        
        # 순 잔액 확인
        # 김씨네: 지불 100,000 - 분담 20,000 = +80,000 (채권)
        # 나머지 4가족: 지불 0 - 분담 20,000 = -20,000 (채무)
        balances = self.calc.calculate_balances()
        self.assertAlmostEqual(balances["김씨네"], 80000.0)
        self.assertAlmostEqual(balances["이씨네"], -20000.0)
        
        # 최적 송금 경로 확인 (4가족이 각각 김씨네에게 20,000원씩 송금해야 함)
        transfers = self.calc.get_optimal_transfers()
        self.assertEqual(len(transfers), 4)
        for debtor, creditor, amount in transfers:
            self.assertEqual(creditor, "김씨네")
            self.assertEqual(amount, 20000)
            
        print("[green]테스트 성공: N분의 1 균등 분담 검증 완료[/green]")

    def test_split_by_member_count(self) -> None:
        """
        2. 인원수 비율로 지출을 분담하는 경우를 검증합니다.
        예: 이씨네가 150,000원을 내고 김씨네(4명), 이씨네(3명), 박씨네(2명), 최씨네(1명) 총 10명이 참여.
        인당 분담금 = 15,000원
        - 김씨네: 15,000 * 4 = 60,000 분담
        - 이씨네: 15,000 * 3 = 45,000 분담
        - 박씨네: 15,000 * 2 = 30,000 분담
        - 최씨네: 15,000 * 1 = 15,000 분담
        순 잔액:
        - 김씨네: -60,000
        - 이씨네: +105,000 (150,000 지불 - 45,000 분담)
        - 박씨네: -30,000
        - 최씨네: -15,000
        """
        print("[magenta]테스트 시작: 인원수 비례 분담[/magenta]")
        
        expense = Expense(
            item_name="펜션 숙박비",
            payer_name="이씨네",
            amount=150000,
            participants=["김씨네", "이씨네", "박씨네", "최씨네"],
            split_by_member=True
        )
        self.calc.add_expense(expense)
        
        balances = self.calc.calculate_balances()
        self.assertAlmostEqual(balances["김씨네"], -60000.0)
        self.assertAlmostEqual(balances["이씨네"], 105000.0)
        self.assertAlmostEqual(balances["박씨네"], -30000.0)
        self.assertAlmostEqual(balances["최씨네"], -15000.0)
        
        # 송금 경로 검증
        transfers = self.calc.get_optimal_transfers()
        self.assertEqual(len(transfers), 3) # 김씨네, 박씨네, 최씨네 -> 이씨네
        
        transfer_dict = {t[0]: t[2] for t in transfers}
        self.assertEqual(transfer_dict["김씨네"], 60000)
        self.assertEqual(transfer_dict["박씨네"], 30000)
        self.assertEqual(transfer_dict["최씨네"], 15000)
        
        print("[green]테스트 성공: 인원수 비례 분담 검증 완료[/green]")

    def test_complex_settlement(self) -> None:
        """
        3. 여러 지출이 얽혀있는 복잡한 시나리오에서 송금 최소화 알고리즘의 유효성을 검증합니다.
        김씨네가 100,000 지출 (5가족 N분의 1) -> 각 20,000
        박씨네가 60,000 지출 (김, 이, 박 3가족 N분의 1) -> 각 20,000
        
        지출 계산:
        - 김씨네: 지출 100,000 / 분담 (20,000 + 20,000) = 40,000 -> 순 잔액 +60,000
        - 이씨네: 지출 0 / 분담 (20,000 + 20,000) = 40,000 -> 순 잔액 -40,000
        - 박씨네: 지출 60,000 / 분담 (20,000 + 20,000) = 40,000 -> 순 잔액 +20,000
        - 최씨네: 지출 0 / 분담 20,000 -> 순 잔액 -20,000
        - 정씨네: 지출 0 / 분담 20,000 -> 순 잔액 -20,000
        
        채무자: 이씨네(40k), 최씨네(20k), 정씨네(20k)
        채권자: 김씨네(60k), 박씨네(20k)
        
        그리디 알고리즘 동작 예측:
        1. 가장 빚이 많은 이씨네(40k)가 가장 받을 돈이 많은 김씨네(60k)에게 40k 송금.
           - 이씨네 정산 완료. 김씨네 받을 돈 잔액 20k로 감소.
        2. 그 다음 최씨네(20k)가 김씨네(20k)에게 20k 송금.
           - 최씨네 및 김씨네 정산 완료.
        3. 정씨네(20k)가 박씨네(20k)에게 20k 송금.
           - 정씨네 및 박씨네 정산 완료.
           
        총 거래 건수: 3건 (단순 분배 시 7~8건에 비해 현저히 낮아짐)
        """
        print("[magenta]테스트 시작: 복합 지출 정산 및 송금 최소화[/magenta]")
        
        # 지출 1: 김씨네 100,000원 지불, 5가족 참여, N분의 1
        self.calc.add_expense(Expense("장보기", "김씨네", 100000, ["김씨네", "이씨네", "박씨네", "최씨네", "정씨네"], False))
        
        # 지출 2: 박씨네 60,000원 지불, 3가족(김, 이, 박) 참여, N분의 1
        self.calc.add_expense(Expense("주유비", "박씨네", 60000, ["김씨네", "이씨네", "박씨네"], False))
        
        balances = self.calc.calculate_balances()
        self.assertAlmostEqual(balances["김씨네"], 60000.0)
        self.assertAlmostEqual(balances["이씨네"], -40000.0)
        self.assertAlmostEqual(balances["박씨네"], 20000.0)
        self.assertAlmostEqual(balances["최씨네"], -20000.0)
        self.assertAlmostEqual(balances["정씨네"], -20000.0)
        
        transfers = self.calc.get_optimal_transfers()
        self.assertEqual(len(transfers), 3)
        
        # 예상 송금 목록 비교 검증
        expected_transfers = [
            ("이씨네", "김씨네", 40000),
            ("최씨네", "김씨네", 20000),
            ("정씨네", "박씨네", 20000)
        ]
        
        # 순서가 다를 수 있으므로 셋(set)으로 비교
        self.assertEqual(set(transfers), set(expected_transfers))
        print("[green]테스트 성공: 복합 지출 정산 검증 완료[/green]")

if __name__ == "__main__":
    unittest.main()
