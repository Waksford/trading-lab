from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import (
    AssetClass,
    AssetStatus
)


PALABRAS_EXCLUIDAS = [
    " ETF",
    "ETN",
    " FUND",
    "TRUST",
    "DEPOSITARY",
    "DEPOSITORY",
    "PREFERRED",
    "PREFERENCE",
    "NOTES",
    "NOTE DUE",
    "BOND",
    "TREASURY",
    "WARRANT",
    "WARRANTS",
    "UNITS",
    "UNIT ",
    "ACQUISITION",
    "CAPITAL SECURITIES",
    "SUBORDINATED",
    "DEBENTURE",
    "RIGHTS",
    "RIGHT ",
    "CREDIT OPPORTUNITIES",
    "CLOSED-END",
    "INVESTMENT FUND",
    "INCOME FUND",
    "MUTUAL FUND"
]


EXCHANGES_EMPRESAS = {
    "NASDAQ",
    "NYSE",
    "AMEX"
}


def parece_accion_ordinaria(
    nombre
):

    if not nombre:
        return False

    nombre_upper = (
        nombre.upper()
    )

    for palabra in PALABRAS_EXCLUIDAS:

        if palabra in nombre_upper:
            return False

    return True


def obtener_universo_usa(
    api_key,
    secret_key
):

    client = TradingClient(
        api_key,
        secret_key,
        paper=True
    )

    request = GetAssetsRequest(
        asset_class=AssetClass.US_EQUITY,
        status=AssetStatus.ACTIVE
    )

    assets = client.get_all_assets(
        request
    )

    print(
        f"Activos recibidos desde Alpaca: "
        f"{len(assets)}"
    )

    universo = []

    descartados_tipo = 0

    for asset in assets:

        if not asset.tradable:
            continue

        symbol = asset.symbol

        nombre = (
            asset.name
            or ""
        )

        if "." in symbol:
            continue

        exchange = (
            asset.exchange.value
            if hasattr(
                asset.exchange,
                "value"
            )
            else str(
                asset.exchange
            )
        )

        if (
            exchange
            not in EXCHANGES_EMPRESAS
        ):
            continue

        if not parece_accion_ordinaria(
            nombre
        ):

            descartados_tipo += 1
            continue

        universo.append({

            "symbol": symbol,

            "nombre": nombre,

            "exchange": exchange,

            "fractionable": (
                asset.fractionable
            )
        })

    print(
        f"Descartados por tipo de instrumento: "
        f"{descartados_tipo}"
    )

    print(
        f"Posibles acciones ordinarias: "
        f"{len(universo)}"
    )

    return universo