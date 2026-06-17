import sys
from pyspark.context import SparkContext
from pyspark.sql.functions import col, to_date, sha2, round as spark_round
from pyspark.sql.types import DoubleType
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
# READ BRONZE
# ======================
print("Reading Bronze taxi data...")
taxi = spark.read.parquet(f"{BUCKET}/bronze/taxi/")

print("Reading Bronze weather data...")
weather = spark.read.json(f"{BUCKET}/bronze/weather/")

# ======================
# CLEANING TAXI
# ======================
print("Cleaning taxi data...")

# Supprimer lignes nulles sur colonnes critiques
taxi_clean = taxi.dropna(subset=[
    "tpep_pickup_datetime",
    "tpep_dropoff_datetime",
    "PULocationID",
    "DOLocationID"
])

# Filtrer valeurs aberrantes
taxi_clean = taxi_clean.filter(
    (col("fare_amount") > 0) &
    (col("fare_amount") < 500) &
    (col("trip_distance") > 0) &
    (col("trip_distance") < 200) &
    (col("passenger_count") > 0) &
    (col("passenger_count") <= 8)
)

# Dédoublonnage
taxi_clean = taxi_clean.dropDuplicates()

# Typage
taxi_clean = taxi_clean.withColumn("fare_amount", col("fare_amount").cast(DoubleType()))
taxi_clean = taxi_clean.withColumn("trip_distance", col("trip_distance").cast(DoubleType()))

# Ajout colonne de partition date
taxi_clean = taxi_clean.withColumn(
    "pickup_date", to_date(col("tpep_pickup_datetime"))
)

# ======================
# RGPD — Anonymisation
# ======================
# Généralisation GPS : arrondir à 2 décimales (~1km de précision)
# Les coordonnées précises sont des données de localisation (RGPD art. 4)
if "pickup_longitude" in taxi_clean.columns:
    taxi_clean = taxi_clean \
        .withColumn("pickup_latitude", spark_round(col("pickup_latitude"), 2)) \
        .withColumn("pickup_longitude", spark_round(col("pickup_longitude"), 2)) \
        .withColumn("dropoff_latitude", spark_round(col("dropoff_latitude"), 2)) \
        .withColumn("dropoff_longitude", spark_round(col("dropoff_longitude"), 2))

# Pseudonymisation du VendorID (identifiant opérateur)
taxi_clean = taxi_clean.withColumn(
    "vendor_pseudo", sha2(col("VendorID").cast("string"), 256)
).drop("VendorID")

# ======================
# CLEANING WEATHER
# ======================
print("Cleaning weather data...")
weather_clean = weather.dropna()
weather_clean = weather_clean.dropDuplicates()

# ======================
# JOINTURE taxi + weather (silver enrichi)
# ======================
# (La jointure complète nécessite un timestamp commun — ici on prépare les données)
# La jointure taxi_weather sera réalisée en gold

# ======================
# WRITE SILVER (partitionné par date)
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
    raise ValueError("QUALITY CHECK FAILED: taxi_clean is empty after cleaning!")

if weather_count == 0:
    raise ValueError("QUALITY CHECK FAILED: weather_clean is empty after cleaning!")

job.commit()
print("Bronze → Silver DONE")
