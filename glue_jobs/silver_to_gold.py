from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

job = Job(glueContext)
job.init("silver_to_gold", {})

# ======================
# READ SILVER
# ======================
taxi = spark.read.parquet("s3://nyc-taxi-platform/silver/taxi_clean/")
weather = spark.read.parquet("s3://nyc-taxi-platform/silver/weather_clean/")

taxi.createOrReplaceTempView("taxi")

# ======================
# GOLD KPI
# ======================
gold = spark.sql("""
SELECT
    DATE(tpep_pickup_datetime) as day,
    COUNT(*) as nb_trips,
    AVG(trip_distance) as avg_distance,
    AVG(fare_amount) as avg_fare
FROM taxi
GROUP BY DATE(tpep_pickup_datetime)
""")

# ======================
# WRITE GOLD
# ======================
gold.write.mode("overwrite").parquet(
    "s3://nyc-taxi-platform/gold/trips_kpi/"
)

job.commit()

print("Silver → Gold done")
