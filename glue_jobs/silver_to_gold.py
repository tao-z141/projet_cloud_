import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql.functions import (
    col, avg, count, sum as spark_sum,
    round as spark_round, to_date
)

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
taxi.createOrReplaceTempView("taxi")

print("Reading Silver weather_clean...")
weather = spark.read.parquet(f"{BUCKET}/silver/weather_clean/")
weather.createOrReplaceTempView("weather")

# ======================
# READ ZONES LOOKUP (bronze)
# Contient : LocationID, Borough, Zone, service_zone
# ======================
print("Reading Zones lookup...")
zones = spark.read.csv(
    f"{BUCKET}/bronze/zones/taxi_zone_lookup.csv",
    header=True,
    inferSchema=True
)
zones = zones.select(
    col("LocationID").alias("zone_id"),
    col("Borough").alias("borough"),
    col("Zone").alias("zone_name"),
    col("service_zone")
)
zones.createOrReplaceTempView("zones")

# ======================
# DATAMART 1 — kpi_daily (agrégat global par jour)
# ======================
print("Building kpi_daily...")
kpi_daily = spark.sql("""
    SELECT
        DATE(tpep_pickup_datetime)      AS day,
        COUNT(*)                        AS nb_trips,
        ROUND(AVG(trip_distance), 2)    AS avg_distance_km,
        ROUND(AVG(fare_amount), 2)      AS avg_fare_usd,
        ROUND(SUM(fare_amount), 2)      AS total_revenue_usd,
        ROUND(AVG(passenger_count), 2)  AS avg_passengers
    FROM taxi
    WHERE DATE(tpep_pickup_datetime) BETWEEN '2024-01-01' AND '2024-01-31'
    GROUP BY DATE(tpep_pickup_datetime)
    ORDER BY day
""")

# ======================
# DATAMART 2 — kpi_zone avec noms des zones
# Jointure taxi + zones lookup
# ======================
print("Building kpi_zone with zone names...")
kpi_zone = spark.sql("""
    SELECT
        t.PULocationID                  AS zone_id,
        z.zone_name,
        z.borough,
        z.service_zone,
        COUNT(*)                        AS nb_trips,
        ROUND(AVG(t.fare_amount), 2)    AS avg_fare_usd,
        ROUND(AVG(t.trip_distance), 2)  AS avg_distance_km,
        ROUND(SUM(t.fare_amount), 2)    AS total_revenue_usd
    FROM taxi t
    LEFT JOIN zones z ON t.PULocationID = z.zone_id
    WHERE DATE(t.tpep_pickup_datetime) BETWEEN '2024-01-01' AND '2024-01-31'
    GROUP BY t.PULocationID, z.zone_name, z.borough, z.service_zone
    ORDER BY nb_trips DESC
""")

# ======================
# DATAMART 3 — dm_performance (zone + jour + noms)
# Problématique 1 : Quels jours/zones génèrent le plus de revenus ?
# ======================
print("Building dm_performance...")
dm_performance = spark.sql("""
    SELECT
        DATE(t.tpep_pickup_datetime)    AS day,
        t.PULocationID                  AS zone_id,
        z.zone_name,
        z.borough,
        COUNT(*)                        AS nb_trips,
        ROUND(SUM(t.fare_amount), 2)    AS total_revenue_usd,
        ROUND(AVG(t.fare_amount), 2)    AS avg_fare_usd,
        ROUND(AVG(t.trip_distance), 2)  AS avg_distance_km,
        ROUND(AVG(t.passenger_count), 2) AS avg_passengers,
        ROUND(AVG(t.tip_amount), 2)     AS avg_tip_usd
    FROM taxi t
    LEFT JOIN zones z ON t.PULocationID = z.zone_id
    WHERE DATE(t.tpep_pickup_datetime) BETWEEN '2024-01-01' AND '2024-01-31'
    GROUP BY DATE(t.tpep_pickup_datetime), t.PULocationID, z.zone_name, z.borough
""")

# ======================
# DATAMART 4 — dm_weather_impact
# Problématique 2 : La météo influence-t-elle la demande de taxis ?
# ======================
print("Building dm_weather_impact...")
weather_daily = spark.sql("""
    SELECT
        date                            AS day,
        ROUND(AVG(temperature_2m), 2)   AS avg_temp_c,
        ROUND(MIN(temperature_2m), 2)   AS min_temp_c,
        ROUND(MAX(temperature_2m), 2)   AS max_temp_c,
        ROUND(SUM(precipitation), 2)    AS total_precip_mm,
        ROUND(AVG(windspeed_10m), 2)    AS avg_wind_kmh
    FROM weather
    GROUP BY date
""")
kpi_daily.createOrReplaceTempView("kpi_daily")
weather_daily.createOrReplaceTempView("weather_daily")

dm_weather_impact = spark.sql("""
    SELECT
        k.day,
        k.nb_trips,
        k.avg_fare_usd,
        k.total_revenue_usd,
        w.avg_temp_c,
        w.min_temp_c,
        w.max_temp_c,
        w.total_precip_mm,
        w.avg_wind_kmh,
        CASE
            WHEN w.total_precip_mm > 5  THEN 'Pluie forte'
            WHEN w.total_precip_mm > 0  THEN 'Pluie légère'
            ELSE 'Sec'
        END AS weather_condition,
        CASE
            WHEN w.avg_temp_c < 0   THEN 'Gel'
            WHEN w.avg_temp_c < 5   THEN 'Froid'
            WHEN w.avg_temp_c < 15  THEN 'Frais'
            ELSE 'Doux'
        END AS temp_category
    FROM kpi_daily k
    LEFT JOIN weather_daily w ON k.day = w.day
""")

# ======================
# API EXPORTS
# ======================
print("Building api_exports...")
api_export = spark.sql("""
    SELECT
        DATE(t.tpep_pickup_datetime)    AS day,
        t.PULocationID                  AS zone_id,
        z.zone_name,
        z.borough,
        COUNT(*)                        AS nb_trips,
        ROUND(AVG(t.fare_amount), 2)    AS avg_fare_usd
    FROM taxi t
    LEFT JOIN zones z ON t.PULocationID = z.zone_id
    WHERE DATE(t.tpep_pickup_datetime) BETWEEN '2024-01-01' AND '2024-01-31'
    GROUP BY DATE(t.tpep_pickup_datetime), t.PULocationID, z.zone_name, z.borough
""")

# ======================
# WRITE GOLD
# ======================
print("Writing Gold datamarts...")
kpi_daily.write.mode("overwrite").parquet(f"{BUCKET}/gold/kpi_daily/")
kpi_zone.write.mode("overwrite").parquet(f"{BUCKET}/gold/kpi_zone/")
dm_performance.write.mode("overwrite").partitionBy("day").parquet(f"{BUCKET}/gold/dm_performance/")
dm_weather_impact.write.mode("overwrite").parquet(f"{BUCKET}/gold/dm_weather_impact/")
api_export.write.mode("overwrite").partitionBy("day").parquet(f"{BUCKET}/gold/api_exports/")

# ======================
# QUALITY CHECKS
# ======================
print(f"kpi_daily: {kpi_daily.count()} rows")
print(f"kpi_zone: {kpi_zone.count()} rows")
print(f"dm_performance: {dm_performance.count()} rows")
print(f"dm_weather_impact: {dm_weather_impact.count()} rows")

job.commit()
print("Silver → Gold DONE avec noms de zones")
