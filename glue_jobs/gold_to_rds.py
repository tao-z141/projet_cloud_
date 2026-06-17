import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql.functions import col, year, month, dayofmonth, dayofweek

args = getResolvedOptions(sys.argv, ["JOB_NAME", "RDS_HOST", "RDS_PASSWORD"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

BUCKET = "s3://nyc-taxi-platform"
RDS_HOST     = args["RDS_HOST"]
RDS_PORT     = "5432"
RDS_DB       = "taxidb"
RDS_USER     = "postgres"
RDS_PASSWORD = args["RDS_PASSWORD"]

JDBC_URL = f"jdbc:postgresql://{RDS_HOST}:{RDS_PORT}/{RDS_DB}"
JDBC_PROPS = {
    "user": RDS_USER,
    "password": RDS_PASSWORD,
    "driver": "org.postgresql.Driver"
}

print(f"Connecting to RDS: {RDS_HOST}")

# ======================
# READ GOLD DATAMARTS
# ======================
kpi_daily        = spark.read.parquet(f"{BUCKET}/gold/kpi_daily/")
kpi_zone         = spark.read.parquet(f"{BUCKET}/gold/kpi_zone/")
dm_performance   = spark.read.parquet(f"{BUCKET}/gold/dm_performance/")
dm_weather_impact = spark.read.parquet(f"{BUCKET}/gold/dm_weather_impact/")

# ======================
# DIMENSION : dim_date
# ======================
dim_date = kpi_daily.select(
    col("day").alias("date_id"),
    year(col("day")).alias("year"),
    month(col("day")).alias("month"),
    dayofmonth(col("day")).alias("day_of_month"),
    dayofweek(col("day")).alias("day_of_week")
).dropDuplicates(["date_id"])

# ======================
# DIMENSION : dim_zone
# ======================
dim_zone = kpi_zone.select(
    col("zone_id"),
    col("nb_trips"),
    col("avg_fare_usd"),
    col("total_revenue_usd")
).dropDuplicates(["zone_id"])

# ======================
# DIMENSION : dim_weather
# ======================
dim_weather = dm_weather_impact.select(
    col("day").alias("date_id"),
    col("avg_temp_c"),
    col("min_temp_c"),
    col("max_temp_c"),
    col("total_precip_mm"),
    col("avg_wind_kmh"),
    col("weather_condition"),
    col("temp_category")
).dropDuplicates(["date_id"])

# ======================
# FACT TABLE : fact_trips
# ======================
fact_trips = kpi_daily.select(
    col("day").alias("date_id"),
    col("nb_trips"),
    col("avg_distance_km"),
    col("avg_fare_usd"),
    col("total_revenue_usd"),
    col("avg_passengers")
)

# ======================
# DATAMART : dm_performance (zone + jour)
# ======================
dm_perf = dm_performance.select(
    col("day"),
    col("zone_id"),
    col("nb_trips"),
    col("total_revenue_usd"),
    col("avg_fare_usd"),
    col("avg_distance_km"),
    col("avg_passengers"),
    col("avg_tip_usd")
)

# ======================
# DATAMART : dm_weather_impact
# ======================
dm_weather = dm_weather_impact.select(
    col("day"),
    col("nb_trips"),
    col("avg_fare_usd"),
    col("total_revenue_usd"),
    col("avg_temp_c"),
    col("total_precip_mm"),
    col("weather_condition"),
    col("temp_category")
)

# ======================
# WRITE TO RDS — Schéma étoile complet
# ======================
print("Writing dim_date...")
dim_date.write.mode("overwrite").jdbc(JDBC_URL, "dim_date", properties=JDBC_PROPS)

print("Writing dim_zone...")
dim_zone.write.mode("overwrite").jdbc(JDBC_URL, "dim_zone", properties=JDBC_PROPS)

print("Writing dim_weather...")
dim_weather.write.mode("overwrite").jdbc(JDBC_URL, "dim_weather", properties=JDBC_PROPS)

print("Writing fact_trips...")
fact_trips.write.mode("overwrite").jdbc(JDBC_URL, "fact_trips", properties=JDBC_PROPS)

print("Writing dm_performance...")
dm_perf.write.mode("overwrite").jdbc(JDBC_URL, "dm_performance", properties=JDBC_PROPS)

print("Writing dm_weather_impact...")
dm_weather.write.mode("overwrite").jdbc(JDBC_URL, "dm_weather_impact", properties=JDBC_PROPS)

# ======================
# QUALITY CHECKS
# ======================
print(f"fact_trips: {fact_trips.count()} rows")
print(f"dim_date: {dim_date.count()} rows")
print(f"dim_zone: {dim_zone.count()} rows")
print(f"dim_weather: {dim_weather.count()} rows")
print(f"dm_performance: {dm_perf.count()} rows")
print(f"dm_weather_impact: {dm_weather.count()} rows")

job.commit()
print("Gold → RDS DONE — Schéma étoile complet")
