from pyspark.context import SparkContext
from awsglue.context import GlueContext

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

taxi = spark.read.parquet("s3://nyc-taxi-silver/taxi_clean/")
weather = spark.read.parquet("s3://nyc-taxi-silver/weather_clean/")

taxi.createOrReplaceTempView("taxi")
weather.createOrReplaceTempView("weather")

gold = spark.sql("""
SELECT
    DATE(tpep_pickup_datetime) as day,
    COUNT(*) as nb_trips,
    AVG(trip_distance) as avg_distance
FROM taxi
GROUP BY DATE(tpep_pickup_datetime)
""")

gold.write.mode("overwrite").parquet(
    "s3://nyc-taxi-gold/trips_kpi/"
)

print("Silver → Gold done")
