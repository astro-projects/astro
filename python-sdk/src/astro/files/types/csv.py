from __future__ import annotations

import io

import pandas as pd

from typing import Optional
from astro.constants import FileType as FileTypeConstants
from astro.dataframes.load_options import PandasLoadOptions
from astro.dataframes.pandas import PandasDataframe
from astro.dataframes.load_options import CsvLoadOption
from astro.files.types.base import FileType
from astro.options import LoadOptions
from astro.utils.dataframe import convert_columns_names_capitalization
from astro.options import LoadOptionsList


class CSVFileType(FileType):
    """Concrete implementation to handle CSV file type"""

    # We need skipcq because it's a method overloading so we don't want to make it a static method
    def export_to_dataframe(
        self,
        stream,
        load_options: LoadOptions | PandasLoadOptions | None = None,
        columns_names_capitalization="original",
        **kwargs,
    ) -> pd.DataFrame:  # skipcq PYL-R0201
        """read csv file from one of the supported locations and return dataframe

        :param stream: file stream object
        :param load_options: Pandas option to pass to the Pandas lib while reading csv
        :param columns_names_capitalization: determines whether to convert all columns to lowercase/uppercase
            in the resulting dataframe
        """
        if isinstance(load_options, PandasLoadOptions):
            kwargs.update(load_options.to_dict())
        df = pd.read_csv(stream, **kwargs)
        df = convert_columns_names_capitalization(
            df=df, columns_names_capitalization=columns_names_capitalization
        )
        return PandasDataframe.from_pandas_df(df)

    # We need skipcq because it's a method overloading so we don't want to make it a static method
    def create_from_dataframe(self, df: pd.DataFrame, stream: io.TextIOWrapper) -> None:  # skipcq PYL-R0201
        """Write csv file to one of the supported locations

        :param df: pandas dataframe
        :param stream: file stream object
        """
        df.to_csv(stream, index=False)

    @staticmethod
    def get_options(load_option_list: LoadOptionsList) -> Optional[CsvLoadOption]:
        """
        Get CsvLoadOption
        :param load_option_list:
        """
        return load_option_list.get("CsvLoadOption")

    @property
    def name(self):
        return FileTypeConstants.CSV
