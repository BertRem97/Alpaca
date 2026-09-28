from config import Config
from alpaca_trader import AlpacaTrader
from database import Database
from strategy import MovingAverageCrossover
from advanced_strategy import MultiIndicatorStrategy
import requests


class TelegramHandler:
    """Afhandeling van Telegram commando's voor de trading bot."""

    def __init__(self, auto_trade_state: dict, strategy=None):
        self.token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.trader = AlpacaTrader()
        self.db = Database()
        self.strategy = strategy or MovingAverageCrossover(Config.FAST_MA, Config.SLOW_MA)
        # Gedeelde mutable state (referentie naar bot.py zijn dict)
        self.auto_trade_state = auto_trade_state

    def send_message(self, text: str, chat_id: str = None) -> bool:
        """Stuur een bericht naar Telegram. Ondersteunt Markdown opmaak."""
        try:
            payload = {
                "chat_id": chat_id or self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }
            resp = requests.post(
                f"{self.api_url}/sendMessage", json=payload, timeout=10
            )
            return resp.status_code == 200
        except Exception:
            return False

    def get_updates(self, offset: int = 0) -> list[dict]:
        """Haal nieuwe berichten/commando's op van Telegram."""
        try:
            params = {"timeout": 30, "offset": offset}
            resp = requests.get(
                f"{self.api_url}/getUpdates", params=params, timeout=35
            )
            if resp.status_code == 200:
                return resp.json().get("result", [])
            return []
        except Exception:
            return []

    def handle_command(self, text: str, chat_id: str) -> str:
        """Verwerk een binnenkomend commando en geef een antwoord terug."""
        text = text.strip()
        parts = text.split()
        cmd = parts[0].lower().lstrip("/")
        args = parts[1:]

        handlers = {
            "start": self._cmd_start,
            "help": self._cmd_help,
            "status": self._cmd_status,
            "balance": self._cmd_balance,
            "positions": self._cmd_positions,
            "performance": self._cmd_performance,
            "trades": self._cmd_trades,
            "config": self._cmd_config,
            "signal": self._cmd_signal,
            "start_bot": self._cmd_start_bot,
            "stop_bot": self._cmd_stop_bot,
            "buy": self._cmd_buy,
            "sell": self._cmd_sell,
            "close": self._cmd_close,
            "cancel": self._cmd_cancel,
        }

        handler = handlers.get(cmd)
        if handler:
            try:
                return handler(args)
            except Exception as e:
                return f"❌ Fout bij verwerken van commando: {e}"
        return (
            f"❓ Onbekend commando: /{cmd}\n"
            f"Typ /help voor een overzicht van alle commando's."
        )

    # ─── Commando handlers ───────────────────────────────────────────

    def _cmd_start(self, args) -> str:
        return (
            "🤖 *Trading Bot*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "Welkom! Ik ben je trading bot.\n"
            "Typ /help om alle commando's te zien.\n"
            "Typ /status voor de huidige bot status."
        )

    def _cmd_help(self, args) -> str:
        return (
            "📋 *Commando's*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "*Algemeen*\n"
            "/start - Welkomstbericht\n"
            "/help - Dit overzicht\n"
            "/status - Bot status (aan/uit)\n"
            "/config - Toon configuratie\n\n"
            "*Account & Posities*\n"
            "/balance - Account saldo & koopkracht\n"
            "/positions - Open posities\n\n"
            "*Prestaties*\n"
            "/performance - Winst/verlies statistieken\n"
            "/trades - Recente trades (laatste 10)\n\n"
            "*Trading*\n"
            "/signal <symbool> - Toon strategie signaal\n"
            "/buy <symbool> <aantal> - Koop aandelen\n"
            "/sell <symbool> <aantal> - Verkoop aandelen\n"
            "/close <symbool> - Sluit volledige positie\n"
            "/cancel - Annuleer alle open orders\n\n"
            "*Auto-trade*\n"
            "/start\\_bot - Start automatisch handelen\n"
            "/stop\\_bot - Stop automatisch handelen"
        )

    def _cmd_status(self, args) -> str:
        active = self.auto_trade_state.get("enabled", False)
        mode = "PAPER (simulatie)" if Config.PAPER_TRADING else "LIVE (echt geld!)"
        icon = "🟢" if active else "🔴"
        if Config.STRATEGY == "advanced":
            strat = f"Strategie: Advanced (RSI/MACD/BB/Volume)"
        else:
            strat = f"Strategie: Simple MA ({Config.FAST_MA}/{Config.SLOW_MA})"
        return (
            f"{icon} *Bot Status*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Auto-trade: {'AAN' if active else 'UIT'}\n"
            f"Mode: {mode}\n"
            f"Symbolen: {', '.join(Config.SYMBOLS)}\n"
            f"{strat}\n"
            f"Poll interval: {Config.POLL_INTERVAL}s"
        )

    def _cmd_config(self, args) -> str:
        return Config.summary()

    def _cmd_balance(self, args) -> str:
        account = self.trader.get_account()
        if not account:
            return "❌ Kon accountinformatie niet ophalen van Alpaca."

        equity = float(account.get("equity", 0))
        cash = float(account.get("cash", 0))
        buying_power = float(account.get("buying_power", 0))
        portfolio_value = float(account.get("portfolio_value", 0))

        return (
            "💰 *Account*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"Portfolio waarde: ${portfolio_value:,.2f}\n"
            f"Eigen vermogen: ${equity:,.2f}\n"
            f"Contant: ${cash:,.2f}\n"
            f"Koopkracht: ${buying_power:,.2f}\n"
            f"Status: {account.get('status', 'onbekend')}"
        )

    def _cmd_positions(self, args) -> str:
        positions = self.trader.get_positions()
        if not positions:
            return "📭 Je hebt momenteel geen open posities."

        lines = ["📊 *Open Posities*\n━━━━━━━━━━━━━━━━━━━"]
        for p in positions:
            symbol = p.get("symbol", "?")
            qty = float(p.get("qty", 0))
            market_value = float(p.get("market_value", 0))
            unrealized_pl = float(p.get("unrealized_pl", 0))
            pl_pct = float(p.get("unrealized_plpc", 0)) * 100
            icon = "📈" if unrealized_pl >= 0 else "📉"

            lines.append(
                f"{icon} *{symbol}* — {qty} stuks\n"
                f"   Waarde: ${market_value:,.2f}\n"
                f"   W/V: ${unrealized_pl:,.2f} ({pl_pct:+.2f}%)"
            )
        return "\n".join(lines)

    def _cmd_performance(self, args) -> str:
        perf = self.db.get_performance()
        pnl_icon = "📈" if perf["total_pnl"] >= 0 else "📉"
        return (
            "📊 *Prestaties*\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            f"Totale trades: {perf['total_trades']}\n"
            f"Aankopen: {perf['buy_count']}\n"
            f"Verkopen: {perf['sell_count']}\n\n"
            f"{pnl_icon} Gerealiseerde W/V: ${perf['total_pnl']:.2f}\n"
            f"Winst trades: {perf['wins']}\n"
            f"Verlies trades: {perf['losses']}\n"
            f"Winstpercentage: {perf['win_rate']:.1f}%"
        )

    def _cmd_trades(self, args) -> str:
        trades = self.db.get_recent_trades(10)
        if not trades:
            return "📭 Nog geen trades uitgevoerd."

        lines = ["📜 *Recente Trades*\n━━━━━━━━━━━━━━━━━━━"]
        for t in trades:
            symbol = t.get("symbol", "?")
            side = t.get("side", "?")
            qty = float(t.get("qty", 0))
            price = float(t.get("price", 0))
            created = t.get("created_at", "")[:19]
            icon = "🟢" if side == "buy" else "🔴"
            pnl_str = ""
            if t.get("pnl") is not None:
                pnl_val = float(t["pnl"])
                pnl_str = f" | W/V: ${pnl_val:.2f}"

            lines.append(
                f"{icon} {created}\n"
                f"   {side.upper()} {qty}x {symbol} @ ${price:.2f}{pnl_str}"
            )
        return "\n".join(lines)

    def _cmd_signal(self, args) -> str:
        if not args:
            symbols = Config.SYMBOLS
        else:
            symbols = [args[0].upper()]

        lines = ["🎯 *Strategie Signalen*\n━━━━━━━━━━━━━━━━━━━"]
        for symbol in symbols:
            sig = self.strategy.get_signal(symbol)
            signal = sig["signal"]
            icon = {"buy": "🟢", "sell": "🔴", "hold": "⚪"}.get(signal, "❓")
            price = sig.get("price")
            price_str = f"${price:.2f}" if price else "N/A"

            lines.append(f"{icon} *{symbol}*: {signal.upper()} | Prijs: {price_str}")

            # Toon indicator details afhankelijk van strategie
            indicators = sig.get("indicators", {})
            if Config.STRATEGY == "advanced" and indicators:
                ind = indicators
                rsi = ind.get("rsi")
                macd = ind.get("macd")
                bb = ind.get("bollinger")
                sma_f = ind.get("sma_fast")
                sma_s = ind.get("sma_slow")
                vol_r = ind.get("volume_ratio")

                if rsi is not None:
                    lines.append(f"   RSI: {rsi:.1f}")
                if macd is not None:
                    lines.append(f"   MACD hist: {macd['histogram']:.4f}")
                if bb is not None:
                    lines.append(f"   Bollinger %B: {bb['percent_b']:.1f}%")
                if sma_f is not None and sma_s is not None:
                    lines.append(f"   SMA{Config.FAST_MA}: ${sma_f:.2f} | SMA{Config.SLOW_MA}: ${sma_s:.2f}")
                if vol_r is not None:
                    vol_ok = ind.get("volume_confirmed", False)
                    lines.append(f"   Volume: {vol_r:.1f}x {'OK' if vol_ok else 'laag'}")
                score = sig.get("score", 0)
                lines.append(f"   Score: {score:+d}")
            else:
                fast = sig.get("fast_ma")
                slow = sig.get("slow_ma")
                fast_str = f"${fast:.2f}" if fast else "N/A"
                slow_str = f"${slow:.2f}" if slow else "N/A"
                lines.append(f"   MA{Config.FAST_MA}: {fast_str} | MA{Config.SLOW_MA}: {slow_str}")

            lines.append(f"   {sig.get('reason', '')}")
        return "\n".join(lines)

    def _cmd_start_bot(self, args) -> str:
        self.auto_trade_state["enabled"] = True
        strat = "Advanced Multi-Indicator (RSI/MACD/BB/Volume)" if Config.STRATEGY == "advanced" else f"Simple MA Crossover ({Config.FAST_MA}/{Config.SLOW_MA})"
        return (
            "🟢 *Auto-trade gestart!*\n"
            f"De bot handelt nu automatisch in: {', '.join(Config.SYMBOLS)}\n"
            f"Strategie: {strat}\n"
            f"Poll interval: {Config.POLL_INTERVAL}s"
        )

    def _cmd_stop_bot(self, args) -> str:
        self.auto_trade_state["enabled"] = False
        return "🔴 *Auto-trade gestopt.*\nDe bot handelt niet meer automatisch."

    def _cmd_buy(self, args) -> str:
        if len(args) < 1:
            return "❌ Gebruik: /buy <symbool> [aantal]"
        symbol = args[0].upper()
        qty = float(args[1]) if len(args) > 1 else Config.QUANTITY

        price = self.trader.get_latest_price(symbol)
        order = self.trader.buy(symbol, qty)

        if order:
            order_id = order.get("id", "")
            fill_price = float(order.get("filled_avg_price") or 0) or price or 0
            self.db.log_trade(symbol, "buy", qty, fill_price, order_id, strategy="manual")
            return (
                f"✅ *Aankoop geplaatst*\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"{symbol}: {qty} stuks @ ~${fill_price:.2f}\n"
                f"Order ID: {order_id}"
            )
        return f"❌ Kon geen kooporder plaatsen voor {symbol}. Controleer saldo en markturenp."

    def _cmd_sell(self, args) -> str:
        if len(args) < 1:
            return "❌ Gebruik: /sell <symbool> [aantal]"
        symbol = args[0].upper()
        qty = float(args[1]) if len(args) > 1 else Config.QUANTITY

        price = self.trader.get_latest_price(symbol)
        order = self.trader.sell(symbol, qty)

        if order:
            order_id = order.get("id", "")
            fill_price = float(order.get("filled_avg_price") or 0) or price or 0
            pnl = self._calculate_pnl(symbol, qty, fill_price)
            self.db.log_trade(
                symbol, "sell", qty, fill_price, order_id, strategy="manual", pnl=pnl
            )
            pnl_str = f"\nW/V: ${pnl:.2f}" if pnl is not None else ""
            return (
                f"✅ *Verkoop geplaatst*\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"{symbol}: {qty} stuks @ ~${fill_price:.2f}\n"
                f"Order ID: {order_id}{pnl_str}"
            )
        return f"❌ Kon geen verkooporder plaatsen voor {symbol}."

    def _cmd_close(self, args) -> str:
        if len(args) < 1:
            return "❌ Gebruik: /close <symbool>"
        symbol = args[0].upper()

        result = self.trader.close_position(symbol)
        if result:
            return f"✅ Posie voor {symbol} gesloten."
        return f"❌ Kon positie voor {symbol} niet sluiten. Bestaat deze?"

    def _cmd_cancel(self, args) -> str:
        if self.trader.cancel_all_orders():
            return "✅ Alle openstaande orders geannuleerd."
        return "❌ Kon orders niet annuleren."

    def _calculate_pnl(self, symbol: str, qty: float, sell_price: float) -> float | None:
        """Bereken gerealiseerde winst/verlies op basis van de gemiddelde aankoops prijs."""
        pos = self.trader.get_position(symbol)
        if pos:
            avg_cost = float(pos.get("avg_entry_price", 0))
            return (sell_price - avg_cost) * qty
        return None
