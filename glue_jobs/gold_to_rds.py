import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql.functions import col, year, month, dayofmonth, dayofweek
import os

# ======================
# INIT GLUE JOB
# ======================
args = getResolvedOptions(sys.argv, [
    "JOB_NAME",
    "RDS_HOST",
    "RDS_PASSWORD"
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

job = Job(glueContext)
job.init(args["JOB_NAME"], args)

BUCKET = "s3://nyc-taxi-platform"

# Credentials passés en paramètres du job (pas via Secrets Manager)
RDS_HOST     = args["RDS_HOST"]
RDS_PORT     = "5432"
RDS_DB       = "taxidb"
RDS_USER     = "postgres"
RDS_PASSWORD = args["RDS_PASSWORD"]

print(f"Connecting to RDS: {RDS_HOST}:{RDS_PORT}/{RDS_DB}")

JDBC_URL = f"jdbc:postgresql://{RDS_HOST}:{RDS_PORT}/{RDS_DB}"
JDBC_PROPS = {
    "user": RDS_USER,
    "password": RDS_PASSWORD,
    "driver": "org.postgresql.Driver"
}

# ======================
# READ GOLD
# ======================
print("Reading Gold kpi_daily...")
kpi_daily = spark.read.parquet(f"{BUCKET}/gold/kpi_daily/")

print("Reading Gold kpi_zone...")
kpi_zone = spark.read.parquet(f"{BUCKET}/gold/kpi_zone/")

# ======================
# DIMENSIONS + FACT TABLE
# ======================
dim_date = kpi_daily.select(
    col("day").alias("date_id"),
    year(col("day")).alias("year"),
    month(col("day")).alias("month"),
    dayofmonth(col("day")).alias("day_of_month"),
    dayofweek(col("day")).alias("day_of_week")
).dropDuplicates(["date_id"])

dim_zone = kpi_zone.select(
    col("zone_id"),
    col("nb_trips"),
    col("avg_fare_usd"),
    col("total_revenue_usd")
).dropDuplicates(["zone_id"])

fact_trips = kpi_daily.select(
    col("day").alias("date_id"),
    col("nb_trips"),
    col("avg_distance_km"),
    col("avg_fare_usd"),
    col("total_revenue_usd"),
    col("avg_passengers")
)

# ======================
# WRITE TO RDS
# ======================
print("Writing dim_date...")
dim_date.write.mode("overwrite").jdbc(JDBC_URL, "dim_date", properties=JDBC_PROPS)

print("Writing dim_zone...")
dim_zone.write.mode("overwrite").jdbc(JDBC_URL, "dim_zone", properties=JDBC_PROPS)

print("Writing fact_trips...")
fact_trips.write.mode("overwrite").jdbc(JDBC_URL, "fact_trips", properties=JDBC_PROPS)

print(f"fact_trips: {fact_trips.count()} rows")
print(f"dim_date: {dim_date.count()} rows")
print(f"dim_zone: {dim_zone.count()} rows")

job.commit()
print("Gold → RDS DONE")
