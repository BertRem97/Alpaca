import time
import signal
import sys
import logging
from config import Config
from alpaca_trader import AlpacaTrader
from database import Database
from strategy import MovingAverageCrossover
from advanced_strategy import MultiIndicatorStrategy
from telegram_handler import TelegramHandler
from pprint import pprint

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("trading-bot")


class TradingBot:
    """Hoofd-orchestrator: combineert Alpaca trading, strategie, database en Telegram."""

    def __init__(self):
        # Valideer configuratie
        errors = Config.validate()
        if errors:
            for e in errors:
                logger.error(f"Configuratiefout: {e}")
            logger.error("Fix de .env en start opnieuw.")
            sys.exit(1)

        # Gedeelde state voor auto-trade aan/uit (bewerkt via Telegram)
        self.auto_trade_state = {"enabled": Config.AUTO_TRADE_ENABLED}

        # Componenten
        self.trader = AlpacaTrader()
        self.db = Database()
        if Config.STRATEGY == "simple":
            self.strategy = MovingAverageCrossover(Config.FAST_MA, Config.SLOW_MA)
            strategy_name = "Simple MA Crossover"
        else:
            self.strategy = MultiIndicatorStrategy(
                rsi_period=Config.RSI_PERIOD,
                rsi_oversold=Config.RSI_OVERSOLD,
                rsi_overbought=Config.RSI_OVERBOUGHT,
                macd_fast=Config.MACD_FAST,
                macd_slow=Config.MACD_SLOW,
                macd_signal=Config.MACD_SIGNAL,
                bb_period=Config.BB_PERIOD,
                bb_std=Config.BB_STD,
                sma_fast=Config.FAST_MA,
                sma_slow=Config.SLOW_MA,
                volume_period=Config.VOLUME_PERIOD,
            )
            strategy_name = "Advanced Multi-Indicator"
        self.telegram = TelegramHandler(self.auto_trade_state, self.strategy)

        # Telegram polling state
        self.update_offset = 0
        self.running = True

        logger.info(
            f"Bot gestart | Mode: {'PAPER' if Config.PAPER_TRADING else 'LIVE'} | "
            f"Strategie: {strategy_name} | "
            f"Symbolen: {', '.join(Config.SYMBOLS)} | "
            f"Auto-trade: {'AAN' if self.auto_trade_state['enabled'] else 'UIT'}"
        )

    def run(self):
        """Hoofdloop: verwerk Telegram commando's en voer periodiek strategie uit."""
        self.telegram.send_message(
            "🤖 Trading Bot is gestart!\n"
            f"Mode: {'PAPER (simulatie)' if Config.PAPER_TRADING else 'LIVE (echt geld!)'}\n"
            f"Auto-trade: {'AAN' if self.auto_trade_state['enabled'] else 'UIT'}\n"
            "Typ /help voor commando's."
        )

        # Registreer SIGINT/SIGTERM voor nette afsluiting
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        last_poll_time = 0
        last_trade_time = 0

        while self.running:
            now = time.time()

            # 1. Verwerk Telegram commando's (elke 1 seconde)
            if now - last_poll_time >= 1:
                self._poll_telegram()
                last_poll_time = now

            # 2. Voer strategie uit (elke POLL_INTERVAL seconden, als auto-trade aan staat)
            if (
                self.auto_trade_state["enabled"]
                and now - last_trade_time >= Config.POLL_INTERVAL
            ):
                self._run_strategy()
                last_trade_time = now

            time.sleep(0.5)

    def _poll_telegram(self):
        """Haal en verwerk inkomende Telegram berichten."""
        updates = self.telegram.get_updates(offset=self.update_offset)
        for update in updates:
            self.update_offset = update["update_id"] + 1
            message = update.get("message")
            if not message:
                continue

            text = message.get("text", "")
            chat_id = str(message.get("chat", {}).get("id", ""))

            if not text.startswith("/"):
                continue

            logger.info(f"Telegram commando: {text} (chat: {chat_id})")
            response = self.telegram.handle_command(text, chat_id)
            self.telegram.send_message(response, chat_id)

    def _run_strategy(self):
        """Voer de trading strategie uit voor alle geconfigureerde symbolen."""
        for symbol in Config.SYMBOLS:

            sig = self.strategy.get_signal(symbol)
            print(symbol)
            pprint(sig)
            print('-------------')

            if sig["signal"] == "buy":
                logger.info(f"BUY signaal voor {symbol}: {sig['reason']}")
                self._execute_buy(symbol, Config.QUANTITY, sig)

            elif sig["signal"] == "sell":
                logger.info(f"SELL signaal voor {symbol}: {sig['reason']}")
                self._execute_sell(symbol, Config.QUANTITY, sig)

            else:
                logger.debug(f"HOLD voor {symbol}: {sig.get('reason', '')}")



    def _execute_buy(self, symbol: str, qty: float, signal: dict):
        """Voer een kooporder uit en log deze."""
        price = signal.get("price")
        order = self.trader.buy(symbol, qty)

        if order:
            order_id = order.get("id", "")
            fill_price = float(order.get("filled_avg_price") or 0) or price or 0
            self.db.log_trade(
                symbol, "buy", qty, fill_price, order_id, strategy=Config.STRATEGY
            )
            self.telegram.send_message(
                f"🟢 *Auto BUY*\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"{symbol}: {qty} stuks @ ${fill_price:.2f}\n"
                f"Reden: {signal.get('reason', '')}"
            )
            logger.info(f"Buy order geplaatst: {symbol} {qty} @ ${fill_price:.2f}")
        else:
            logger.error(f"Buy order mislukt voor {symbol}")
            self.telegram.send_message(f"❌ Auto BUY mislukt voor {symbol}")

    def _execute_sell(self, symbol: str, qty: float, signal: dict):
        """Voer een verkooporder uit, bereken W/V en log deze."""
        price = signal.get("price")

        # Controleer of we een positie hebben om te verkopen
        position = self.trader.get_position(symbol)
        if not position:
            logger.info(f"Geen positie om te verkopen voor {symbol}")
            return

        # Verkoop maximaal wat we bezitten
        position_qty = float(position.get("qty", 0))
        sell_qty = min(qty, position_qty)

        order = self.trader.sell(symbol, sell_qty)

        if order:
            order_id = order.get("id", "")
            fill_price = float(order.get("filled_avg_price") or 0) or price or 0
            avg_cost = float(position.get("avg_entry_price", 0))
            pnl = (fill_price - avg_cost) * sell_qty

            self.db.log_trade(
                symbol,
                "sell",
                sell_qty,
                fill_price,
                order_id,
                strategy=Config.STRATEGY,
                pnl=pnl,
            )
            pnl_icon = "📈" if pnl >= 0 else "📉"
            self.telegram.send_message(
                f"🔴 *Auto SELL*\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"{symbol}: {sell_qty} stuks @ ${fill_price:.2f}\n"
                f"{pnl_icon} W/V: ${pnl:.2f}\n"
                f"Reden: {signal.get('reason', '')}"
            )
            logger.info(
                f"Sell order geplaatst: {symbol} {sell_qty} @ ${fill_price:.2f} (W/V: ${pnl:.2f})"
            )
        else:
            logger.error(f"Sell order mislukt voor {symbol}")
            self.telegram.send_message(f"❌ Auto SELL mislukt voor {symbol}")

    def _shutdown(self, signum, frame):
        """Nette afsluiting bij SIGINT/SIGTERM."""
        logger.info(f"Signaal {signum} ontvangen — bot stopt...")
        self.running = False
        self.telegram.send_message("🔴 Trading Bot wordt gestopt. Tot ziens!")
        sys.exit(0)


if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
