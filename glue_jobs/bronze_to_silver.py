import sys
from pyspark.context import SparkContext
from pyspark.sql.functions import col, to_date, sha2, round as spark_round, posexplode
from pyspark.sql.types import DoubleType
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
# READ BRONZE WEATHER
# ======================
print("Reading Bronze weather data...")
weather_raw = spark.read.json(f"{BUCKET}/bronze/weather/")

# Afficher le schéma pour debug
print("Weather schema:")
weather_raw.printSchema()

# ======================
# PARSE WEATHER JSON (Open-Meteo format)
# Structure : { hourly: { time: [...], temperature_2m: [...], ... } }
# On utilise posexplode sur le tableau time pour avoir l'index
# puis on accède aux autres tableaux par index
# ======================
try:
    # Extraire les arrays
    weather_with_arrays = weather_raw.select(
        col("hourly.time").alias("time_arr"),
        col("hourly.temperature_2m").alias("temp_arr"),
        col("hourly.precipitation").alias("precip_arr"),
        col("hourly.windspeed_10m").alias("wind_arr"),
        col("hourly.weathercode").alias("code_arr")
    )

    # posexplode sur time pour avoir l'index
    weather_exploded = weather_with_arrays.select(
        posexplode(col("time_arr")).alias("idx", "datetime"),
        col("temp_arr"),
        col("precip_arr"),
        col("wind_arr"),
        col("code_arr")
    )

    # Récupérer les autres valeurs par index
    weather_clean = weather_exploded.select(
        col("datetime"),
        col("temp_arr").getItem(col("idx")).alias("temperature_2m"),
        col("precip_arr").getItem(col("idx")).alias("precipitation"),
        col("wind_arr").getItem(col("idx")).alias("windspeed_10m"),
        col("code_arr").getItem(col("idx")).alias("weathercode"),
        to_date(col("datetime")).alias("date")
    ).dropna()

    print(f"Weather parsed: {weather_clean.count()} rows")
    weather_clean.show(5)

except Exception as e:
    print(f"Weather parsing failed: {e}")
    print("Falling back to raw weather...")
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
