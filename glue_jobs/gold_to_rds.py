import sys
from awsglue.utils import getResolvedOptions
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.context import SparkContext
from pyspark.sql.functions import col, year, month, dayofmonth, dayofweek
import boto3
import json

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
# RÉCUPÉRER LES CREDENTIALS RDS DEPUIS SECRETS MANAGER
# ======================
secrets_client = boto3.client("secretsmanager", region_name="eu-west-3")
secret = secrets_client.get_secret_value(SecretId="nyc-db-password")
creds = json.loads(secret["SecretString"])

# Récupérer l'endpoint RDS depuis les outputs CloudFormation
cf_client = boto3.client("cloudformation", region_name="eu-west-3")
stack = cf_client.describe_stacks(StackName="nyc-db")
outputs = {o["OutputKey"]: o["OutputValue"] for o in stack["Stacks"][0]["Outputs"]}

RDS_HOST = outputs["RDSEndpoint"]
RDS_PORT = outputs.get("RDSPort", "5432")
RDS_DB   = "taxidb"
RDS_USER = creds["username"]
RDS_PASS = creds["password"]

JDBC_URL = f"jdbc:postgresql://{RDS_HOST}:{RDS_PORT}/{RDS_DB}"
JDBC_PROPS = {
    "user": RDS_USER,
    "password": RDS_PASS,
    "driver": "org.postgresql.Driver"
}

# ======================
# READ GOLD
# ======================
print("Reading Gold kpi_daily...")
kpi_daily = spark.read.parquet(f"{BUCKET}/gold/kpi_daily/")

print("Reading Gold kpi_zone...")
kpi_zone = spark.read.parquet(f"{BUCKET}/gold/kpi_zone/")

print("Reading Silver taxi_clean for dimensions...")
taxi = spark.read.parquet(f"{BUCKET}/silver/taxi_clean/")

# ======================
# DIMENSION : dim_date
# ======================
print("Building dim_date...")
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
print("Building dim_zone...")
dim_zone = kpi_zone.select(
    col("zone_id"),
    col("nb_trips"),
    col("avg_fare_usd"),
    col("total_revenue_usd")
).dropDuplicates(["zone_id"])

# ======================
# FACT TABLE : fact_trips (depuis kpi_daily)
# ======================
print("Building fact_trips...")
fact_trips = kpi_daily.select(
    col("day").alias("date_id"),
    col("nb_trips"),
    col("avg_distance_km"),
    col("avg_fare_usd"),
    col("total_revenue_usd"),
    col("avg_passengers")
)

# ======================
# WRITE TO RDS PostgreSQL
# ======================
print("Writing dim_date to RDS...")
dim_date.write \
    .mode("overwrite") \
    .jdbc(JDBC_URL, "dim_date", properties=JDBC_PROPS)

print("Writing dim_zone to RDS...")
dim_zone.write \
    .mode("overwrite") \
    .jdbc(JDBC_URL, "dim_zone", properties=JDBC_PROPS)

print("Writing fact_trips to RDS...")
fact_trips.write \
    .mode("overwrite") \
    .jdbc(JDBC_URL, "fact_trips", properties=JDBC_PROPS)

# ======================
# QUALITY CHECK
# ======================
print(f"fact_trips rows: {fact_trips.count()}")
print(f"dim_date rows: {dim_date.count()}")
print(f"dim_zone rows: {dim_zone.count()}")

job.commit()
print("Gold → RDS DONE")
