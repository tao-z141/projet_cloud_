from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
import sys

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

job = Job(glueContext)
job.init("bronze_to_silver", {})

# ======================
# READ BRONZE (1 BUCKET)
# ======================
taxi = spark.read.parquet("s3://nyc-taxi-platform/bronze/taxi/")
weather = spark.read.json("s3://nyc-taxi-platform/bronze/weather/")

# ======================
# CLEANING
# ======================
taxi_clean = taxi.dropna()

# ======================
# WRITE SILVER
# ======================
taxi_clean.write.mode("overwrite").parquet(
    "s3://nyc-taxi-platform/silver/taxi_clean/"
)

weather.write.mode("overwrite").parquet(
    "s3://nyc-taxi-platform/silver/weather_clean/"
)

job.commit()

print("Bronze → Silver done")
