FROM apache/hive:4.0.0

USER root
ADD https://jdbc.postgresql.org/download/postgresql-42.7.4.jar /opt/hive/lib/postgresql-42.7.4.jar
RUN chmod 644 /opt/hive/lib/postgresql-42.7.4.jar

# Add hadoop-aws and AWS SDK to classpath for S3A filesystem support
RUN cp /opt/hadoop/share/hadoop/tools/lib/hadoop-aws-3.3.6.jar /opt/hive/lib/ \
    && cp /opt/hadoop/share/hadoop/tools/lib/aws-java-sdk-bundle-1.12.367.jar /opt/hive/lib/

USER hive
