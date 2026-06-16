from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session

taxi = spark.read.parquet("s3://nyc-taxi-bronze/taxi/")
weather = spark.read.json("s3://nyc-taxi-bronze/weather/")

# nettoyage basique
taxi_clean = taxi.dropna()

# write silver
taxi_clean.write.mode("overwrite").parquet(
    "s3://nyc-taxi-silver/taxi_clean/"
)

weather.write.mode("overwrite").parquet(
    "s3://nyc-taxi-silver/weather_clean/"
)

print("Bronze → Silver done")
