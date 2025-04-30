import pytest
from iv_data import iv_rank_polygon


def test_iv_rank_mock(monkeypatch):
    # monkeypatch requests.get to avoid API call
    class MockResp:
        def json(self):
            return {"results": [{"vwap": i} for i in range(1,11)]}
    monkeypatch.setattr('requests.get', lambda *args,**kwargs: MockResp())
    rank = iv_rank_polygon("MSTR", 10)
    assert 0 <= rank <= 100