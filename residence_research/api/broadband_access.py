from pathlib import Path
from typing import Literal
import requests

class BroadbandCoverage:
    def __init__(self, shape_records: shapefile.ShapeRecords):
        self.shape_records = shape_records

    def get_coverage(self, latitude: float, longitude: float):
        shape_record = find_shape_record(self.shape_records, latitude, longitude)
        if shape_record:
            return shape_record.record.as_dict()
        else:
            return None
        
    @staticmethod
    def _get_census_details(latitude, longitude):
        base_url = 'https://geo.fcc.gov/api/census/area'

        url = f'{base_url}?lat={latitude}&lon={longitude}&format=json'
        response = requests.get(url)
        
        # Check if the API request was successful
        if response.status_code == 200:
            census_details = response.json()
            return census_details['results'][0]
        
    @classmethod
    def from_shapefile(cls, shapefile_path: str):
        sf = shapefile.Reader(shapefile_path)
        return cls(sf.shapeRecords())
    
    @classmethod
    def from_coordinates(cls, latitude, longitude, type: Literal['5G-NR', '4G-LTE']):
        census_details = cls._get_census_details(latitude, longitude)
        state_code = census_details['state_fips']
        broadband_data = Path('./broadband_data/')
        
        # Create ./broadband_data folder if it doesn't exist
        broadband_data.mkdir(parents=True, exist_ok=True)
        
        # Find the shape file for the state
        shapefiles = list(broadband_data.glob(f'bdc_{state_code}_131425_{type}*'))
        
        if len(shapefiles) == 0:
            raise ValueError(f'No shapefile found for state {state_code} and type {type}')
        
        
        return cls.from_shapefile(shapefiles[0])
    