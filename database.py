import requests
from datetime import datetime, timezone
from config import Config


class Database:
    """Supabase database wrapper voor het opslaan en opvragen van trades."""

    def __init__(self):
        self.url = Config.SUPABASE_URL
        self.key = Config.SUPABASE_KEY
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def _post(self, table: str, payload: dict) -> dict | None:
        """Voer een INSERT uit via de Supabase REST API."""
        try:
            resp = requests.post(
                f"{self.url}/rest/v1/{table}",
                headers={**self.headers, "Prefer": "return=representation"},
                json=payload,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                return data[0] if isinstance(data, list) else data
            return None
        except Exception:
            return None

    def _get(self, table: str, params: dict | None = None) -> list[dict]:
        """Voer een SELECT uit via de Supabase REST API."""
        try:
            resp = requests.get(
                f"{self.url}/rest/v1/{table}",
                headers=self.headers,
                params=params or {},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
            return []
        except Exception:
            return []

    def log_trade(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        order_id: str = "",
        status: str = "filled",
        strategy: str = "ma_crossover",
        pnl: float | None = None,
    ) -> dict | None:
        """Sla een uitgevoerde trade op in de database."""
        payload = {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            "order_id": order_id or None,
            "status": status,
            "strategy": strategy,
            "pnl": pnl,
        }
        return self._post("trades", payload)

    def get_recent_trades(self, limit: int = 10) -> list[dict]:
        """Haal de meest recente trades op."""
        return self._get(
            "trades",
            {
                "select": "*",
                "order": "created_at.desc",
                "limit": str(limit),
            },
        )

    def get_performance(self) -> dict:
        """Bereken performance statistieken op basis van opgeslagen trades."""
        trades = self._get("trades", {"select": "*"})

        if not trades:
            return {
                "total_trades": 0,
                "total_pnl": 0.0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "buy_count": 0,
                "sell_count": 0,
            }

        total_pnl = 0.0
        wins = 0
        losses = 0
        buy_count = 0
        sell_count = 0

        for t in trades:
            if t.get("side") == "buy":
                buy_count += 1
            else:
                sell_count += 1

            pnl = t.get("pnl")
            if pnl is not None:
                total_pnl += float(pnl)
                if pnl > 0:
                    wins += 1
                elif pnl < 0:
                    losses += 1

        closed = wins + losses
        win_rate = (wins / closed * 100) if closed > 0 else 0.0

        return {
            "total_trades": len(trades),
            "total_pnl": total_pnl,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "buy_count": buy_count,
            "sell_count": sell_count,
        }
