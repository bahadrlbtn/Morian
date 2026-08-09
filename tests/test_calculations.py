import unittest
from app.finance.calculations import calculate_cagr, calculate_fcf, safe_divide, weighted_average
from app.finance.scoring import calculate_stock_score, calculate_quality_score, detect_red_flags
from app.config import ScoreWeights
from app.models import ScoreResult


class CalculationTests(unittest.TestCase):
    def test_safe_divide_preserves_missing(self):
        self.assertIsNone(safe_divide(None, 2))
        self.assertIsNone(safe_divide(2, 0))

    def test_cagr(self):
        self.assertAlmostEqual(calculate_cagr(100, 161.051, 5), .10, places=3)
        self.assertIsNone(calculate_cagr(-1, 10, 3))

    def test_fcf_uses_capex_absolute_value(self):
        self.assertEqual(calculate_fcf(100, 30), 70)
        self.assertEqual(calculate_fcf(100, -30), 70)

    def test_missing_components_reduce_coverage_not_score(self):
        score, coverage = weighted_average({"a":80,"b":None},{"a":1,"b":1})
        self.assertEqual(score, 80)
        self.assertEqual(coverage, .5)

    def test_composite_renormalizes_available_scores(self):
        scores = {"quality":ScoreResult(score=80,coverage=1,components={}),"growth":ScoreResult(score=None,coverage=0,components={}),"valuation":ScoreResult(score=60,coverage=1,components={}),"financial_health":ScoreResult(score=70,coverage=1,components={}),"momentum":ScoreResult(score=50,coverage=1,components={})}
        score, coverage = calculate_stock_score(scores, ScoreWeights())
        self.assertAlmostEqual(score, 68.67, places=2)
        self.assertEqual(coverage, .75)

    def test_lower_leverage_scores_better(self):
        low = calculate_quality_score({"net_debt_ebitda":0}).components["balance_sheet"]
        high = calculate_quality_score({"net_debt_ebitda":4}).components["balance_sheet"]
        self.assertGreater(low, high)

    def test_sparse_category_is_not_scored(self):
        result=calculate_quality_score({"roic":.30})
        self.assertIsNone(result.score)
        self.assertLess(result.coverage,.40)

    def test_red_flags_ignore_null(self):
        self.assertEqual(detect_red_flags({"free_cash_flow":None}), [])
        self.assertEqual(detect_red_flags({"free_cash_flow":-1})[0].severity, "HIGH")


if __name__ == "__main__": unittest.main()
