-- Thrift Server + Delta Lake ACID test
-- Run: docker exec -it rideshare-spark-thrift-server /opt/spark/bin/beeline -u jdbc:hive2://localhost:10000 -f /opt/spark-scripts/thrift-test.sql

-- Basic connectivity test
SELECT 'Thrift Server Connected!' AS message;

-- Show available databases
SHOW DATABASES;

-- Create a Delta table in S3 (MinIO)
DROP TABLE IF EXISTS thrift_test_table;
CREATE TABLE thrift_test_table (id INT, name STRING, created_at TIMESTAMP)
USING DELTA
LOCATION 's3a://rideshare-bronze/thrift-test-table';

-- Insert test data (ACID transaction)
INSERT INTO thrift_test_table VALUES
  (1, 'test_record_1', current_timestamp()),
  (2, 'test_record_2', current_timestamp()),
  (3, 'test_record_3', current_timestamp());

-- Read back the data
SELECT * FROM thrift_test_table;

-- Show table details (should show Delta format)
DESCRIBE EXTENDED thrift_test_table;

-- Verify Delta Lake features
DESCRIBE HISTORY thrift_test_table;

-- Cleanup
DROP TABLE IF EXISTS thrift_test_table;

SELECT 'Delta Lake ACID test passed!' AS result;
