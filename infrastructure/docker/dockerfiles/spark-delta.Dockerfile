# Spark with Delta Lake JARs pre-installed
# Used by: spark-master, spark-worker, spark-thrift-server
# This ensures Delta Lake classes are available to all Spark components
FROM apache/spark:4.0.0-python3

USER root

# Download Delta Lake, S3A, and Kafka connector JARs at build time
# These must be in /opt/spark/jars/ to be on the classpath for all sessions
RUN curl -sL https://repo1.maven.org/maven2/io/delta/delta-spark_2.13/4.0.0/delta-spark_2.13-4.0.0.jar \
        -o /opt/spark/jars/delta-spark_2.13-4.0.0.jar && \
    curl -sL https://repo1.maven.org/maven2/io/delta/delta-storage/4.0.0/delta-storage-4.0.0.jar \
        -o /opt/spark/jars/delta-storage-4.0.0.jar && \
    curl -sL https://repo1.maven.org/maven2/org/antlr/antlr4-runtime/4.9.3/antlr4-runtime-4.9.3.jar \
        -o /opt/spark/jars/antlr4-runtime-4.9.3.jar && \
    curl -sL https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.4.1/hadoop-aws-3.4.1.jar \
        -o /opt/spark/jars/hadoop-aws-3.4.1.jar && \
    curl -sL https://repo1.maven.org/maven2/software/amazon/awssdk/bundle/2.24.6/bundle-2.24.6.jar \
        -o /opt/spark/jars/aws-sdk-bundle-2.24.6.jar && \
    curl -sL https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.13/4.0.0/spark-sql-kafka-0-10_2.13-4.0.0.jar \
        -o /opt/spark/jars/spark-sql-kafka-0-10_2.13-4.0.0.jar && \
    curl -sL https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.13/4.0.0/spark-token-provider-kafka-0-10_2.13-4.0.0.jar \
        -o /opt/spark/jars/spark-token-provider-kafka-0-10_2.13-4.0.0.jar && \
    curl -sL https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.9.0/kafka-clients-3.9.0.jar \
        -o /opt/spark/jars/kafka-clients-3.9.0.jar && \
    curl -sL https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.12.0/commons-pool2-2.12.0.jar \
        -o /opt/spark/jars/commons-pool2-2.12.0.jar

# Install Python dependencies for Delta Lake Python API
RUN pip install --no-cache-dir delta-spark==4.0.0
