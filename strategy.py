from alpaca_trader import AlpacaTrader


class MovingAverageCrossover:
    """
    Moving Average Crossover strategie.

    Koopt wanneer de snelle MA (korte termijn gemiddelde) van onder naar boven
    de trage MA (lange termijn gemiddelde) kruist.
    Verkoopt wanneer de snelle MA van boven naar onder de trage MA kruist.
    """

    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.trader = AlpacaTrader()

    def calculate_ma(self, prices: list[float], period: int) -> float | None:
        """Bereken de Simple Moving Average over de laatste `period` prijzen."""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period

    def get_signal(self, symbol: str) -> dict:
        """
        Bepaal het handelssignaal voor een symbool.

        Geeft een dict terug met:
        - signal: 'buy', 'sell' of 'hold'
        - fast_ma: waarde van de snelle MA
        - slow_ma: waarde van de trage MA
        - price: huidige prijs
        """
        bars = self.trader.get_bars(symbol, limit=self.slow_period + 5)

        if len(bars) < self.slow_period:
            return {
                "signal": "hold",
                "fast_ma": None,
                "slow_ma": None,
                "price": None,
                "reason": f"Onvoldoende data ({len(bars)} bars, {self.slow_period} nodig)",
            }

        closes = [float(bar["c"]) for bar in bars]
        current_price = closes[-1]

        fast_ma = self.calculate_ma(closes, self.fast_period)
        slow_ma = self.calculate_ma(closes, self.slow_period)

        if fast_ma is None or slow_ma is None:
            return {
                "signal": "hold",
                "fast_ma": None,
                "slow_ma": None,
                "price": current_price,
                "reason": "MA kon niet berekend worden",
            }

        # Vergelijk laatste twee datapunten voor kruising
        if len(closes) >= self.slow_period + 1:
            prev_fast = self.calculate_ma(closes[:-1], self.fast_period)
            prev_slow = self.calculate_ma(closes[:-1], self.slow_period)

            if prev_fast is not None and prev_slow is not None:
                # Bullish crossover: fast gaat van onder naar boven slow
                if prev_fast <= prev_slow and fast_ma > slow_ma:
                    return {
                        "signal": "buy",
                        "fast_ma": fast_ma,
                        "slow_ma": slow_ma,
                        "price": current_price,
                        "reason": "Bullish crossover (snelle MA kruist trage MA naar boven)",
                    }

                # Bearish crossover: fast gaat van boven naar onder slow
                if prev_fast >= prev_slow and fast_ma < slow_ma:
                    return {
                        "signal": "sell",
                        "fast_ma": fast_ma,
                        "slow_ma": slow_ma,
                        "price": current_price,
                        "reason": "Bearish crossover (snelle MA kruist trage MA naar onder)",
                    }

        return {
            "signal": "hold",
            "fast_ma": fast_ma,
            "slow_ma": slow_ma,
            "price": current_price,
            "reason": "Geen kruising gedetecteerd",
        }
