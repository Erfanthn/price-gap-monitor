# price-gap-monitor

A small watcher that compares Bitpin's order book with Bybit's and tells you
when a coin on Bitpin is offered **below** what Bybit is bidding for it.

That situation means anyone can buy on one platform and sell on the other.
For the platform, it is usually a sign that a price feed is stuck or a market
maker has stepped away, and it is better to see it in a minute than in an hour.

## How it works

Every minute, for each symbol:

* `XXX_USDT`: Bybit best bid vs Bitpin best ask.
* `XXX_IRT`: Bybit best bid × Bitpin's `USDT_IRT` best bid, vs Bitpin best ask.

```
gap % = (Bybit-based price - Bitpin ask) / Bybit-based price × 100
```

If the gap is above the threshold (default 1% for USDT pairs, 0.5% for IRT
pairs, because the IRT books move with the rial too), it sends one line to
Telegram, or prints it if no bot is set up. All requests in a round run in
parallel with `aiohttp`, so 50 symbols take about as long as one.

Only public order-book endpoints are used. No API key is needed.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env     # symbols, thresholds, optional Telegram bot
python price_gap.py --once
python price_gap.py
python -m pytest -q
```

## Notes

* Top-of-book only. A 2% gap on a book with $50 on the ask side is not the
  same as a 2% gap with $50,000, and this tool does not check depth yet.
* I built the first version at work to keep an eye on our prices, and this is
  a cleaned-up public rewrite with no keys or internal settings. I wrote it
  with a lot of help from AI tools.

## License

MIT
