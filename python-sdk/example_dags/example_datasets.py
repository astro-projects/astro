"""
You can use Datasets(introduced in Airflow 2.4) to specify data dependencies in your DAGs.
Note that in addition to scheduling DAGs based upon time,they can also be scheduled based
upon a task updating a dataset.The below example showcases this functionality
by specifying the Dataset dependency using a `schedule` parameter on the consumer DAG
This Example DAG :
 - Pulls a CSV file from Github and loads it into a Postgres table, imdb_movies.
 - Once the load_file task(the producer DAG) has completed successfully,
   Airflow schedules the transform_top_animations task(the consumer DAG) , since we
   specified the Dataset dependency on imdb_movies_table using `schedule` parameter.
 - The transform_top_animations finds the Top 5 movies based on rating, and
   loads it into another Postgres table, top_animation
Pre-requisites:
 - Install Airflow 2.4
 - Install dependencies for Astro Python SDK with Postgres, refer to README.md
 - Create an Airflow Connection to connect to Postgres Table.
"""

from datetime import datetime

from airflow import DAG

from astro import sql as aql
from astro.files import File
from astro.sql.table import Table

input_file = File(path="gs://dag-authoring/movies/imdb_v2.csv")
imdb_movies_table = Table(name="imdb_movies", conn_id="postgres_default")
top_animations_table = Table(name="top_animation", conn_id="postgres_default")
START_DATE = datetime(2000, 1, 1)


@aql.transform()
def get_top_five_animations(input_table: Table):  # skipcq: PYL-W0613
    return """
        SELECT title, rating
        FROM {{input_table}}
        WHERE genre1=='Animation'
        ORDER BY rating desc
        LIMIT 5;
    """


with DAG(
    dag_id="load_file",
    schedule_interval=None,
    start_date=START_DATE,
    catchup=False,
) as load_dag:
    imdb_movies = aql.load_file(
        input_file=File(
            path="https://raw.githubusercontent.com/astronomer/astro-sdk/main/tests/data/imdb_v2.csv"
        ),
        task_id="load_csv",
        output_table=imdb_movies_table,
    )

with DAG(
    dag_id="transform_top_animations",
    schedule=[imdb_movies_table],
    start_date=START_DATE,
    catchup=False,
) as transform_dag:
    top_five_animations = get_top_five_animations(
        input_table=imdb_movies_table,
        output_table=top_animations_table,
    )
