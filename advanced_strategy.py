import math
from alpaca_trader import AlpacaTrader


class MultiIndicatorStrategy:
    """
    Geavanceerde multi-indicator strategie die vijf signalen combineert:

    1. RSI (Relative Strength Index) — overbought/oversold meting
    2. MACD (Moving Average Convergence Divergence) — trend momentum
    3. Bollinger Bands — volatiliteit en prijsextremen
    4. SMA Crossover — trend richting (snelle vs trage moving average)
    5. Volume bevestiging — alleen handelen bij voldoende volume

    Elke indicator levert een score bij (-2 tot +2). De totale score bepaalt
    het signaal:
      - score >= +3  → BUY
      - score <= -3  → SELL
      - anders       → HOLD
    """

    def __init__(
        self,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bb_period: int = 20,
        bb_std: float = 2.0,
        sma_fast: int = 10,
        sma_slow: int = 30,
        volume_period: int = 20,
    ):
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.sma_fast = sma_fast
        self.sma_slow = sma_slow
        self.volume_period = volume_period
        self.trader = AlpacaTrader()

    # ─── Indicator berekeningen ──────────────────────────────────────

    def _sma(self, values: list[float], period: int) -> float | None:
        """Simple Moving Average over de laatste `period` waarden."""
        if len(values) < period:
            return None
        return sum(values[-period:]) / period

    def _ema(self, values: list[float], period: int) -> list[float]:
        """Exponential Moving Average reeks. Geeft een lijst terug even lang als de input."""
        if len(values) == 0:
            return []
        multiplier = 2 / (period + 1)
        ema_values = [values[0]]
        for i in range(1, len(values)):
            ema_prev = ema_values[-1]
            ema_values.append(values[i] * multiplier + ema_prev * (1 - multiplier))
        return ema_values

    def _rsi(self, closes: list[float], period: int) -> float | None:
        """Relative Strength Index over de laatste `period` dagen."""
        if len(closes) < period + 1:
            return None

        gains = []
        losses = []
        for i in range(len(closes) - period, len(closes)):
            change = closes[i] - closes[i - 1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _macd(self, closes: list[float]) -> dict | None:
        """
        MACD berekening.
        Geeft dict met macd_line, signal_line, histogram en prev_histogram.
        """
        if len(closes) < self.macd_slow + self.macd_signal:
            return None

        ema_fast = self._ema(closes, self.macd_fast)
        ema_slow = self._ema(closes, self.macd_slow)

        # MACD line = EMA(fast) - EMA(slow)
        macd_line = []
        for i in range(len(closes)):
            macd_line.append(ema_fast[i] - ema_slow[i])

        # Signal line = EMA van MACD line
        signal_line = self._ema(macd_line, self.macd_signal)

        # Histogram = MACD - Signal
        current_hist = macd_line[-1] - signal_line[-1]
        prev_hist = macd_line[-2] - signal_line[-2] if len(macd_line) >= 2 else 0

        return {
            "macd_line": macd_line[-1],
            "signal_line": signal_line[-1],
            "histogram": current_hist,
            "prev_histogram": prev_hist,
        }

    def _bollinger_bands(self, closes: list[float]) -> dict | None:
        """
        Bollinger Bands berekening.
        Geeft dict met middle, upper, lower band en percent_b (positie t.o.v. bands).
        """
        if len(closes) < self.bb_period:
            return None

        slice_ = closes[-self.bb_period:]
        middle = sum(slice_) / self.bb_period

        variance = sum((x - middle) ** 2 for x in slice_) / self.bb_period
        std = math.sqrt(variance)

        upper = middle + self.bb_std * std
        lower = middle - self.bb_std * std

        price = closes[-1]
        band_width = upper - lower
        percent_b = ((price - lower) / band_width * 100) if band_width > 0 else 50.0

        return {
            "middle": middle,
            "upper": upper,
            "lower": lower,
            "percent_b": percent_b,
        }

    def _volume_confirmation(self, volumes: list[float]) -> dict:
        """
        Volume bevestiging: vergelijk huidig volume met gemiddelde.
        Geeft dict met ratio en of er voldoende volume is.
        """
        if len(volumes) < self.volume_period + 1:
            return {"ratio": 1.0, "confirmed": True, "reason": "Onvoldoende data — geen filter"}

        avg_volume = sum(volumes[-self.volume_period - 1 : -1]) / self.volume_period
        current_volume = volumes[-1]

        if avg_volume == 0:
            return {"ratio": 1.0, "confirmed": True, "reason": "Gemiddeld volume is 0"}

        ratio = current_volume / avg_volume
        return {
            "ratio": ratio,
            "confirmed": ratio >= 0.8,
            "reason": f"Volume {ratio:.1f}x gemiddelde ({'OK' if ratio >= 0.8 else 'laag'})",
        }

    # ─── Signaal evaluatie ───────────────────────────────────────────

    def get_signal(self, symbol: str) -> dict:
        """
        Bepaal het handelssignaal voor een symbool door alle indicatoren te combineren.

        Geeft een dict terug met:
        - signal: 'buy', 'sell' of 'hold'
        - score: totale score (-10 tot +10)
        - price: huidige prijs
        - indicators: dict met alle indicator waarden en hun individuele scores
        - reason: leesbare uitleg van het signaal
        """
        # We hebben voldoende data nodig voor alle indicatoren
        min_bars = max(self.sma_slow + 5, self.macd_slow + self.macd_signal + 5, self.bb_period + 5, self.rsi_period + 5)
        bars = self.trader.get_bars(symbol, limit=min_bars)

        if len(bars) < min_bars:
            return {
                "signal": "hold",
                "score": 0,
                "price": None,
                "indicators": {},
                "reason": f"Onvoldoende data ({len(bars)} bars, {min_bars} nodig)",
            }

        closes = bars['close'].astype(float).tolist()
        volumes = bars['volume'].astype(float).tolist()
        current_price = closes[-1]

        # Bereken alle indicatoren
        rsi = self._rsi(closes, self.rsi_period)
        macd = self._macd(closes)
        bb = self._bollinger_bands(closes)
        sma_fast = self._sma(closes, self.sma_fast)
        sma_slow = self._sma(closes, self.sma_slow)
        vol = self._volume_confirmation(volumes)

        # Bereken vorige SMA waarden voor crossover detectie
        sma_fast_prev = self._sma(closes[:-1], self.sma_fast)
        sma_slow_prev = self._sma(closes[:-1], self.sma_slow)

        scores: list[tuple[str, int, str]] = []
        total_score = 0

        # ── 1. RSI scoring ───────────────────────────────────────────
        rsi_score = 0
        rsi_detail = ""
        if rsi is not None:
            if rsi < self.rsi_oversold:
                rsi_score = 2
                rsi_detail = f"Oversold ({rsi:.1f}) — sterke koopkans"
            elif rsi < 40:
                rsi_score = 1
                rsi_detail = f"Lage RSI ({rsi:.1f}) — licht bullish"
            elif rsi > self.rsi_overbought:
                rsi_score = -2
                rsi_detail = f"Overbought ({rsi:.1f}) — sterke verkoopkans"
            elif rsi > 60:
                rsi_score = -1
                rsi_detail = f"Hoge RSI ({rsi:.1f}) — licht bearish"
            else:
                rsi_detail = f"Neutraal ({rsi:.1f})"
        scores.append(("RSI", rsi_score, rsi_detail))

        # ── 2. MACD scoring ──────────────────────────────────────────
        macd_score = 0
        macd_detail = ""
        if macd is not None:
            hist = macd["histogram"]
            prev_hist = macd["prev_histogram"]
            if hist > 0 and prev_hist <= 0:
                macd_score = 2
                macd_detail = "Bullish crossover — MACD kruist signaallijn naar boven"
            elif hist > 0 and hist > prev_hist:
                macd_score = 1
                macd_detail = f"Positieve histogram, momentum neemt toe ({hist:.4f})"
            elif hist < 0 and prev_hist >= 0:
                macd_score = -2
                macd_detail = "Bearish crossover — MACD kruist signaallijn naar onder"
            elif hist < 0 and hist < prev_hist:
                macd_score = -1
                macd_detail = f"Negatieve histogram, momentum neemt af ({hist:.4f})"
            else:
                macd_detail = f"Neutraal (hist: {hist:.4f})"
        scores.append(("MACD", macd_score, macd_detail))

        # ── 3. Bollinger Bands scoring ───────────────────────────────
        bb_score = 0
        bb_detail = ""
        if bb is not None:
            pb = bb["percent_b"]
            if pb < 0:
                bb_score = 2
                bb_detail = f"Prijs onder onderste band (%B: {pb:.1f}%) — oversold"
            elif pb < 20:
                bb_score = 1
                bb_detail = f"Prijs nabij onderste band (%B: {pb:.1f}%)"
            elif pb > 100:
                bb_score = -2
                bb_detail = f"Prijs boven bovenste band (%B: {pb:.1f}%) — overbought"
            elif pb > 80:
                bb_score = -1
                bb_detail = f"Prijs nabij bovenste band (%B: {pb:.1f}%)"
            else:
                bb_detail = f"Neutraal (%B: {pb:.1f}%)"
        scores.append(("Bollinger", bb_score, bb_detail))

        # ── 4. SMA Crossover scoring ─────────────────────────────────
        sma_score = 0
        sma_detail = ""
        if sma_fast is not None and sma_slow is not None:
            if sma_fast_prev is not None and sma_slow_prev is not None:
                if sma_fast_prev <= sma_slow_prev and sma_fast > sma_slow:
                    sma_score = 2
                    sma_detail = "Bullish crossover — snelle MA kruist trage MA naar boven"
                elif sma_fast_prev >= sma_slow_prev and sma_fast < sma_slow:
                    sma_score = -2
                    sma_detail = "Bearish crossover — snelle MA kruist trage MA naar onder"
                elif sma_fast > sma_slow:
                    sma_score = 1
                    sma_detail = f"Snelle MA boven trage MA ({sma_fast:.2f} > {sma_slow:.2f})"
                elif sma_fast < sma_slow:
                    sma_score = -1
                    sma_detail = f"Snelle MA onder trage MA ({sma_fast:.2f} < {sma_slow:.2f})"
            else:
                sma_detail = "Onvoldoende data voor crossover detectie"
        scores.append(("SMA", sma_score, sma_detail))

        # ── 5. Volume bevestiging ────────────────────────────────────
        # Volume versterkt of verzwakt het signaal, maar levert zelf geen richting
        vol_score = 0
        vol_detail = vol["reason"]
        if not vol["confirmed"]:
            # Bij laag volume worden andere signalen afgezwakt
            vol_score = 0
            vol_detail += " — signalen afgezwakt"
        scores.append(("Volume", vol_score, vol_detail))

        # Totale score
        total_score = sum(s for _, s, _ in scores)

        # Bepaal signaal
        # Pas volume filter toe: als volume niet bevestigd, verhoag drempel
        threshold = 3 if vol["confirmed"] else 4

        if total_score >= threshold:
            signal = "buy"
        elif total_score <= -threshold:
            signal = "sell"
        else:
            signal = "hold"

        # Bouw reden tekst
        reason_parts = [f"Score: {total_score:+d} (drempel: ±{threshold})"]
        for name, score, detail in scores:
            icon = "🟢" if score > 0 else "🔴" if score < 0 else "⚪"
            reason_parts.append(f"{icon} {name} ({score:+d}): {detail}")

        reason = "\n".join(reason_parts)

        return {
            "signal": signal,
            "score": total_score,
            "price": current_price,
            "indicators": {
                "rsi": rsi,
                "macd": macd,
                "bollinger": bb,
                "sma_fast": sma_fast,
                "sma_slow": sma_slow,
                "volume_ratio": vol["ratio"],
                "volume_confirmed": vol["confirmed"],
            },
            "reason": reason,
        }
