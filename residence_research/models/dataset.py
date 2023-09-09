import os
from abc import ABC, abstractmethod

import pandas as pd
import requests
from pathlib import Path

class ResearchDataset:
    def __init__(self):
        # get geojson
        # self.df = 
        pass
    
    def add(self, dataset, weight):
        pass
    
    def remove(self, name):
        pass
    


class DatasetABC(ABC):
    """
    Abstract base class for a dataset that can be downloaded if it doesn't exist
    and transformed as needed.
    """

    def __init__(self, dataset_url: str, dataset_path: Path):
        """
        Initializes the dataset with the URL and local path.

        Args:
            dataset_url (str): The URL to download the dataset.
            dataset_path (str): The local path to save the dataset.
        """
        self.dataset_url = dataset_url
        self.dataset_path = dataset_path
        self.download_dataset()

    def download_dataset(self):
        """
        Downloads the dataset if it doesn't already exist.

        Returns:
            bool: True if the dataset is downloaded or already exists, False otherwise.
        """
        if os.path.exists(self.dataset_path):
            print("Dataset already exists. Skipping download.")
            return True

        self.dataset_path.mkdir(parents=True, exist_ok=True)
        
        try:
            response = requests.get(self.dataset_url)
            response.raise_for_status()

            with open(self.dataset_path, "wb") as file:
                file.write(response.content)

            print("Dataset downloaded successfully.")
            return True

        except requests.exceptions.RequestException as e:
            print("Error occurred while downloading the dataset:", str(e))
            return False

    @abstractmethod
    def as_df(self) -> pd.DataFrame:
        """
        Transforms the downloaded dataset as needed and returns as a pandas DataFrame.
        This method must be implemented by subclasses.
        """
        pass
