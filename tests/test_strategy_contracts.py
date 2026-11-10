from datetime import date

from contracts import select_contract
from strategy import BEAR, BULL, failed_2u, fvg_retest, ftfc_direction, ict_fvg_retest, orb_direction, two_one_two
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


def test_ict_fvg_retest_respects_and_invalidates():
    bull = [c(9, 10, 8, 9.5), c(9.5, 10.5, 9.5, 10.4), c(10.8, 11.5, 10.8, 11.4), c(11.4, 11.5, 10.6, 11.0)]
    assert ict_fvg_retest(bull) == BULL
    assert ict_fvg_retest(bull[:3] + [c(11.4, 11.5, 10.6, 10.7)]) is None  # closed inside the gap, not respected
    assert ict_fvg_retest(bull[:3] + [c(11.4, 11.5, 9.0, 9.5), c(9.5, 11.2, 9.4, 11.0)]) is None  # filled in between
    bear = [c(11, 12, 10.5, 10.6), c(10.6, 10.7, 9.6, 9.7), c(9.4, 9.4, 8.8, 8.9), c(8.9, 9.6, 8.8, 9.2)]
    assert ict_fvg_retest(bear) == BEAR
    assert ict_fvg_retest([c(1, 2, 1, 2)] * 3) is None


def test_orb_direction():
    orb = c(100, 101, 99, 100.5)
    assert orb_direction(orb, c(100.5, 102, 100, 101.5)) == BULL
    assert orb_direction(orb, c(100, 100.2, 98, 98.5)) == BEAR
    assert orb_direction(orb, c(100, 101.5, 98.5, 100.2)) is None  # wicks outside, closes inside
    assert orb_direction(orb, orb) is None and orb_direction(None, orb) is None


TODAY = date(2026, 3, 11)


def test_contract_comes_from_listed_chain_within_policy():
    pick = select_contract(BULL, 109.5, TODAY, ["2026-03-11", "2026-03-13", "2026-03-20"], chain)
    assert pick["expiration"] == "2026-03-13" and pick["dte"] == 2  # 0DTE and 9DTE excluded by 1-7 policy
    assert pick["strike"] == 110 and pick["option_type"] == "call" and pick["contracts"] == 1
    assert pick["max_premium_usd"] == round(pick["ask"] * 100, 2) <= 200
    assert pick["option_symbol"] in {o["symbol"] for o in chain("2026-03-13")}
    put = select_contract(BEAR, 109.5, TODAY, ["2026-03-13"], chain)
    assert put["strike"] == 105 and put["option_type"] == "put"


def test_premium_cap_scans_further_otm_then_gives_up():
    def priced(e):
        out = []
        for o in chain(e):
            ask = {110: 2.5, 115: 1.9, 120: 0.8}.get(o["strike"], 5.0)
            out.append({**o, "bid": round(ask - 0.1, 2), "ask": ask})
        return out
    pick = select_contract(BULL, 109.5, TODAY, ["2026-03-13"], priced)
    assert pick["strike"] == 115 and pick["max_premium_usd"] == 190.0
    assert select_contract(BULL, 109.5, TODAY, ["2026-03-13"], priced, max_premium_usd=100)["strike"] == 120
    too_dear = lambda e: [{**o, "bid": 2.9, "ask": 3.0} for o in chain(e)]
    assert select_contract(BULL, 109.5, TODAY, ["2026-03-13"], too_dear) is None


def test_configuration_cannot_loosen_policy():
    loose = select_contract(BULL, 109.5, TODAY, ["2026-03-20"], chain, max_dte=30, max_premium_usd=1000)
    assert loose is None  # 9 DTE still outside the 1-7 policy
    pricey = lambda e: [{**o, "bid": 2.9, "ask": 3.0} for o in chain(e)]
    assert select_contract(BULL, 109.5, TODAY, ["2026-03-13"], pricey, max_premium_usd=1000) is None
    assert select_contract(BULL, 109.5, TODAY, ["2026-03-13"], chain, contracts=2) is None


def test_no_contract_rather_than_fabrication():
    assert select_contract(BULL, 109.5, TODAY, [], chain) is None
    assert select_contract(BULL, 109.5, TODAY, ["2026-03-13"], lambda e: []) is None
    assert select_contract(BULL, 109.5, TODAY, ["2026-03-13"], lambda e: chain(e, oi=10)) is None
    assert select_contract(BULL, 109.5, TODAY, ["2026-03-13"], lambda e: chain(e, spread=5)) is None
    zero_bid = lambda e: [{**o, "bid": 0} for o in chain(e)]
    assert select_contract(BULL, 109.5, TODAY, ["2026-03-13"], zero_bid) is None
    assert select_contract(BULL, 0, TODAY, ["2026-03-13"], chain) is None
