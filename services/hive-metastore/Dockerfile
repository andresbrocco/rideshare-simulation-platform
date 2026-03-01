FROM apache/hive:4.0.0

USER root
ADD https://jdbc.postgresql.org/download/postgresql-42.7.4.jar /opt/hive/lib/postgresql-42.7.4.jar
RUN chmod 644 /opt/hive/lib/postgresql-42.7.4.jar

# Add hadoop-aws and AWS SDK to classpath for S3A filesystem support
# AWS SDK >= 1.12.746 required for EKS Pod Identity credential endpoint
RUN cp /opt/hadoop/share/hadoop/tools/lib/hadoop-aws-3.3.6.jar /opt/hive/lib/
ADD https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.780/aws-java-sdk-bundle-1.12.780.jar /opt/hive/lib/aws-java-sdk-bundle-1.12.780.jar
RUN chmod 644 /opt/hive/lib/aws-java-sdk-bundle-1.12.780.jar

# Install envsubst for runtime config template substitution
RUN apt-get update && apt-get install -y --no-install-recommends gettext-base \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint-wrapper.sh /entrypoint-wrapper.sh
RUN chmod +x /entrypoint-wrapper.sh
RUN chown -R hive:hive /opt/hive/conf

USER hive

ENTRYPOINT ["sh", "-c", "/entrypoint-wrapper.sh"]
