/*
# Create trades table for trading bot

1. New Tables
- `trades` — slaat elke uitgevoerde of gesimuleerde trade op
  - `id` (uuid, primary key)
  - `symbol` (text, niet null) — het aandeel symbool, bijv. "AAPL"
  - `side` (text, niet null) — "buy" of "sell"
  - `qty` (numeric, niet null) — aantal aandelen
  - `price` (numeric, niet null) — uitvoeringsprijs per aandeel
  - `order_id` (text) — Alpaca order ID indien beschikbaar
  - `status` (text, niet null, default 'filled') — order status
  - `strategy` (text) — gebruikte strategie naam
  - `pnl` (numeric) — winst/verlies bij verkoop
  - `created_at` (timestamptz, default now())
2. Security
- Enable RLS on `trades`.
- Single-tenant bot zonder login: anon + authenticated volledige CRUD (data is intentioneel gedeeld).
*/

CREATE TABLE IF NOT EXISTS trades (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol text NOT NULL,
  side text NOT NULL CHECK (side IN ('buy', 'sell')),
  qty numeric NOT NULL CHECK (qty > 0),
  price numeric NOT NULL CHECK (price >= 0),
  order_id text,
  status text NOT NULL DEFAULT 'filled',
  strategy text,
  pnl numeric,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at DESC);

ALTER TABLE trades ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_select_trades" ON trades;
CREATE POLICY "anon_select_trades" ON trades FOR SELECT
  TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_trades" ON trades;
CREATE POLICY "anon_insert_trades" ON trades FOR INSERT
  TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_trades" ON trades;
CREATE POLICY "anon_update_trades" ON trades FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "anon_delete_trades" ON trades;
CREATE POLICY "anon_delete_trades" ON trades FOR DELETE
  TO anon, authenticated USING (true);
