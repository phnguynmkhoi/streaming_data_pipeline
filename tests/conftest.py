import os
import sys

import pytest
from pyspark.sql import SparkSession

APPS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "apps")
if APPS_DIR not in sys.path:
    sys.path.insert(0, APPS_DIR)


@pytest.fixture(scope="session")
def spark():
    session = SparkSession.builder\
        .appName("pytest-unit-tests")\
        .master("local[1]")\
        .config("spark.ui.enabled", "false")\
        .config("spark.sql.shuffle.partitions", "1")\
        .getOrCreate()
    yield session
    session.stop()
