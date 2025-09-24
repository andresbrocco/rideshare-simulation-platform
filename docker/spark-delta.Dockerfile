# Spark with Delta Lake JARs pre-installed
# Used by: spark-master, spark-worker, spark-thrift-server
# This ensures Delta Lake classes are available to all Spark components
FROM apache/spark:4.0.0-python3

USER root

# Download Delta Lake and S3A JARs at build time
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
        -o /opt/spark/jars/aws-sdk-bundle-2.24.6.jar
