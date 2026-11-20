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
        self.assertEqual(len(transfers), 4)
        
        # 예상 송금 목록 비교 검증 (총무 김씨네 중심 송금)
        expected_transfers = [
            ("이씨네", "김씨네", 40000),
            ("최씨네", "김씨네", 20000),
            ("정씨네", "김씨네", 20000),
            ("김씨네", "박씨네", 20000)
        ]
        
        # 순서가 다를 수 있으므로 셋(set)으로 비교
        self.assertEqual(set(transfers), set(expected_transfers))
        print("[green]테스트 성공: 복합 지출 정산 검증 완료[/green]")

    def test_custom_ratio_split(self) -> None:
        """
        4. 사용자 지정 가중치 비율로 지출을 분담하는 경우를 검증합니다.
        김씨네가 120,000원을 내고 김씨네, 이씨네, 박씨네가 참여.
        사용자 지정 비율: 김씨네: 3, 이씨네: 2, 박씨네: 1 (총 6가중치)
        분담 계산:
        - 김씨네: 120,000 * 3/6 = 60,000 분담
        - 이씨네: 120,000 * 2/6 = 40,000 분담
        - 박씨네: 120,000 * 1/6 = 20,000 분담
        순 잔액:
        - 김씨네: 120,000 (지출) - 60,000 = +60,000
        - 이씨네: 0 - 40,000 = -40,000
        - 박씨네: 0 - 20,000 = -20,000
        """
        print("[magenta]테스트 시작: 사용자 지정 비율 분담[/magenta]")
        custom_shares = {"김씨네": 3.0, "이씨네": 2.0, "박씨네": 1.0}
        expense = Expense(
            item_name="특별 장보기",
            payer_name="김씨네",
            amount=120000,
            participants=["김씨네", "이씨네", "박씨네"],
            split_by_member=False,
            custom_shares=custom_shares
        )
        self.calc.add_expense(expense)
        
        balances = self.calc.calculate_balances()
        self.assertAlmostEqual(balances["김씨네"], 60000.0)
        self.assertAlmostEqual(balances["이씨네"], -40000.0)
        self.assertAlmostEqual(balances["박씨네"], -20000.0)
        
        transfers = self.calc.get_optimal_transfers()
        self.assertEqual(len(transfers), 2) # 이씨네 -> 김씨네, 박씨네 -> 김씨네
        
        transfer_dict = {t[0]: t[2] for t in transfers}
        self.assertEqual(transfer_dict["이씨네"], 40000)
        self.assertEqual(transfer_dict["박씨네"], 20000)
        print("[green]테스트 성공: 사용자 지정 비율 분담 검증 완료[/green]")

    def test_custom_ratio_rounding_remainder_to_top_spender(self) -> None:
        """
        5. 비율 합이 99.9%(33.3% × 3)일 때 끝전이 '가장 많이 지출한 참여 가족'에게 남는지 검증합니다.
        김씨네가 100,000원 지불, 김·이·박 33.3%씩 → 정규화하면 1/3씩 = 33,333.33원
        - 다른 가족 몫은 올림: 이씨네·박씨네 33,334원씩
        - 최다 지출 가족 김씨네는 100,000 - 66,668 = 33,332원 → 끝전 1원(33,333원 대비)이 김씨네에게 남음
        순 잔액: 김씨네 +66,668 / 이씨네 -33,334 / 박씨네 -33,334 (합계 0원)
        """
        print("[magenta]테스트 시작: 비율 분담 끝전 → 최다 지출 가족에게 남음[/magenta]")
        shares = {"김씨네": 33.3, "이씨네": 33.3, "박씨네": 33.3}
        self.calc.add_expense(Expense("숙박비", "김씨네", 100000, ["김씨네", "이씨네", "박씨네"], custom_shares=shares))

        balances = self.calc.calculate_balances()
        self.assertAlmostEqual(balances["김씨네"], 66668.0)
        self.assertAlmostEqual(balances["이씨네"], -33334.0)
        self.assertAlmostEqual(balances["박씨네"], -33334.0)
        self.assertAlmostEqual(sum(balances.values()), 0.0)

        notes = self.calc.get_share_rounding_notes()
        self.assertEqual(notes, [{"item_name": "숙박비", "tail": 1, "receiver": "김씨네"}])
        print("[green]테스트 성공: 끝전이 최다 지출 가족에게 남음[/green]")

    def test_custom_ratio_rounding_tie_goes_to_manager(self) -> None:
        """
        6. 최다 지출 가족이 동점이면 비율 분담 끝전이 총무에게 남는지 검증합니다.
        김씨네·이씨네가 각각 50,000원씩 지불(동점), 박씨네가 10,000원을 김·이·박 33.3%씩 비율 분담으로 지불
        - 10,000원 / 3 = 3,333.33원 → 끝전 받을 가족 외에는 3,334원씩(올림)
        - 총무가 이씨네면 이씨네가 3,332원만 냄(끝전이 이씨네에게), 총무를 정하지 않으면 가족 목록 순서상 앞인 김씨네에게
        """
        print("[magenta]테스트 시작: 비율 분담 끝전 동점 시 총무 우선[/magenta]")
        self.calc.add_expense(Expense("장보기", "김씨네", 50000, ["김씨네", "이씨네"]))
        self.calc.add_expense(Expense("주유비", "이씨네", 50000, ["김씨네", "이씨네"]))
        shares = {"김씨네": 33.3, "이씨네": 33.3, "박씨네": 33.3}
        self.calc.add_expense(Expense("카페", "박씨네", 10000, ["김씨네", "이씨네", "박씨네"], custom_shares=shares))

        self.assertEqual(self.calc.get_share_rounding_notes(manager_name="이씨네")[0]["receiver"], "이씨네")
        self.assertEqual(self.calc.get_share_rounding_notes()[0]["receiver"], "김씨네")

        # 총무 지정 시 송금액 합계가 정확히 맞는지(받는 돈 = 보내는 돈 + 총무 몫) 확인
        balances = self.calc.calculate_balances(manager_name="이씨네")
        self.assertAlmostEqual(balances["이씨네"], 50000 - 25000 - 25000 - 3332)
        self.assertAlmostEqual(balances["김씨네"], 50000 - 25000 - 25000 - 3334)
        self.assertAlmostEqual(sum(balances.values()), 0.0)
        print("[green]테스트 성공: 동점 시 총무에게 비율 분담 끝전이 남음[/green]")

    def test_custom_ratio_zero_total_falls_back_to_default_split(self) -> None:
        """
        7. 비율 합이 0%인 비율 분담 지출(백업 파일로만 유입 가능)을 기본 분담(1/N)으로 대신 나누는지 검증합니다.
        김씨네가 50,000원 지불, 김·이 비율 0%/0% → 1/N으로 25,000원씩
        순 잔액: 김씨네 +25,000 / 이씨네 -25,000 (예전에는 김씨네 +50,000만 남아 합계가 맞지 않았음)
        """
        print("[magenta]테스트 시작: 비율 합 0% → 기본 분담 대체[/magenta]")
        zero_shares = {"김씨네": 0.0, "이씨네": 0.0}
        self.calc.add_expense(Expense("간식", "김씨네", 50000, ["김씨네", "이씨네"], custom_shares=zero_shares))

        balances = self.calc.calculate_balances()
        self.assertAlmostEqual(balances["김씨네"], 25000.0)
        self.assertAlmostEqual(balances["이씨네"], -25000.0)
        self.assertAlmostEqual(sum(balances.values()), 0.0)
        self.assertEqual(self.calc.get_zero_share_fallbacks(), [{"item_name": "간식", "fallback": "1/N"}])
        print("[green]테스트 성공: 비율 합 0% 지출이 1/N으로 대체됨[/green]")

    def test_transfer_rounding_leaves_tail_to_manager(self) -> None:
        """
        8. 1/N로 나누어떨어지지 않을 때 끝전이 총무에게 남는지 검증합니다.
        김씨네가 10,000원을 내고 김·이·박 1/N → 정확히는 3,333.33원씩
        - 총무가 김씨네면: 이씨네·박씨네가 똑같이 3,334원씩 보냄(올림) → 총무 6,668원 받음
        - 총무가 이씨네면: 박씨네는 3,334원 보내고(올림), 김씨네는 6,666원 돌려받음(내림)
        """
        print("[magenta]테스트 시작: 송금액 올림/내림으로 끝전은 총무에게[/magenta]")
        self.calc.add_expense(Expense("간식", "김씨네", 10000, ["김씨네", "이씨네", "박씨네"]))

        transfers = self.calc.get_optimal_transfers(manager_name="김씨네")
        self.assertEqual(set(transfers), {("이씨네", "김씨네", 3334), ("박씨네", "김씨네", 3334)})

        transfers = self.calc.get_optimal_transfers(manager_name="이씨네")
        self.assertEqual(set(transfers), {("박씨네", "이씨네", 3334), ("이씨네", "김씨네", 6666)})
        print("[green]테스트 성공: 끝전이 총무에게 남음[/green]")

    def test_transfer_rounding_ignores_float_error(self) -> None:
        """
        9. 나누어떨어지는 금액에서 float 오차 때문에 1원이 더 붙지 않는지 검증합니다.
        0.1원 단위 비율처럼 오차가 생기기 쉬운 값: 김씨네가 30,000원, 3가족 인원수 비례(4·3·2명 → 9명)
        → 13,333.33 / 10,000 / 6,666.67 이 아니라, 이씨네 몫 10,000원은 정확히 10,000원이어야 함
        """
        print("[magenta]테스트 시작: 송금액 float 오차 보정[/magenta]")
        self.calc.add_expense(Expense("장보기", "김씨네", 30000, ["김씨네", "이씨네", "박씨네"], split_by_member=True))
        transfers = {t[0]: t[2] for t in self.calc.get_optimal_transfers(manager_name="김씨네")}
        self.assertEqual(transfers["이씨네"], 10000)
        self.assertEqual(transfers["박씨네"], 6667)
        print("[green]테스트 성공: float 오차로 1원이 더 붙지 않음[/green]")

if __name__ == "__main__":
    unittest.main()
