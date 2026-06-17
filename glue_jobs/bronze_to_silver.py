import sys
from pyspark.context import SparkContext
from pyspark.sql.functions import col, to_date, sha2, round as spark_round, from_json, explode, arrays_zip, lit
from pyspark.sql.types import DoubleType, ArrayType, StringType, StructType, StructField, FloatType
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions

args = getResolvedOptions(sys.argv, ["JOB_NAME"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

BUCKET = "s3://nyc-taxi-platform"

# ======================
# READ BRONZE TAXI
# ======================
print("Reading Bronze taxi data...")
taxi = spark.read.parquet(f"{BUCKET}/bronze/taxi/")

# ======================
# CLEANING TAXI
# ======================
taxi_clean = taxi.dropna(subset=[
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "PULocationID",
    "DOLocationID"
])

taxi_clean = taxi_clean.filter(
    (col("fare_amount") > 0) &
    (col("fare_amount") < 500) &
    (col("trip_distance") > 0) &
    (col("trip_distance") < 200) &
    (col("passenger_count") > 0) &
    (col("passenger_count") <= 8)
)

taxi_clean = taxi_clean.dropDuplicates()
taxi_clean = taxi_clean.withColumn("fare_amount", col("fare_amount").cast(DoubleType()))
taxi_clean = taxi_clean.withColumn("trip_distance", col("trip_distance").cast(DoubleType()))
taxi_clean = taxi_clean.withColumn("pickup_date", to_date(col("tpep_pickup_datetime")))

# RGPD — Pseudonymisation VendorID
taxi_clean = taxi_clean.withColumn(
    "vendor_pseudo", sha2(col("VendorID").cast("string"), 256)
).drop("VendorID")

# ======================
# READ BRONZE WEATHER (JSON historique Open-Meteo)
# ======================
print("Reading Bronze weather data...")
weather_raw = spark.read.json(f"{BUCKET}/bronze/weather/")

# Open-Meteo retourne un objet avec hourly.time[], hourly.temperature_2m[], etc.
# On doit "exploser" les arrays en lignes
if "hourly" in weather_raw.columns:
    weather_clean = weather_raw.select(
        explode(
            arrays_zip(
                col("hourly.time"),
                col("hourly.temperature_2m"),
                col("hourly.precipitation"),
                col("hourly.windspeed_10m"),
                col("hourly.weathercode")
            )
        ).alias("zipped")
    ).select(
        col("zipped.0").alias("datetime"),
        col("zipped.1").alias("temperature_2m"),
        col("zipped.2").alias("precipitation"),
        col("zipped.3").alias("windspeed_10m"),
        col("zipped.4").alias("weathercode")
    )
    weather_clean = weather_clean.withColumn(
        "date", to_date(col("datetime"))
    )
    weather_clean = weather_clean.dropna()
else:
    weather_clean = weather_raw.dropna()

# ======================
# WRITE SILVER
# ======================
print("Writing Silver taxi_clean...")
taxi_clean.write \
    .mode("overwrite") \
    .partitionBy("pickup_date") \
    .parquet(f"{BUCKET}/silver/taxi_clean/")

print("Writing Silver weather_clean...")
weather_clean.write \
    .mode("overwrite") \
    .parquet(f"{BUCKET}/silver/weather_clean/")

# ======================
# QUALITY CHECKS
# ======================
taxi_count = taxi_clean.count()
weather_count = weather_clean.count()
print(f"Silver taxi rows: {taxi_count}")
print(f"Silver weather rows: {weather_count}")

if taxi_count == 0:
    raise ValueError("QUALITY CHECK FAILED: taxi_clean is empty!")
if weather_count == 0:
    raise ValueError("QUALITY CHECK FAILED: weather_clean is empty!")

job.commit()
print("Bronze → Silver DONE")
