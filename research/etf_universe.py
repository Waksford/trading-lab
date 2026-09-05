"""Universo ETF curado para investigación; no es una estrategia productiva."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ETF:
    symbol: str
    name: str
    category: str


CATEGORIES = (
    "Broad US Equity", "US Sectors", "US Style / Factors", "Size",
    "International Developed", "Emerging Markets", "Bonds / Treasuries",
    "Investment Grade / High Yield", "Gold / Commodities", "Real Estate",
)


ETF_UNIVERSE = (
    ETF("SPY", "SPDR S&P 500 ETF Trust", "Broad US Equity"),
    ETF("VOO", "Vanguard S&P 500 ETF", "Broad US Equity"),
    ETF("IVV", "iShares Core S&P 500 ETF", "Broad US Equity"),
    ETF("QQQ", "Invesco QQQ Trust", "Broad US Equity"),
    ETF("DIA", "SPDR Dow Jones Industrial Average ETF", "Broad US Equity"),
    ETF("VTI", "Vanguard Total Stock Market ETF", "Broad US Equity"),
    ETF("SCHB", "Schwab U.S. Broad Market ETF", "Broad US Equity"),
    ETF("ITOT", "iShares Core S&P Total U.S. Stock Market ETF", "Broad US Equity"),
    ETF("RSP", "Invesco S&P 500 Equal Weight ETF", "Broad US Equity"),
    ETF("XLK", "Technology Select Sector SPDR Fund", "US Sectors"),
    ETF("XLF", "Financial Select Sector SPDR Fund", "US Sectors"),
    ETF("XLE", "Energy Select Sector SPDR Fund", "US Sectors"),
    ETF("XLV", "Health Care Select Sector SPDR Fund", "US Sectors"),
    ETF("XLI", "Industrial Select Sector SPDR Fund", "US Sectors"),
    ETF("XLY", "Consumer Discretionary Select Sector SPDR Fund", "US Sectors"),
    ETF("XLP", "Consumer Staples Select Sector SPDR Fund", "US Sectors"),
    ETF("XLU", "Utilities Select Sector SPDR Fund", "US Sectors"),
    ETF("XLB", "Materials Select Sector SPDR Fund", "US Sectors"),
    ETF("XLRE", "Real Estate Select Sector SPDR Fund", "US Sectors"),
    ETF("XLC", "Communication Services Select Sector SPDR Fund", "US Sectors"),
    ETF("VUG", "Vanguard Growth ETF", "US Style / Factors"),
    ETF("VTV", "Vanguard Value ETF", "US Style / Factors"),
    ETF("QUAL", "iShares MSCI USA Quality Factor ETF", "US Style / Factors"),
    ETF("MTUM", "iShares MSCI USA Momentum Factor ETF", "US Style / Factors"),
    ETF("USMV", "iShares MSCI USA Min Vol Factor ETF", "US Style / Factors"),
    ETF("VLUE", "iShares MSCI USA Value Factor ETF", "US Style / Factors"),
    ETF("VIG", "Vanguard Dividend Appreciation ETF", "US Style / Factors"),
    ETF("SCHD", "Schwab U.S. Dividend Equity ETF", "US Style / Factors"),
    ETF("IWM", "iShares Russell 2000 ETF", "Size"),
    ETF("IJH", "iShares Core S&P Mid-Cap ETF", "Size"),
    ETF("IJR", "iShares Core S&P Small-Cap ETF", "Size"),
    ETF("VB", "Vanguard Small-Cap ETF", "Size"),
    ETF("VO", "Vanguard Mid-Cap ETF", "Size"),
    ETF("MDY", "SPDR S&P MidCap 400 ETF Trust", "Size"),
    ETF("VEA", "Vanguard FTSE Developed Markets ETF", "International Developed"),
    ETF("EFA", "iShares MSCI EAFE ETF", "International Developed"),
    ETF("VGK", "Vanguard FTSE Europe ETF", "International Developed"),
    ETF("EWJ", "iShares MSCI Japan ETF", "International Developed"),
    ETF("EWG", "iShares MSCI Germany ETF", "International Developed"),
    ETF("EWU", "iShares MSCI United Kingdom ETF", "International Developed"),
    ETF("EWC", "iShares MSCI Canada ETF", "International Developed"),
    ETF("EWA", "iShares MSCI Australia ETF", "International Developed"),
    ETF("VWO", "Vanguard FTSE Emerging Markets ETF", "Emerging Markets"),
    ETF("EEM", "iShares MSCI Emerging Markets ETF", "Emerging Markets"),
    ETF("IEMG", "iShares Core MSCI Emerging Markets ETF", "Emerging Markets"),
    ETF("MCHI", "iShares MSCI China ETF", "Emerging Markets"),
    ETF("INDA", "iShares MSCI India ETF", "Emerging Markets"),
    ETF("EWZ", "iShares MSCI Brazil ETF", "Emerging Markets"),
    ETF("TLT", "iShares 20+ Year Treasury Bond ETF", "Bonds / Treasuries"),
    ETF("IEF", "iShares 7-10 Year Treasury Bond ETF", "Bonds / Treasuries"),
    ETF("SHY", "iShares 1-3 Year Treasury Bond ETF", "Bonds / Treasuries"),
    ETF("BND", "Vanguard Total Bond Market ETF", "Bonds / Treasuries"),
    ETF("AGG", "iShares Core U.S. Aggregate Bond ETF", "Bonds / Treasuries"),
    ETF("GOVT", "iShares U.S. Treasury Bond ETF", "Bonds / Treasuries"),
    ETF("TIP", "iShares TIPS Bond ETF", "Bonds / Treasuries"),
    ETF("VGSH", "Vanguard Short-Term Treasury ETF", "Bonds / Treasuries"),
    ETF("LQD", "iShares iBoxx Investment Grade Corporate Bond ETF", "Investment Grade / High Yield"),
    ETF("VCIT", "Vanguard Intermediate-Term Corporate Bond ETF", "Investment Grade / High Yield"),
    ETF("VCSH", "Vanguard Short-Term Corporate Bond ETF", "Investment Grade / High Yield"),
    ETF("HYG", "iShares iBoxx High Yield Corporate Bond ETF", "Investment Grade / High Yield"),
    ETF("JNK", "SPDR Bloomberg High Yield Bond ETF", "Investment Grade / High Yield"),
    ETF("GLD", "SPDR Gold Shares", "Gold / Commodities"),
    ETF("IAU", "iShares Gold Trust", "Gold / Commodities"),
    ETF("SLV", "iShares Silver Trust", "Gold / Commodities"),
    ETF("DBC", "Invesco DB Commodity Index Tracking Fund", "Gold / Commodities"),
    ETF("PDBC", "Invesco Optimum Yield Diversified Commodity Strategy", "Gold / Commodities"),
    ETF("USO", "United States Oil Fund", "Gold / Commodities"),
    ETF("VNQ", "Vanguard Real Estate ETF", "Real Estate"),
    ETF("IYR", "iShares U.S. Real Estate ETF", "Real Estate"),
    ETF("SCHH", "Schwab U.S. REIT ETF", "Real Estate"),
    ETF("REET", "iShares Global REIT ETF", "Real Estate"),
    ETF("RWO", "SPDR Dow Jones Global Real Estate ETF", "Real Estate"),
)


PROHIBITED_TOKENS = ("2X", "3X", "ULTRA", "INVERSE", "BEAR", "VIX")


def validate_universe(universe=ETF_UNIVERSE):
    """Valida duplicados, categorías y descriptores de productos excluidos."""
    symbols = [etf.symbol for etf in universe]
    if len(symbols) != len(set(symbols)):
        raise ValueError("El universo ETF contiene símbolos duplicados")
    for etf in universe:
        if etf.category not in CATEGORIES:
            raise ValueError(f"Categoría ETF desconocida: {etf.category}")
        descriptor = f"{etf.symbol} {etf.name}".upper()
        if any(token in descriptor for token in PROHIBITED_TOKENS):
            raise ValueError(f"ETF excluido por estructura: {etf.symbol}")
    return True


validate_universe()
