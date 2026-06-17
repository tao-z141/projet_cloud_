import sys
from pyspark.context import SparkContext
from pyspark.sql.functions import col, avg, count, sum as spark_sum, date_format
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions

# ======================
# INIT GLUE JOB
# ======================
args = getResolvedOptions(sys.argv, ["JOB_NAME"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

job = Job(glueContext)
job.init(args["JOB_NAME"], args)

BUCKET = "s3://nyc-taxi-platform"

# ======================
# READ SILVER
# ======================
print("Reading Silver taxi_clean...")
taxi = spark.read.parquet(f"{BUCKET}/silver/taxi_clean/")

print("Reading Silver weather_clean...")
weather = spark.read.parquet(f"{BUCKET}/silver/weather_clean/")

taxi.createOrReplaceTempView("taxi")
weather.createOrReplaceTempView("weather")

# ======================
# GOLD 1 — KPI journaliers
# ======================
print("Computing gold kpi_daily...")
kpi_daily = spark.sql("""
SELECT
    DATE(tpep_pickup_datetime)   AS day,
    COUNT(*)                     AS nb_trips,
    ROUND(AVG(trip_distance), 2) AS avg_distance_km,
    ROUND(AVG(fare_amount), 2)   AS avg_fare_usd,
    ROUND(SUM(fare_amount), 2)   AS total_revenue_usd,
    AVG(passenger_count)         AS avg_passengers
FROM taxi
GROUP BY DATE(tpep_pickup_datetime)
ORDER BY day
""")

# ======================
# GOLD 2 — KPI par zone (PULocationID)
# ======================
print("Computing gold kpi_zone...")
kpi_zone = spark.sql("""
SELECT
    PULocationID                 AS zone_id,
    COUNT(*)                     AS nb_trips,
    ROUND(AVG(fare_amount), 2)   AS avg_fare_usd,
    ROUND(AVG(trip_distance), 2) AS avg_distance_km,
    ROUND(SUM(fare_amount), 2)   AS total_revenue_usd
FROM taxi
GROUP BY PULocationID
ORDER BY nb_trips DESC
""")

# ======================
# GOLD 3 — Export API (top zones + journalier fusionné)
# ======================
print("Computing gold api_exports...")
api_export = spark.sql("""
SELECT
    DATE(tpep_pickup_datetime)   AS day,
    PULocationID                 AS zone_id,
    COUNT(*)                     AS nb_trips,
    ROUND(AVG(fare_amount), 2)   AS avg_fare_usd
FROM taxi
GROUP BY DATE(tpep_pickup_datetime), PULocationID
""")

# ======================
# WRITE GOLD
# ======================
print("Writing Gold kpi_daily...")
kpi_daily.write \
    .mode("overwrite") \
    .parquet(f"{BUCKET}/gold/kpi_daily/")

print("Writing Gold kpi_zone...")
kpi_zone.write \
    .mode("overwrite") \
    .parquet(f"{BUCKET}/gold/kpi_zone/")

print("Writing Gold api_exports...")
api_export.write \
    .mode("overwrite") \
    .partitionBy("day") \
    .parquet(f"{BUCKET}/gold/api_exports/")

# ======================
# QUALITY CHECKS
# ======================
daily_count = kpi_daily.count()
zone_count = kpi_zone.count()

print(f"Gold kpi_daily rows: {daily_count}")
print(f"Gold kpi_zone rows: {zone_count}")

if daily_count == 0:
    raise ValueError("QUALITY CHECK FAILED: kpi_daily is empty!")

if zone_count == 0:
    raise ValueError("QUALITY CHECK FAILED: kpi_zone is empty!")

job.commit()
print("Silver → Gold DONE")
