import requests
from config import Config


class AlpacaTrader:
    """Wrapper rond de Alpaca REST API voor het plaatsen van orders en ophalen van marktdata."""

    def __init__(self):
        self.api_key = Config.ALPACA_API_KEY
        self.secret_key = Config.ALPACA_SECRET_KEY
        self.base_url = Config.ALPACA_BASE_URL
        self.data_url = Config.ALPACA_DATA_URL
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Content-Type": "application/json",
        }

    def get_account(self) -> dict | None:
        """Haal accountinformatie op (saldo, koopkracht, enz.)."""
        try:
            resp = requests.get(
                f"{self.base_url}/v2/account", headers=self.headers, timeout=10
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception:
            return None

    def get_positions(self) -> list[dict]:
        """Haal alle open posities op."""
        try:
            resp = requests.get(
                f"{self.base_url}/v2/positions", headers=self.headers, timeout=10
            )
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception:
            return []

    def get_position(self, symbol: str) -> dict | None:
        """Haal een specifieke positie op voor een symbool."""
        try:
            resp = requests.get(
                f"{self.base_url}/v2/positions/{symbol}",
                headers=self.headers,
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception:
            return None

    def get_bars(self, symbol: str, timeframe: str = "1Day", limit: int = 100) -> list[dict]:
        """Haal historische candlestick-data (OHLCV) op voor een symbool via de Alpaca v2 bars endpoint."""
        try:
            params = {
                "symbols": symbol,
                "timeframe": timeframe,
                "limit": str(limit),
                "adjustment": "raw",
                "sort": "asc",
            }
            resp = requests.get(
                f"{self.data_url}/stocks/bars",
                headers=self.headers,
                params=params,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                bars_by_symbol = data.get("bars", {})
                if isinstance(bars_by_symbol, dict):
                    return bars_by_symbol.get(symbol, [])
                return bars_by_symbol
            return []
        except Exception:
            return []

    def get_latest_price(self, symbol: str) -> float | None:
        """Haal de meest recente prijs op voor een symbool."""
        try:
            resp = requests.get(
                f"{self.data_url}/stocks/{symbol}/trades/latest",
                headers=self.headers,
                timeout=10,
            )
            if resp.status_code == 200:
                trade = resp.json().get("trade")
                if trade:
                    return float(trade["p"])
            # Fallback: gebruik laatste bar
            bars = self.get_bars(symbol, limit=1)
            if bars:
                return float(bars[-1]["c"])
            return None
        except Exception:
            return None

    def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        time_in_force: str = "gtc",
    ) -> dict | None:
        """Plaats een order bij Alpaca. Geeft het order response terug of None bij fout."""
        try:
            payload = {
                "symbol": symbol,
                "qty": str(qty),
                "side": side,
                "type": order_type,
                "time_in_force": time_in_force,
            }
            resp = requests.post(
                f"{self.base_url}/v2/orders",
                headers=self.headers,
                json=payload,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                return resp.json()
            return None
        except Exception:
            return None

    def buy(self, symbol: str, qty: float) -> dict | None:
        """Koop aandelen."""
        return self.submit_order(symbol, qty, "buy")

    def sell(self, symbol: str, qty: float) -> dict | None:
        """Verkoop aandelen."""
        return self.submit_order(symbol, qty, "sell")

    def close_position(self, symbol: str) -> dict | None:
        """Sluit een volledige positie voor een symbool."""
        try:
            resp = requests.delete(
                f"{self.base_url}/v2/positions/{symbol}",
                headers=self.headers,
                timeout=10,
            )
            if resp.status_code in (200, 202):
                return resp.json()
            return None
        except Exception:
            return None

    def cancel_all_orders(self) -> bool:
        """Annuleer alle openstaande orders."""
        try:
            resp = requests.delete(
                f"{self.base_url}/v2/orders", headers=self.headers, timeout=10
            )
            return resp.status_code in (200, 204)
        except Exception:
            return False
