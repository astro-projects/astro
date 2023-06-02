import os
from datetime import datetime
from io import StringIO
from typing import List

import airflow
import pandas as pd
import requests
from airflow import DAG

from astro import sql as aql

START_DATE = datetime(2000, 1, 1)

"""
This DAG means to serve as an example of how you can use the @aql.dataframe decorator to create custom
API hooks. By requesting the expected data and returning it as a dataframe, our results can now easily pass into
@task or @aql.transform tasks.
"""

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": 0,
}
# We need deserialization classes for airflow 2.5 with the value where as 2.2.5 we don't need it.
if airflow.__version__ == "2.2.5":
    ALLOWED_DESERIALIZATION_CLASSES = os.getenv("AIRFLOW__CORE__ALLOWED_DESERIALIZATION_CLASSES")
else:
    ALLOWED_DESERIALIZATION_CLASSES = os.getenv(
        "AIRFLOW__CORE__ALLOWED_DESERIALIZATION_CLASSES", default="airflow\\.* astro\\.*"
    )


def _load_covid_data():
    raw_data = requests.get("https://data.covid19india.org/csv/latest/case_time_series.csv")
    str_reader = StringIO()
    str_reader.write(raw_data.text)
    str_reader.seek(0)
    return pd.read_csv(str_reader)


# [START dataframe_api]
@aql.dataframe(columns_names_capitalization="original")
def load_and_group_covid_data():
    """
    Loads data from a COVID data REST API and then groups values based on the months.
    :return: A list of dataframes for each month of the pandemic
    """
    covid_df = _load_covid_data()
    covid_df["Date_YMD"] = covid_df["Date_YMD"].apply(lambda d: datetime.strptime(d, "%Y-%m-%d"))
    return [x for _, x in covid_df.groupby(covid_df.Date_YMD.dt.month)]


@aql.dataframe(columns_names_capitalization="original")
def find_worst_covid_month(dfs: List[pd.DataFrame]):
    """
    Takes a list of dataframes and then finds the month with the worst covid outbreak
    :param dfs: a list of DFs containing COVID data
    """
    res = {}
    for covid_month_data in dfs:
        if ALLOWED_DESERIALIZATION_CLASSES == "airflow\\.* astro\\.*":
            covid_month = datetime.fromtimestamp(covid_month_data.Date_YMD.iloc[0] / 1e3).strftime("%Y-%m")
        else:
            covid_month = covid_month_data.Date_YMD.iloc[0].__format__("%Y-%m")
        num_deceased = covid_month_data["Daily Deceased"].sum()
        res[covid_month] = num_deceased
        print(f"Found {num_deceased} dead for month {covid_month}")
    max_dead_month = max(res, key=res.get)  # type: ignore
    print(f"The worst month was {max_dead_month} with {res[max_dead_month]} dead")


with DAG(
    "example_dataframe",
    schedule_interval=None,
    start_date=START_DATE,
    catchup=False,
    default_args=default_args,
) as dag:
    covid_data = load_and_group_covid_data()
    find_worst_covid_month(covid_data)
# [END dataframe_api]
