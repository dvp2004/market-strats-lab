from __future__ import annotations

from copy import deepcopy
from typing import Any


INSTRUMENT_FIELDS = [
    "instrument_id",
    "provider_symbol",
    "display_name",
    "asset_class",
    "asset_subclass",
    "economic_role",
    "portfolio_role",
    "core_or_satellite",
    "expected_calendar",
    "currency",
    "price_timezone",
    "quantity_precision",
    "maximum_weight",
    "is_benchmark_only",
    "is_primary_implementation",
    "alternative_proxy_group",
    "requires_corporate_actions",
    "minimum_warmup_months",
    "notes",
]

PROPOSED_INSTRUMENTS = [
    "SPY",
    "QQQ",
    "IWM",
    "RSP",
    "EFA",
    "VGK",
    "EWJ",
    "EEM",
    "VWO",
    "SHY",
    "IEF",
    "TLT",
    "TIP",
    "AGG",
    "LQD",
    "HYG",
    "EMB",
    "GLD",
    "DBC",
    "DBA",
    "DBB",
    "USO",
    "VNQ",
    "UUP",
    "FXE",
    "FXY",
    "FXB",
    "BIL",
    "BTC-USD",
    "ACWI",
]


def _entry(
    instrument_id: str,
    *,
    display_name: str,
    asset_class: str,
    asset_subclass: str,
    economic_role: str,
    portfolio_role: str,
    core_or_satellite: str,
    calendar: str = "us_listed_etf",
    currency: str = "USD",
    timezone: str = "America/New_York",
    maximum_weight: float = 0.10,
    benchmark_only: bool = False,
    primary: bool = True,
    proxy_group: str = "",
    corporate_actions: bool = True,
    warmup: int = 12,
    notes: str = "",
) -> dict[str, Any]:
    return {
        "instrument_id": instrument_id,
        "provider_symbol": instrument_id,
        "display_name": display_name,
        "asset_class": asset_class,
        "asset_subclass": asset_subclass,
        "economic_role": economic_role,
        "portfolio_role": portfolio_role,
        "core_or_satellite": core_or_satellite,
        "expected_calendar": calendar,
        "currency": currency,
        "price_timezone": timezone,
        "quantity_precision": 6,
        "maximum_weight": maximum_weight,
        "is_benchmark_only": benchmark_only,
        "is_primary_implementation": primary,
        "alternative_proxy_group": proxy_group,
        "requires_corporate_actions": corporate_actions,
        "minimum_warmup_months": warmup,
        "notes": notes,
    }


DEFAULT_INSTRUMENT_REGISTRY: dict[str, dict[str, Any]] = {
    "SPY": _entry(
        "SPY",
        display_name="SPDR S&P 500 ETF Trust",
        asset_class="equity",
        asset_subclass="us_large_cap",
        economic_role="US broad equity beta",
        portfolio_role="core_growth",
        core_or_satellite="core",
        notes="Candidate building block and SPY benchmark exemption documented separately.",
    ),
    "QQQ": _entry(
        "QQQ",
        display_name="Invesco QQQ Trust",
        asset_class="equity",
        asset_subclass="us_large_cap_growth",
        economic_role="Nasdaq 100 growth exposure",
        portfolio_role="growth_tilt",
        core_or_satellite="core",
    ),
    "IWM": _entry(
        "IWM",
        display_name="iShares Russell 2000 ETF",
        asset_class="equity",
        asset_subclass="us_small_cap",
        economic_role="US small-cap equity beta",
        portfolio_role="equity_diversifier",
        core_or_satellite="core",
    ),
    "RSP": _entry(
        "RSP",
        display_name="Invesco S&P 500 Equal Weight ETF",
        asset_class="equity",
        asset_subclass="us_equal_weight",
        economic_role="US equal-weight equity exposure",
        portfolio_role="equity_diversifier",
        core_or_satellite="core",
    ),
    "EFA": _entry(
        "EFA",
        display_name="iShares MSCI EAFE ETF",
        asset_class="equity",
        asset_subclass="developed_ex_us",
        economic_role="Developed ex-US equity beta",
        portfolio_role="international_equity",
        core_or_satellite="core",
    ),
    "VGK": _entry(
        "VGK",
        display_name="Vanguard FTSE Europe ETF",
        asset_class="equity",
        asset_subclass="europe",
        economic_role="European equity beta",
        portfolio_role="regional_equity",
        core_or_satellite="core",
    ),
    "EWJ": _entry(
        "EWJ",
        display_name="iShares MSCI Japan ETF",
        asset_class="equity",
        asset_subclass="japan",
        economic_role="Japan equity beta",
        portfolio_role="regional_equity",
        core_or_satellite="core",
    ),
    "EEM": _entry(
        "EEM",
        display_name="iShares MSCI Emerging Markets ETF",
        asset_class="equity",
        asset_subclass="emerging_markets",
        economic_role="Emerging-market equity beta",
        portfolio_role="international_equity",
        core_or_satellite="core",
        proxy_group="emerging_markets_equity",
        notes="Primary implementation proxy for EEM/VWO group in GMA-0 config.",
    ),
    "VWO": _entry(
        "VWO",
        display_name="Vanguard FTSE Emerging Markets ETF",
        asset_class="equity",
        asset_subclass="emerging_markets",
        economic_role="Emerging-market equity beta",
        portfolio_role="alternative_proxy",
        core_or_satellite="satellite",
        primary=False,
        proxy_group="emerging_markets_equity",
        notes="Alternative proxy; registry must not allocate to both EEM and VWO automatically.",
    ),
    "SHY": _entry(
        "SHY",
        display_name="iShares 1-3 Year Treasury Bond ETF",
        asset_class="fixed_income",
        asset_subclass="short_treasury",
        economic_role="Short-duration Treasury ballast",
        portfolio_role="defensive_bond",
        core_or_satellite="core",
    ),
    "IEF": _entry(
        "IEF",
        display_name="iShares 7-10 Year Treasury Bond ETF",
        asset_class="fixed_income",
        asset_subclass="intermediate_treasury",
        economic_role="Intermediate-duration Treasury ballast",
        portfolio_role="defensive_bond",
        core_or_satellite="core",
    ),
    "TLT": _entry(
        "TLT",
        display_name="iShares 20+ Year Treasury Bond ETF",
        asset_class="fixed_income",
        asset_subclass="long_treasury",
        economic_role="Long-duration Treasury convexity",
        portfolio_role="defensive_bond",
        core_or_satellite="core",
    ),
    "TIP": _entry(
        "TIP",
        display_name="iShares TIPS Bond ETF",
        asset_class="fixed_income",
        asset_subclass="inflation_linked",
        economic_role="Inflation-linked Treasury exposure",
        portfolio_role="inflation_hedge",
        core_or_satellite="core",
    ),
    "AGG": _entry(
        "AGG",
        display_name="iShares Core U.S. Aggregate Bond ETF",
        asset_class="fixed_income",
        asset_subclass="aggregate_bond",
        economic_role="Core US investment-grade bond exposure",
        portfolio_role="defensive_bond",
        core_or_satellite="core",
    ),
    "LQD": _entry(
        "LQD",
        display_name="iShares iBoxx Investment Grade Corporate Bond ETF",
        asset_class="fixed_income",
        asset_subclass="investment_grade_credit",
        economic_role="Investment-grade corporate credit exposure",
        portfolio_role="credit",
        core_or_satellite="core",
    ),
    "HYG": _entry(
        "HYG",
        display_name="iShares iBoxx High Yield Corporate Bond ETF",
        asset_class="fixed_income",
        asset_subclass="high_yield_credit",
        economic_role="High-yield credit risk exposure",
        portfolio_role="credit_risk",
        core_or_satellite="core",
    ),
    "EMB": _entry(
        "EMB",
        display_name="iShares J.P. Morgan USD Emerging Markets Bond ETF",
        asset_class="fixed_income",
        asset_subclass="emerging_market_debt",
        economic_role="USD emerging-market sovereign debt",
        portfolio_role="credit_diversifier",
        core_or_satellite="core",
    ),
    "GLD": _entry(
        "GLD",
        display_name="SPDR Gold Shares",
        asset_class="commodity",
        asset_subclass="gold",
        economic_role="Gold exposure",
        portfolio_role="crisis_diversifier",
        core_or_satellite="core",
    ),
    "DBC": _entry(
        "DBC",
        display_name="Invesco DB Commodity Index Tracking Fund",
        asset_class="commodity",
        asset_subclass="broad_commodities",
        economic_role="Broad commodity exposure",
        portfolio_role="inflation_hedge",
        core_or_satellite="core",
        proxy_group="commodity_complex",
        notes="Primary broad commodity proxy for DBC/DBA/DBB/USO group.",
    ),
    "DBA": _entry(
        "DBA",
        display_name="Invesco DB Agriculture Fund",
        asset_class="commodity",
        asset_subclass="agriculture",
        economic_role="Agriculture commodity exposure",
        portfolio_role="commodity_satellite",
        core_or_satellite="satellite",
        primary=False,
        proxy_group="commodity_complex",
    ),
    "DBB": _entry(
        "DBB",
        display_name="Invesco DB Base Metals Fund",
        asset_class="commodity",
        asset_subclass="base_metals",
        economic_role="Industrial metals commodity exposure",
        portfolio_role="commodity_satellite",
        core_or_satellite="satellite",
        primary=False,
        proxy_group="commodity_complex",
    ),
    "USO": _entry(
        "USO",
        display_name="United States Oil Fund",
        asset_class="commodity",
        asset_subclass="crude_oil",
        economic_role="Crude oil futures-linked exposure",
        portfolio_role="commodity_satellite",
        core_or_satellite="satellite",
        primary=False,
        proxy_group="commodity_complex",
    ),
    "VNQ": _entry(
        "VNQ",
        display_name="Vanguard Real Estate ETF",
        asset_class="real_assets",
        asset_subclass="us_reit",
        economic_role="US listed real estate exposure",
        portfolio_role="real_asset_diversifier",
        core_or_satellite="core",
    ),
    "UUP": _entry(
        "UUP",
        display_name="Invesco DB US Dollar Index Bullish Fund",
        asset_class="currency",
        asset_subclass="usd_index",
        economic_role="US dollar exposure",
        portfolio_role="currency_satellite",
        core_or_satellite="core",
    ),
    "FXE": _entry(
        "FXE",
        display_name="Invesco CurrencyShares Euro Trust",
        asset_class="currency",
        asset_subclass="euro",
        economic_role="Euro currency exposure",
        portfolio_role="currency_satellite",
        core_or_satellite="satellite",
    ),
    "FXY": _entry(
        "FXY",
        display_name="Invesco CurrencyShares Japanese Yen Trust",
        asset_class="currency",
        asset_subclass="yen",
        economic_role="Japanese yen currency exposure",
        portfolio_role="currency_satellite",
        core_or_satellite="satellite",
    ),
    "FXB": _entry(
        "FXB",
        display_name="Invesco CurrencyShares British Pound Sterling Trust",
        asset_class="currency",
        asset_subclass="gbp",
        economic_role="British pound currency exposure",
        portfolio_role="currency_satellite",
        core_or_satellite="satellite",
    ),
    "BIL": _entry(
        "BIL",
        display_name="SPDR Bloomberg 1-3 Month T-Bill ETF",
        asset_class="cash_equivalent",
        asset_subclass="t_bill",
        economic_role="Cash-equivalent Treasury bills",
        portfolio_role="cash_proxy",
        core_or_satellite="core",
    ),
    "BTC-USD": _entry(
        "BTC-USD",
        display_name="Bitcoin USD",
        asset_class="crypto",
        asset_subclass="bitcoin",
        economic_role="Bitcoin spot proxy",
        portfolio_role="high_caveat_satellite",
        core_or_satellite="satellite",
        calendar="bitcoin_utc_daily",
        timezone="UTC",
        maximum_weight=0.05,
        corporate_actions=False,
        notes="Must not delay core replay; dynamically eligible only after own warm-up.",
    ),
    "ACWI": _entry(
        "ACWI",
        display_name="iShares MSCI ACWI ETF",
        asset_class="equity",
        asset_subclass="global_equity",
        economic_role="Global equity benchmark",
        portfolio_role="benchmark",
        core_or_satellite="benchmark",
        benchmark_only=True,
        maximum_weight=1.0,
        notes="Benchmark-only exemption documented; does not delay core allocator-common-date.",
    ),
}


CALENDAR_REGISTRY = [
    {
        "calendar_id": "us_listed_etf",
        "description": "US-listed ETF exchange trading calendar",
        "expected_observation_pattern": "business-day observations excluding exchange holidays",
        "weekend_observations_expected": False,
        "notes": "Used for Yahoo daily ETF bars; GMA-0 does not repair holiday gaps.",
    },
    {
        "calendar_id": "bitcoin_utc_daily",
        "description": "Bitcoin 24/7 UTC calendar",
        "expected_observation_pattern": "daily UTC observations including weekends",
        "weekend_observations_expected": True,
        "notes": "BTC weekends are preserved during availability audit.",
    },
    {
        "calendar_id": "macro_publication_placeholder",
        "description": "Macro publication calendar placeholder",
        "expected_observation_pattern": "series-specific release calendar",
        "weekend_observations_expected": False,
        "notes": "Design placeholder only; no macro series downloaded in GMA-0.",
    },
]

MACRO_SERIES_REGISTRY = [
    ("3-month cash rate", "cash_rate_3m", "daily_or_monthly", True),
    ("2-year Treasury yield", "treasury_2y", "daily", False),
    ("10-year Treasury yield", "treasury_10y", "daily", False),
    ("30-year Treasury yield", "treasury_30y", "daily", False),
    ("10y-2y curve", "curve_10y_2y", "derived_daily", False),
    ("10y-3m curve", "curve_10y_3m", "derived_daily", False),
    ("10-year breakeven inflation", "breakeven_10y", "daily", False),
    ("real-yield proxy", "real_yield_proxy", "daily", False),
    ("VIX", "vix", "daily", False),
    ("high-yield option-adjusted spread", "hy_oas", "daily", False),
    ("financial-conditions or stress index", "financial_conditions", "weekly", True),
    ("CPI", "cpi", "monthly", True),
    ("unemployment", "unemployment", "monthly", True),
    ("industrial production", "industrial_production", "monthly", True),
]


def default_instrument_registry() -> dict[str, dict[str, Any]]:
    return deepcopy(DEFAULT_INSTRUMENT_REGISTRY)


def validate_registry(registry: dict[str, dict[str, Any]]) -> None:
    seen_provider_symbols: set[str] = set()
    missing_ids = sorted(set(PROPOSED_INSTRUMENTS) - set(registry))
    if missing_ids:
        raise ValueError(f"Missing proposed instruments: {missing_ids}")
    for key, entry in registry.items():
        missing = [field for field in INSTRUMENT_FIELDS if field not in entry]
        if missing:
            raise ValueError(f"{key}: missing registry fields: {missing}")
        if entry["instrument_id"] != key:
            raise ValueError(f"{key}: instrument_id must match registry key")
        provider_symbol = str(entry["provider_symbol"])
        if provider_symbol in seen_provider_symbols:
            raise ValueError(f"Duplicate provider symbol: {provider_symbol}")
        seen_provider_symbols.add(provider_symbol)


def registry_frame(registry: dict[str, dict[str, Any]]) -> Any:
    import pandas as pd

    return pd.DataFrame([registry[key] for key in sorted(registry)])


def calendar_frame() -> Any:
    import pandas as pd

    return pd.DataFrame(CALENDAR_REGISTRY)


def macro_series_frame() -> Any:
    import pandas as pd

    rows = []
    for display_name, series_id, frequency, vintage_required in MACRO_SERIES_REGISTRY:
        rows.append(
            {
                "series_id": series_id,
                "display_name": display_name,
                "frequency": frequency,
                "point_in_time_release_timestamp_required": True,
                "vintage_aware_retrieval_required": bool(vintage_required),
                "downloaded_in_gma0": False,
                "notes": "Design registry only; retrieval deferred until a later phase.",
            }
        )
    return pd.DataFrame(rows)
