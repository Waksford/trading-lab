"""Proveedor exclusivamente de MARKET DATA para opciones Alpaca.

No importa TradingClient, modelos de orden ni endpoints de ejecucion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import os
import re


CONTRACT_RE = re.compile(r"^([A-Z]+?)(\d{6})([CP])(\d{8})$")
SUPPORTED_FEEDS = ("opra", "indicative")


class AlpacaOptionsError(RuntimeError):
    pass


class AlpacaEntitlementError(AlpacaOptionsError):
    pass


def _value(obj, name, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _iso(value):
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def parse_contract_symbol(symbol):
    match = CONTRACT_RE.match(str(symbol).strip().upper())
    if not match:
        raise ValueError(f"Simbolo de opcion no reconocido: {symbol}")
    root, expiry, option_code, strike = match.groups()
    return {
        "root_symbol": root,
        "expiration_date": datetime.strptime(expiry, "%y%m%d").date().isoformat(),
        "strike": int(strike) / 1000,
        "option_type": "call" if option_code == "C" else "put",
        "is_call": option_code == "C",
        "is_put": option_code == "P",
    }


def normalize_snapshot(symbol, snapshot, feed):
    contract = parse_contract_symbol(symbol)
    quote = _value(snapshot, "latest_quote")
    trade = _value(snapshot, "latest_trade")
    greeks = _value(snapshot, "greeks")
    return {
        "contract_symbol": str(symbol).upper(), **contract,
        "bid": _value(quote, "bid_price"), "ask": _value(quote, "ask_price"),
        "bid_size": _value(quote, "bid_size"), "ask_size": _value(quote, "ask_size"),
        "quote_timestamp": _iso(_value(quote, "timestamp")),
        "last": _value(trade, "price"),
        "trade_timestamp": _iso(_value(trade, "timestamp")),
        "implied_volatility": _value(snapshot, "implied_volatility"),
        "delta": _value(greeks, "delta"), "gamma": _value(greeks, "gamma"),
        "theta": _value(greeks, "theta"), "vega": _value(greeks, "vega"),
        "rho": _value(greeks, "rho"),
        "open_interest": _value(snapshot, "open_interest"),
        "volume": _value(snapshot, "volume"), "feed": str(feed).lower(),
        "source": "ALPACA",
    }


@dataclass
class ChainResult:
    underlying: str
    feed: str
    snapshots: list[dict]


class AlpacaOptionsMarketDataProvider:
    """Adaptador mínimo sobre clientes históricos oficiales de alpaca-py."""

    def __init__(self, api_key=None, secret_key=None, option_client=None,
                 stock_client=None):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        if not self.api_key or not self.secret_key:
            raise AlpacaOptionsError("Faltan ALPACA_API_KEY/ALPACA_SECRET_KEY")
        if option_client is None or stock_client is None:
            from alpaca.data.historical import OptionHistoricalDataClient, StockHistoricalDataClient
            option_client = option_client or OptionHistoricalDataClient(self.api_key, self.secret_key)
            stock_client = stock_client or StockHistoricalDataClient(self.api_key, self.secret_key)
        self.option_client = option_client
        self.stock_client = stock_client

    def get_underlying_price(self, underlying):
        """Consulta un latest trade de mercado; los índices pueden no estar soportados."""
        from alpaca.data.requests import StockLatestTradeRequest
        response = self.stock_client.get_stock_latest_trade(
            StockLatestTradeRequest(symbol_or_symbols=[underlying])
        )
        trade = response.get(underlying) if isinstance(response, dict) else None
        return {
            "spot_price": _value(trade, "price"),
            "trade_timestamp": _iso(_value(trade, "timestamp")),
            "daily_change_pct": None,
        }

    def get_chain(self, underlying, feed):
        if str(feed).lower() not in SUPPORTED_FEEDS:
            raise ValueError(f"Feed no soportado: {feed}")
        from alpaca.data.enums import OptionsFeed
        from alpaca.data.requests import OptionChainRequest
        feed_enum = OptionsFeed.OPRA if str(feed).lower() == "opra" else OptionsFeed.INDICATIVE
        try:
            response = self.option_client.get_option_chain(
                OptionChainRequest(underlying_symbol=underlying, feed=feed_enum)
            )
        except Exception as error:
            message = str(error).lower()
            if ("403" in message or "subscription" in message or "entitle" in message
                    or "agreement is not signed" in message):
                raise AlpacaEntitlementError(str(error)) from error
            raise AlpacaOptionsError(str(error)) from error
        snapshots = []
        for symbol, snapshot in (response or {}).items():
            try:
                snapshots.append(normalize_snapshot(symbol, snapshot, feed))
            except (TypeError, ValueError):
                continue
        return ChainResult(underlying=underlying, feed=str(feed).lower(), snapshots=snapshots)

    def discover_chain(self, underlying):
        """Prueba OPRA de forma explícita y cae a INDICATIVE solo por entitlement."""
        errors = []
        for feed in SUPPORTED_FEEDS:
            try:
                return self.get_chain(underlying, feed), errors
            except AlpacaEntitlementError as error:
                errors.append(f"{feed.upper()}: entitlement: {error}")
        raise AlpacaEntitlementError(" | ".join(errors) or "Sin feed de opciones disponible")
