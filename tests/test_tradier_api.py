import pytest

from tradier_api import TradierClient, TradierError, as_list


class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body or {}, headers or {}

    def json(self):
        return self._body


class GetOnlySession:
    """Has no post/put/delete: any non-GET call would raise AttributeError."""

    def __init__(self, responses):
        self.responses, self.headers, self.seen = list(responses), {}, []

    def get(self, url, params=None, timeout=None):
        self.seen.append((url, params))
        return self.responses.pop(0)


def client(responses):
    return TradierClient("tok", session=GetOnlySession(responses), sleep=lambda s: None)


def test_refuses_order_and_account_paths():
    c = client([])
    for path in ["/v1/accounts/1/orders", "/v1/markets/../accounts/1/orders", "/v1/user/profile"]:
        with pytest.raises(TradierError):
            c._get(path)
    assert c.session.seen == []


def test_single_object_and_null_normalized():
    assert as_list(None) == [] and as_list({"a": 1}) == [{"a": 1}] and as_list([1]) == [1]
    c = client([Resp(200, {"history": {"day": {"date": "2026-03-10", "open": 1}}}), Resp(200, {"history": None})])
    assert c.history("SPY", "daily", "2026-03-01", "2026-03-10") == [{"date": "2026-03-10", "open": 1}]
    assert c.history("SPY", "daily", "2026-03-01", "2026-03-10") == []


def test_rate_limit_retry_then_success_and_header_tracking():
    c = client([Resp(429), Resp(200, {"clock": {"state": "open"}}, {"X-Ratelimit-Available": "57"})])
    assert c.clock() == {"state": "open"}
    assert c.rate_limit_available == 57 and len(c.session.seen) == 2


def test_entitlement_errors_are_explicit():
    with pytest.raises(TradierError, match="entitlement"):
        client([Resp(401)]).clock()


def test_unsupported_intervals_rejected_before_any_request():
    c = client([])
    with pytest.raises(ValueError):
        c.timesales("SPY", "240", "a", "b")
    with pytest.raises(ValueError):
        c.history("SPY", "D", "a", "b")
    assert c.session.seen == []


def test_timesales_uses_documented_endpoint_and_regular_session_filter():
    c = client([Resp(200, {"series": {"data": [{"time": "2026-03-10T09:30:00"}]}})])
    c.timesales("SPY", "15min", "2026-03-10 09:30", "2026-03-10 16:00")
    url, params = c.session.seen[0]
    assert url.endswith("/v1/markets/timesales") and params["session_filter"] == "open"
