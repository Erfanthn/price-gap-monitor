"""Alert when a coin on Bitpin is offered below what Bybit is bidding for it.

If the best ask on Bitpin is cheaper than the best bid on Bybit, someone can buy
here and sell there. For the platform that is a pricing problem worth seeing
quickly. For IRT pairs, the Bybit price is converted with Bitpin's own
USDT_IRT bid.

    python price_gap.py            # loop, every INTERVAL seconds
    python price_gap.py --once     # one round
"""
import argparse
import asyncio
import logging
import os
from datetime import datetime

import aiohttp

BYBIT_ORDERBOOK = "https://api.bybit.com/v5/market/orderbook"
BITPIN_ORDERBOOK = "https://api.bitpin.org/api/v1/mth/orderbook/{symbol}/"

log = logging.getLogger("price_gap")


def load_env(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if v.strip():
                    os.environ.setdefault(k.strip(), v.strip())


def gap_pct(reference: float, ask: float) -> float:
    """How far below the reference price the ask is, in percent (positive = cheaper)."""
    return (reference - ask) / reference * 100


async def get_json(session, url, params=None):
    try:
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                log.warning("%s -> HTTP %s", url, r.status)
                return None
            return await r.json()
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        log.warning("%s -> %s", url, type(e).__name__)
        return None


async def bybit_bid(session, base):
    data = await get_json(session, BYBIT_ORDERBOOK, {"category": "spot", "symbol": f"{base}USDT", "limit": 1})
    if not data or data.get("retCode") != 0:
        return None
    bids = data.get("result", {}).get("b") or []
    return float(bids[0][0]) if bids else None


async def bitpin_top(session, symbol, side):
    data = await get_json(session, BITPIN_ORDERBOOK.format(symbol=symbol))
    rows = (data or {}).get(side) or []
    return float(rows[0][0]) if rows else None


async def check(session, symbol, cfg):
    base, quote = symbol.split("_", 1)
    if quote == "USDT":
        ref, ask = await asyncio.gather(bybit_bid(session, base), bitpin_top(session, symbol, "asks"))
        threshold = cfg["usdt_threshold"]
    elif quote == "IRT":
        bid, rate, ask = await asyncio.gather(
            bybit_bid(session, base),
            bitpin_top(session, "USDT_IRT", "bids"),
            bitpin_top(session, symbol, "asks"),
        )
        ref = bid * rate if bid and rate else None
        threshold = cfg["irt_threshold"]
    else:
        log.warning("%s: only USDT and IRT pairs are supported", symbol)
        return None
    if ref is None or ask is None:
        log.info("%s: missing price, skipped", symbol)
        return None
    g = gap_pct(ref, ask)
    log.info("%s: Bybit-based %.8g, Bitpin ask %.8g, gap %+.3f%%", symbol, ref, ask, g)
    if g >= threshold:
        return (f"{symbol}: Bitpin ask {ask:,.8g} is {g:.2f}% below the Bybit-based price "
                f"{ref:,.8g} (threshold {threshold}%) at {datetime.now():%Y-%m-%d %H:%M:%S}")
    return None


async def send(session, text):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print(text, flush=True)
        return
    try:
        async with session.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                json={"chat_id": chat, "text": text},
                                timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                log.warning("Telegram returned %s", r.status)
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        log.warning("Telegram send failed: %s", type(e).__name__)  # never log the URL: it has the token


async def run(cfg, once):
    async with aiohttp.ClientSession() as session:
        while True:
            results = await asyncio.gather(*(check(session, s, cfg) for s in cfg["symbols"]))
            for msg in filter(None, results):
                await send(session, msg)
            if once:
                return
            await asyncio.sleep(cfg["interval"])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--once", action="store_true")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_env()
    cfg = {
        "symbols": [s.strip().upper() for s in os.environ.get(
            "SYMBOLS", "BTC_USDT,BTC_IRT,ETH_USDT,ETH_IRT,XRP_USDT,XRP_IRT").split(",") if s.strip()],
        "usdt_threshold": float(os.environ.get("USDT_THRESHOLD", "1.0")),
        "irt_threshold": float(os.environ.get("IRT_THRESHOLD", "0.5")),
        "interval": int(os.environ.get("INTERVAL", "60")),
    }
    asyncio.run(run(cfg, a.once))


if __name__ == "__main__":
    main()
