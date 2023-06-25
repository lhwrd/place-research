"""https://www.huduser.gov/portal/datasets/fmr/fmr2023/FY23_FMRs_revised.xlsx
"""
import pandas as pd
from residence_research.main import DatasetABC
from pathlib import Path

THIS_DIR = Path(__file__).parent


class FairMarketRent(DatasetABC):
    def __init__(self):
        dataset_url = (
            "https://www.huduser.gov/portal/datasets/fmr/fmr2023/FY23_FMRs_revised.xlsx"
        )
        dataset_path = THIS_DIR / "data" / "FY23_FMRs_revised.xlsx"
        super().__init__(dataset_url, dataset_path)

    def as_df(self):
        df = pd.read_excel(
            self.dataset_path,
            usecols=["fips", "fmr_0", "fmr_1", "fmr_2", "fmr_3", "fmr_4"],
        )
        df["fips"] = df["fips"].apply(lambda s: str(s).replace("99999", "").zfill(5))
        return df
