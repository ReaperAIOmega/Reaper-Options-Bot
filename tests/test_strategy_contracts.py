from datetime import date

from contracts import select_contract
from strategy import BEAR, BULL, failed_2u, fvg_retest, ftfc_direction, two_one_two
from tests.fixtures import chain


def c(o, h, l, cl):
    return {"open": o, "high": h, "low": l, "close": cl}


def test_two_one_two_both_directions_and_none():
    assert two_one_two([c(10, 11, 5, 6), c(6, 10, 6, 9), c(9, 12, 8, 11)]) == BULL
    assert two_one_two([c(6, 11, 5, 10), c(9, 10, 6, 7), c(7, 8, 4, 5)]) == BEAR
    assert two_one_two([c(10, 11, 5, 6), c(6, 12, 6, 9), c(9, 12, 8, 11)]) is None  # not an inside bar


def test_failed_2u_is_bearish_only():
    assert failed_2u([c(1, 2, 1, 2), c(2, 3, 2, 3), c(3.5, 3.6, 2, 2.5)]) == BEAR
    assert failed_2u([c(2, 2, 1, 1), c(2, 3, 2, 3), c(3.5, 3.6, 2, 2.5)]) is None


def test_fvg_retest_uses_three_candle_gap():
    assert fvg_retest([c(9, 10, 8, 10), c(10, 13, 10, 13), c(13, 14, 12, 14), c(14, 14, 11, 13)]) == BULL
    assert fvg_retest([c(13, 14, 12, 12), c(12, 12, 9, 9), c(9, 10, 8, 8), c(8, 11, 8, 10)]) == BEAR
    assert fvg_retest([c(9, 10, 8, 10), c(10, 11, 9, 11), c(11, 12, 9.5, 12), c(12, 12, 9, 11)]) is None  # no gap


def test_ftfc_requires_agreement_on_every_timeframe():
    up, down = [c(1, 2, 1, 2)], [c(2, 2, 1, 1)]
    assert ftfc_direction({"a": up, "b": up}) == BULL
    assert ftfc_direction({"a": down, "b": down}) == BEAR
    assert ftfc_direction({"a": up, "b": down}) is None
    assert ftfc_direction({"a": up}) is None
    assert ftfc_direction({"a": up, "b": [c(1, 2, 1, 1)]}) is None  # doji


TODAY = date(2026, 3, 11)


def test_contract_comes_from_listed_chain_nearest_otm_in_dte_window():
    pick = select_contract(BULL, 109.5, TODAY, ["2026-03-13", "2026-03-20"], chain)
    assert pick["expiration"] == "2026-03-20" and pick["dte"] == 9  # 03-13 is below min DTE
    assert pick["strike"] == 110 and pick["option_type"] == "call"
    assert pick["option_symbol"] in {o["symbol"] for o in chain("2026-03-20")}
    put = select_contract(BEAR, 109.5, TODAY, ["2026-03-20"], chain)
    assert put["strike"] == 105 and put["option_type"] == "put"


def test_no_contract_rather_than_fabrication():
    assert select_contract(BULL, 109.5, TODAY, [], chain) is None
    assert select_contract(BULL, 109.5, TODAY, ["2026-03-20"], lambda e: []) is None
    assert select_contract(BULL, 109.5, TODAY, ["2026-03-20"], lambda e: chain(e, oi=10)) is None
    assert select_contract(BULL, 109.5, TODAY, ["2026-03-20"], lambda e: chain(e, spread=5)) is None
    zero_bid = lambda e: [{**o, "bid": 0} for o in chain(e)]
    assert select_contract(BULL, 109.5, TODAY, ["2026-03-20"], zero_bid) is None
    assert select_contract(BULL, 0, TODAY, ["2026-03-20"], chain) is None
