import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Centrale configuratie voor de trading bot. Leest alle instellingen uit .env."""

    # Alpaca API
    ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
    ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
    ALPACA_BASE_URL = os.getenv(
        "ALPACA_BASE_URL", "https://paper-api.alpaca.markets"
    )
    ALPACA_DATA_URL = os.getenv(
        "ALPACA_DATA_URL", "https://data.alpaca.markets/v2"
    )

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")

    # Trading instellingen
    SYMBOLS = [
        s.strip().upper()
        for s in os.getenv("TRADING_SYMBOLS", "AAPL,MSFT,GOOGL").split(",")
        if s.strip()
    ]
    FAST_MA = int(os.getenv("FAST_MA", "10"))
    SLOW_MA = int(os.getenv("SLOW_MA", "30"))
    QUANTITY = float(os.getenv("TRADE_QUANTITY", "1"))
    POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "300"))

    # Strategie keuze: "simple" of "advanced"
    STRATEGY = os.getenv("STRATEGY", "advanced").lower()

    # Advanced strategy instellingen
    RSI_PERIOD = int(os.getenv("RSI_PERIOD", "14"))
    RSI_OVERSOLD = float(os.getenv("RSI_OVERSOLD", "30"))
    RSI_OVERBOUGHT = float(os.getenv("RSI_OVERBOUGHT", "70"))
    MACD_FAST = int(os.getenv("MACD_FAST", "12"))
    MACD_SLOW = int(os.getenv("MACD_SLOW", "26"))
    MACD_SIGNAL = int(os.getenv("MACD_SIGNAL", "9"))
    BB_PERIOD = int(os.getenv("BB_PERIOD", "20"))
    BB_STD = float(os.getenv("BB_STD", "2"))
    VOLUME_PERIOD = int(os.getenv("VOLUME_PERIOD", "20"))

    # Bot status — standaard uit bij opstarten
    AUTO_TRADE_ENABLED = os.getenv("AUTO_TRADE_ENABLED", "false").lower() == "true"
    PAPER_TRADING = "paper-api.alpaca.markets" in ALPACA_BASE_URL

    @classmethod
    def validate(cls) -> list[str]:
        """Controleer of alle benodigde instellingen aanwezig zijn. Geeft een lijst van foutmeldingen terug."""
        errors = []
        if not cls.ALPACA_API_KEY:
            errors.append("ALPACA_API_KEY ontbreekt in .env")
        if not cls.ALPACA_SECRET_KEY:
            errors.append("ALPACA_SECRET_KEY ontbreekt in .env")
        if not cls.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN ontbreekt in .env")
        if not cls.TELEGRAM_CHAT_ID:
            errors.append("TELEGRAM_CHAT_ID ontbreekt in .env")
        if cls.FAST_MA >= cls.SLOW_MA:
            errors.append(
                f"FAST_MA ({cls.FAST_MA}) moet kleiner zijn dan SLOW_MA ({cls.SLOW_MA})"
            )
        if cls.STRATEGY not in ("simple", "advanced"):
            errors.append(
                f"STRATEGY ({cls.STRATEGY}) moet 'simple' of 'advanced' zijn"
            )
        if cls.MACD_FAST >= cls.MACD_SLOW:
            errors.append(
                f"MACD_FAST ({cls.MACD_FAST}) moet kleiner zijn dan MACD_SLOW ({cls.MACD_SLOW})"
            )
        return errors

    @classmethod
    def summary(cls) -> str:
        """Geef een tekstuele samenvatting van de huidige configuratie."""
        mode = "PAPER (simulatie)" if cls.PAPER_TRADING else "LIVE (echt geld!)"
        if cls.STRATEGY == "advanced":
            strat = (
                f"Strategie: Advanced (RSI{cls.RSI_PERIOD}/MACD{cls.MACD_FAST}"
                f"/{cls.MACD_SLOW}/{cls.MACD_SIGNAL}/BB{cls.BB_PERIOD})\n"
            )
        else:
            strat = (
                f"Snelle MA: {cls.FAST_MA} dagen\n"
                f"Trage MA: {cls.SLOW_MA} dagen\n"
            )
        return (
            f"⚙️ *Configuratie*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Mode: {mode}\n"
            f"Symbolen: {', '.join(cls.SYMBOLS)}\n"
            f"{strat}"
            f"Aantal per trade: {cls.QUANTITY}\n"
            f"Poll interval: {cls.POLL_INTERVAL}s\n"
            f"Auto-trade: {'AAN' if cls.AUTO_TRADE_ENABLED else 'UIT'}"
        )
