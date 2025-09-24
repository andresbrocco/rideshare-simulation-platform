"""Test Delta Lake read/write operations against MinIO."""

from pyspark.sql import SparkSession

spark = (
    SparkSession.builder.appName("MinIO-Delta-Test")
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
    .config(
        "spark.sql.catalog.spark_catalog",
        "org.apache.spark.sql.delta.catalog.DeltaCatalog",
    )
    # S3A configuration for MinIO
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin")
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin")
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    # Use simple auth provider to avoid AWS SDK credential chain
    .config(
        "spark.hadoop.fs.s3a.aws.credentials.provider",
        "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
    )
    .getOrCreate()
)

data = [("test1", 1), ("test2", 2), ("test3", 3)]
df = spark.createDataFrame(data, ["name", "value"])

delta_path = "s3a://rideshare-bronze/test-delta-table"
print(f"Writing Delta table to {delta_path}...")
df.write.format("delta").mode("overwrite").save(delta_path)

print("Reading Delta table back...")
df_read = spark.read.format("delta").load(delta_path)
df_read.show()

print("SUCCESS: Delta Lake read/write to MinIO works!")
spark.stop()
