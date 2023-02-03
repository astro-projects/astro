import os
from datetime import datetime, timedelta

import pandas as pd

# Uses data from https://www.kaggle.com/c/shelter-animal-outcomes
from airflow.decorators import dag

from astro import sql as aql
from astro.files import File
from astro.table import Table

DUCKDB_CONN_ID = "duckdb_default"
AWS_CONN_ID = "aws_default"


@aql.transform()
def filter_data(input_table: Table):
    return """SELECT *
    FROM {{input_table}} WHERE type NOT LIKE 'Guinea Pig'
    """


@aql.dataframe()
def aggregate_data(df: pd.DataFrame):
    new_df = df.pivot_table(index="DATE", values="NAME", columns=["TYPE"], aggfunc="count").reset_index()
    new_df.columns = new_df.columns.str.lower()
    return new_df


@dag(
    start_date=datetime(2021, 1, 1),
    max_active_runs=1,
    schedule_interval=None,
    default_args={
        "email_on_failure": False,
        "retries": 0,
        "retry_delay": timedelta(minutes=5),
    },
    catchup=False,
)
def example_duckdb_load_transform_dataframe_and_save():
    adoption_center_data = aql.load_file(
        input_file=File("s3://tmp9/ADOPTION_CENTER_2_unquoted.csv", conn_id=AWS_CONN_ID),
        task_id="adoption_center_data",
        output_table=Table(conn_id="duckdb_default"),
    )

    filtered_dataframe = filter_data(
        adoption_center_data,
    )

    aggregated_dataframe = aggregate_data(
        filtered_dataframe,
        output_table=Table(conn_id="duckdb_default"),
    )

    s3_bucket = os.getenv("GCS_BUCKET", "s3://astro-sdk")
    aql.export_to_file(
        task_id="save_file_to_gcs",
        input_data=aggregated_dataframe,
        output_file=File(
            path=f"{s3_bucket}/{{{{ task_instance_key_str }}}}/aggregated_data_duckdb.csv",
            conn_id="aws_default",
        ),
        if_exists="replace",
    )

    aql.cleanup()


dag = example_duckdb_load_transform_dataframe_and_save()
