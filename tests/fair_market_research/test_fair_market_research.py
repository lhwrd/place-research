import pandas as pd

from residence_research.datasets.fair_market_rent import FairMarketRent


def test_fair_market_rent():
    df = FairMarketRent().as_df()

    assert (["fips", "fmr_0", "fmr_1", "fmr_2", "fmr_3", "fmr_4"] == df.columns).all()
