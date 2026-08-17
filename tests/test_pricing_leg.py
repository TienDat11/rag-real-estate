"""Tests for the Story 3.3 pricing tiered leg (price_calc additions).

Layer 1 here covers the pure tier math: attrs.price_tiers parsing, band price
scaling from the real range, honest per-m² range math, and unit-code -> type
band resolution. Later layers (result shape, routing, sql_leg dispatch, workflow
stamp) are covered in this file and the rewrite/stamp test files. No DB/network.
"""

from api.price_calc import (
    DEFAULT_TIER_BANDS,
    Offer,
    per_m2_range,
    price_tiers_from_attrs,
    resolve_unit_type_for_code,
    tiered_band_prices,
)


def _offer(**over):
    base = dict(
        subject_key="unit:camellia/2pn-noi-khu",
        display_name="Căn hộ 2PN View nội khu",
        policy_key="chuan",
        price_min_vnd=3_740_000_000,
        price_max_vnd=4_790_000_000,
        price_quality="range",
        attrs={
            "type": "2PN",
            "view": "nội khu",
            "area_m2": [57.4, 72.1],
            "units": ["CH-15", "CH-18", "CH-10"],
        },
    )
    base.update(over)
    return Offer(**base)


# ---- price_tiers_from_attrs -------------------------------------------------
def test_price_tiers_from_attrs_parses_db_json():
    attrs = {
        "price_tiers": [
            {"band": "t4-t10", "floor_from": 4, "floor_to": 10, "pct": 0.0},
            {"band": "t11-t15", "floor_from": 11, "floor_to": 15, "pct": 2.5},
            {"band": "t16-t20", "floor_from": 16, "floor_to": 20, "pct": 5.0},
            {"band": "t21-25", "floor_from": 21, "floor_to": 25, "pct": 7.5},
        ]
    }
    tiers = price_tiers_from_attrs(attrs)
    assert len(tiers) == 4
    assert tiers[0]["pct"] == 0.0
    assert tiers[3]["pct"] == 7.5
    assert tiers[2]["floor_from"] == 16


def test_price_tiers_missing_attrs_uses_neutral_fallback():
    # No price_tiers in attrs — never fabricate a premium: all pct 0.0.
    tiers = price_tiers_from_attrs({})
    assert tiers == DEFAULT_TIER_BANDS
    assert all(t["pct"] == 0.0 for t in tiers)


def test_price_tiers_invalid_ignored_for_neutral_fallback():
    for bad in (
        {"price_tiers": "not-a-list"},
        {"price_tiers": [{"band": "x"}]},  # missing pct
        {"price_tiers": [{"pct": 500}]},  # pct out of sane range
    ):
        tiers = price_tiers_from_attrs(bad)
        assert tiers == DEFAULT_TIER_BANDS


# ---- tiered_band_prices -----------------------------------------------------
def test_tiered_band_prices_scales_real_range():
    o = _offer()
    # A real attrs tier carries its pct (the neutral fallback ladder is 0.0).
    tier = {"band": "t16-t20", "floor_from": 16, "floor_to": 20, "pct": 5.0}
    lo, hi = tiered_band_prices(o, tier)
    assert lo == 3_927_000_000  # 3_740_000_000 * 1.05
    assert hi == 5_029_500_000  # 4_790_000_000 * 1.05


def test_tiered_band_prices_zero_pct_keeps_base():
    o = _offer()
    lo, hi = tiered_band_prices(o, DEFAULT_TIER_BANDS[0])  # pct 0.0
    assert (lo, hi) == (3_740_000_000, 4_790_000_000)


# ---- per_m2_range -----------------------------------------------------------
def test_per_m2_range_honest_pair():
    # min/m2 = price_min / area_max (largest area -> lowest per-m2);
    # max/m2 = price_max / area_min; round to 1,000 VND.
    lo, hi = per_m2_range(3_740_000_000, 4_790_000_000, [57.4, 72.1])
    assert lo == 51_872_000  # 3740M / 72.1 ~ 51.87M
    assert hi == 83_449_000  # 4790M / 57.4 ~ 83.45M


def test_per_m2_range_rounds_to_nearest_thousand():
    lo, hi = per_m2_range(3_740_000_000, 4_790_000_000, [57.4, 72.1])
    assert lo % 1_000 == 0
    assert hi % 1_000 == 0


# ---- resolve_unit_type_for_code --------------------------------------------
def test_resolve_unit_code_finds_type_band():
    offers = [
        _offer(),
        _offer(
            subject_key="unit:camellia/2pn-mat-duong",
            display_name="2PN mặt đường",
            attrs={
                "type": "2PN",
                "view": "mặt đường",
                "area_m2": [65.1, 69.9],
                "units": ["CH-05", "CH-03A", "CH-01", "CH-02"],
            },
        ),
    ]
    hit = resolve_unit_type_for_code(offers, "CH-10")
    assert hit is not None
    assert hit.subject_key == "unit:camellia/2pn-noi-khu"
    hit2 = resolve_unit_type_for_code(offers, "CH-03A")
    assert hit2 is not None
    assert hit2.subject_key == "unit:camellia/2pn-mat-duong"


def test_resolve_unit_code_normalizes_dash_case():
    offers = [_offer()]
    assert resolve_unit_type_for_code(offers, "ch-10") is not None  # lowercase
    assert resolve_unit_type_for_code(offers, "CH10") is not None  # no dash
    assert resolve_unit_type_for_code(offers, "CH-99") is None  # unknown


# ---- Layer 4: run_pricing (sql_leg, injectable fetch, no pool) ---------------
from decimal import Decimal  # noqa: E402


def _price_row(**over):
    """One v_unit_estimates-shaped row for a 2PN nội khu subject with tiers."""
    row = {
        "subject_key": "unit:camellia/2pn-noi-khu",
        "display_name": "Căn hộ 2PN View nội khu",
        "project_key": "camellia",
        "attrs": '{"type": "2PN", "view": "nội khu", "area_m2": [57.4, 72.1],'
                 ' "units": ["CH-15", "CH-18", "CH-10"],'
                 ' "price_tiers": [{"band": "t4-t10", "floor_from": 4, "floor_to": 10, "pct": 0.0},'
                 ' {"band": "t11-t15", "floor_from": 11, "floor_to": 15, "pct": 2.5},'
                 ' {"band": "t16-t20", "floor_from": 16, "floor_to": 20, "pct": 5.0},'
                 ' {"band": "t21-25", "floor_from": 21, "floor_to": 25, "pct": 7.5}]}',
        "policy_key": "chuan",
        "price_min_vnd": Decimal("3740000000"),
        "price_max_vnd": Decimal("4790000000"),
        "price_quality": "range",
        "deposit_pct": Decimal("30.00"),
        "term_months": 18,
        "interest_rate_pct": Decimal("0.0000"),
    }
    row.update(over)
    return row


def _price_spec(**over):
    spec = {
        "structured_path": "pricing",
        "subject_type": "unit",
        "source": "v_unit_estimates",
        "query_type": "per_m2",
        "limit": 20,
    }
    spec.update(over)
    return spec


def _run_pricing(spec, rows=None, fetch_kwargs=None):
    import asyncio

    from api.sql_leg import run_pricing

    async def fake_fetch():
        if fetch_kwargs and fetch_kwargs.get("raise_"):
            raise RuntimeError("db down")
        return rows or []

    async def go():
        return await run_pricing(spec, None, fetch=fake_fetch)

    return asyncio.run(go())


def test_run_pricing_happy_path():
    result = _run_pricing(_price_spec(), [_price_row()])
    assert result.degraded is False
    assert result.meta["mode"] == "pricing"
    assert result.meta["source"] == "v_unit_estimates"
    assert result.meta["has_approx"] is True  # estimate bands cap confidence (D6)
    assert result.meta["as_of_applied"] is False  # view pins CURRENT_DATE (BH-16)
    assert len(result.rows) == 4  # one fe row per tier band
    assert result.rows[0]["fields"]["leg"] == "pricing"
    assert result.rows[0]["fields"]["floor_band"] == "t4-t10"
    assert result.rows[3]["fields"]["band_pct"] == 7.5
    assert result.rows[3]["fields"]["price_min_vnd"] == 4_020_500_000  # 3740M * 1.075


def test_run_pricing_unit_code_lookup():
    spec = _price_spec(query_type="unit", unit_code="CH-10")
    result = _run_pricing(spec, [_price_row()])
    assert result.degraded is False
    assert len(result.rows) == 4  # CH-10 -> its 2pn-noi-khu band (AC-3, open #O2)
    assert result.rows[0]["fields"]["unit_codes"] == ["CH-15", "CH-18", "CH-10"]


def test_run_pricing_unknown_unit_code_empty_non_degraded():
    spec = _price_spec(query_type="unit", unit_code="CH-99")
    result = _run_pricing(spec, [_price_row()])
    assert result.degraded is False
    assert result.rows == []
    assert result.meta["mode"] == "pricing"


def test_run_pricing_no_estimates_degraded():
    result = _run_pricing(_price_spec(), [])
    assert result.degraded is True
    assert result.meta["degraded_reason"] == "no_estimates"
    assert result.rows == []


def test_run_pricing_fetch_error_degraded():
    result = _run_pricing(_price_spec(), fetch_kwargs={"raise_": True})
    assert result.degraded is True
    assert result.meta["mode"] == "pricing"
    assert result.rows == []


def test_run_sql_leg_dispatches_pricing(monkeypatch):
    import asyncio

    from api import sql_leg as sql_leg_module
    from api.sql_leg import run_sql_leg

    async def fake_fetch():
        return [_price_row()]

    monkeypatch.setattr(sql_leg_module, "_fetch_estimates", fake_fetch)

    async def go():
        return await run_sql_leg(_price_spec(), None, "1m2 giá bao nhiêu theo tầng")

    result = asyncio.run(go())
    assert result.degraded is False
    assert result.meta["mode"] == "pricing"
    assert result.meta["row_count"] == len(result.rows)
    assert result.meta["sql_query"].startswith("SELECT subject_key")

# ---- Layer 2: result shape (fe rows + meta) ---------------------------------
def test_pricing_rows_emits_one_fe_row_per_band():
    from api.price_calc import pricing_rows

    o = _offer(
        attrs={
            "type": "2PN",
            "view": "nội khu",
            "area_m2": [57.4, 72.1],
            "units": ["CH-15", "CH-18", "CH-10"],
            "price_tiers": [
                {"band": "t4-t10", "floor_from": 4, "floor_to": 10, "pct": 0.0},
                {"band": "t11-t15", "floor_from": 11, "floor_to": 15, "pct": 2.5},
                {"band": "t16-t20", "floor_from": 16, "floor_to": 20, "pct": 5.0},
                {"band": "t21-25", "floor_from": 21, "floor_to": 25, "pct": 7.5},
            ],
        }
    )
    rows = pricing_rows([o], {"query_type": "per_m2"})
    assert len(rows) == 4  # one per band
    first = rows[0]
    assert first["fields"]["leg"] == "pricing"
    assert first["fields"]["floor_band"] == "t4-t10"
    assert first["fields"]["price_min_vnd"] == 3_740_000_000
    assert first["fields"]["price_max_vnd"] == 4_790_000_000
    assert first["fields"]["per_m2_min_vnd"] == 51_872_000
    assert first["fields"]["per_m2_max_vnd"] == 83_449_000
    assert first["fields"]["unit_codes"] == ["CH-15", "CH-18", "CH-10"]
    assert first["fields"]["area_m2"] == [57.4, 72.1]
    assert first["quality"] == "range"
    assert first["trust_level"] == "estimate"


def test_pricing_rows_tier_scaling_survives_in_fields():
    from api.price_calc import pricing_rows

    o = _offer(
        attrs={
            "type": "2PN",
            "view": "nội khu",
            "area_m2": [57.4, 72.1],
            "units": [],
            "price_tiers": [{"band": "t21-25", "floor_from": 21, "floor_to": 25, "pct": 7.5}],
        }
    )
    rows = pricing_rows([o], {"query_type": "per_m2"})
    assert rows[0]["fields"]["floor_band"] == "t21-25"
    assert rows[0]["fields"]["band_pct"] == 7.5
    assert rows[0]["fields"]["price_min_vnd"] == 4_020_500_000  # *1.075
    assert rows[0]["fields"]["price_max_vnd"] == 5_149_250_000


def test_pricing_rows_unknown_type_returns_empty():
    from api.price_calc import pricing_rows

    o = _offer(attrs={"type": "2PN", "view": "nội khu", "area_m2": [57.4, 72.1], "units": []})
    assert pricing_rows([o], {"query_type": "unit", "unit_code": "ZZ-99"}) == []
    # A different bedrooms/view spec should not match this offer.
    assert pricing_rows([o], {"query_type": "per_m2", "bedrooms": "3PN"}) == []


def test_pricing_summary_shape():
    from api.price_calc import pricing_summary

    # pricing_summary takes the run result dict (mode/has_approx/row_count...).
    summary = pricing_summary(
        {
            "mode": "pricing",
            "has_approx": True,
            "row_count": 4,
            "matched_subjects": ["unit:camellia/2pn-noi-khu"],
        }
    )
    assert summary["mode"] == "pricing"
    assert summary["has_approx"] is True
    assert summary["row_count"] == 4
    assert summary["matched_subjects"] == ["unit:camellia/2pn-noi-khu"]

