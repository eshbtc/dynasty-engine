# ------------------------------------------------------------------------------
# 7️⃣  TESTS – tests/test_order_helper.py
# ------------------------------------------------------------------------------
import pytest
from order_helper import OrderHelper # Assuming order_helper.py is in the root or PYTHONPATH
from ib_insync import IB, Stock

@pytest.fixture
def mock_ib(monkeypatch):
    """Mocks IB connection and key methods."""
    ib = IB() # Create an IB instance, but don't connect

    # monkey‑patch reqMktData to return dummy market data object
    class DummyMarketData:
        def __init__(self):
            self.bid = 100.0
            self.ask = 102.0
            self.last = 101.0
            # Add other fields if OrderHelper uses them (e.g., close)
            self.close = 100.5 # Example

    # reqMktData usually requires awaiting, mock appropriately if OrderHelper uses await
    # If OrderHelper doesn't use await ib.reqMktData directly, this is simpler
    monkeypatch.setattr(ib, 'reqMktData', lambda contract, genericTickList="", snapshot=False, regulatorySnapshot=False, mktDataOptions=None: DummyMarketData())

    # monkey-patch placeOrder to return a dummy filled trade object
    class DummyOrderStatus:
        def __init__(self, filled_qty):
            self.filled = filled_qty
            self.status = 'Filled'
            # Add other status fields if needed

    class DummyTrade:
        def __init__(self, order, qty):
            self.orderStatus = DummyOrderStatus(qty)
            # Add other trade attributes if needed (e.g., fills, log)
            self.log = []
            self.fills = []

    # Mock placeOrder - assumes it takes contract and order
    monkeypatch.setattr(ib, 'placeOrder', lambda contract, order: DummyTrade(order, order.totalQuantity))

    # Mock reqContractDetails if needed by OrderHelper
    # monkeypatch.setattr(ib, 'reqContractDetails', ...) 

    return ib

def test_limit_vwap(mock_ib):
    """Tests the limit_or_vwap function with mocked IB."""
    # Ensure OrderHelper can be imported (check PYTHONPATH if needed)
    oh = OrderHelper(mock_ib)
    stock_contract = Stock('MSTR','SMART','USD')
    order_size = 10

    # Assuming limit_or_vwap is synchronous. If async, mark test with @pytest.mark.asyncio
    # and use 'await oh.limit_or_vwap(...)'
    # Also ensure mock_ib methods handle async if necessary.
    px, fee = oh.limit_or_vwap(stock_contract, order_size)

    # Assertions based on mocked data (bid=100, ask=102, last=101)
    # The original assertion 100 <= px <= 106 seems broad. Adjust based on expected logic.
    # If it places a limit order, px should be near bid/ask/mid. If VWAP, depends on logic.
    # Let's assume it aims for mid-price + small slippage for limit, or uses 'last' for VWAP-like
    assert isinstance(px, (int, float))
    assert isinstance(fee, (int, float))
    assert px > 0 # Price should be positive
    assert fee >= 0 # Fee should be non-negative (might be 0 in some cases)

    # Example: Tighten assertion if it's expected to be near mid (101)
    # assert 100.5 <= px <= 101.5

    # The original check 100 <= px <= 106 might be valid depending on the VWAP/limit logic
    assert 100 <= px <= 106 # Keeping original broad check for now
    print(f"Test executed limit_or_vwap: Price={px}, Fee={fee}")

# Add more tests for other OrderHelper methods
