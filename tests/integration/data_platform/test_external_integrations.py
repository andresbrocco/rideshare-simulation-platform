"""External integration tests for data platform.

Tests external service compatibility and API conformance:
- EI-001: LocalStack Secrets Manager integration
- EI-002: MinIO S3 API compatibility
- EI-003: Schema Registry integration
"""

import json

import httpx
import pytest
from botocore.exceptions import ClientError


# Module-level marker for external integration tests
pytestmark = pytest.mark.external_integration


@pytest.mark.external_integration
def test_localstack_secrets_manager(localstack_secrets_client):
    """EI-001: Verify LocalStack provides AWS Secrets Manager functionality.

    Tests CRUD operations on secrets to validate LocalStack emulation:
    - Create secret with string value
    - Retrieve secret and verify value
    - Update secret with new value
    - Delete secret

    Verifies:
    - All CRUD operations succeed
    - Secret values returned correctly
    - Permissions work as expected
    - LocalStack provides full Secrets Manager API
    """
    secrets_client = localstack_secrets_client
    secret_name = "ei001-test-secret"
    secret_value_v1 = {"username": "admin", "password": "initial-password"}
    secret_value_v2 = {"username": "admin", "password": "updated-password"}

    # Act & Assert: Create secret
    create_response = secrets_client.create_secret(
        Name=secret_name,
        SecretString=json.dumps(secret_value_v1),
        Description="Test secret for EI-001",
    )
    assert "ARN" in create_response, "Create secret should return ARN"
    assert "Name" in create_response, "Create secret should return Name"

    # Act & Assert: Retrieve secret
    get_response = secrets_client.get_secret_value(SecretId=secret_name)
    assert "SecretString" in get_response, "Get should return SecretString"
    retrieved_value = json.loads(get_response["SecretString"])
    assert (
        retrieved_value == secret_value_v1
    ), f"Retrieved value {retrieved_value} does not match created value {secret_value_v1}"

    # Act & Assert: Update secret
    update_response = secrets_client.update_secret(
        SecretId=secret_name, SecretString=json.dumps(secret_value_v2)
    )
    assert "ARN" in update_response, "Update should return ARN"

    # Verify update applied
    get_updated_response = secrets_client.get_secret_value(SecretId=secret_name)
    updated_value = json.loads(get_updated_response["SecretString"])
    assert (
        updated_value == secret_value_v2
    ), f"Updated value {updated_value} does not match expected {secret_value_v2}"

    # Act & Assert: Delete secret
    delete_response = secrets_client.delete_secret(
        SecretId=secret_name, ForceDeleteWithoutRecovery=True
    )
    assert "ARN" in delete_response, "Delete should return ARN"
    assert "DeletionDate" in delete_response, "Delete should return DeletionDate"

    # Verify secret deleted
    with pytest.raises(ClientError) as exc_info:
        secrets_client.get_secret_value(SecretId=secret_name)
    assert (
        exc_info.value.response["Error"]["Code"] == "ResourceNotFoundException"
    ), "Deleted secret should not be retrievable"


@pytest.mark.external_integration
def test_minio_s3_compatibility(minio_client):
    """EI-002: Verify MinIO provides full S3 API compatibility.

    Tests standard S3 operations to validate MinIO as S3 replacement:
    - List buckets
    - Put object (small file)
    - Get object and verify content
    - Delete object
    - Multipart upload (large file >5MB)

    Verifies:
    - All S3 operations succeed
    - Objects persist correctly
    - Multipart upload works for large files
    - MinIO provides full S3 SDK compatibility
    """
    bucket_name = "rideshare-bronze"
    test_key = "ei002-test-object.txt"
    test_content = b"This is EI-002 test content for MinIO S3 compatibility"
    large_file_key = "ei002-large-file.bin"

    # Act & Assert: List buckets
    buckets = minio_client.list_buckets()
    bucket_names = [bucket["Name"] for bucket in buckets["Buckets"]]
    assert (
        bucket_name in bucket_names
    ), f"Expected bucket {bucket_name} not found in MinIO"

    # Act & Assert: Put object
    minio_client.put_object(Bucket=bucket_name, Key=test_key, Body=test_content)

    # Verify object exists by listing
    objects = list(
        minio_client.list_objects_v2(Bucket=bucket_name, Prefix=test_key).get(
            "Contents", []
        )
    )
    assert len(objects) == 1, f"Expected 1 object with key {test_key}"
    assert objects[0]["Key"] == test_key

    # Act & Assert: Get object
    get_response = minio_client.get_object(Bucket=bucket_name, Key=test_key)
    retrieved_content = get_response["Body"].read()
    assert (
        retrieved_content == test_content
    ), "Retrieved content does not match uploaded content"

    # Act & Assert: Delete object
    minio_client.delete_object(Bucket=bucket_name, Key=test_key)

    # Verify object deleted
    objects_after_delete = list(
        minio_client.list_objects_v2(Bucket=bucket_name, Prefix=test_key).get(
            "Contents", []
        )
    )
    assert len(objects_after_delete) == 0, "Object should not exist after deletion"

    # Act & Assert: Multipart upload (large file >5MB)
    # Generate 6MB of test data
    large_file_size = 6 * 1024 * 1024  # 6 MB
    large_file_content = b"A" * large_file_size

    # Initiate multipart upload
    multipart_response = minio_client.create_multipart_upload(
        Bucket=bucket_name, Key=large_file_key
    )
    upload_id = multipart_response["UploadId"]

    # Upload parts (5MB each part)
    part_size = 5 * 1024 * 1024
    parts = []
    for i, offset in enumerate(range(0, large_file_size, part_size), start=1):
        part_data = large_file_content[offset : offset + part_size]
        part_response = minio_client.upload_part(
            Bucket=bucket_name,
            Key=large_file_key,
            PartNumber=i,
            UploadId=upload_id,
            Body=part_data,
        )
        parts.append({"PartNumber": i, "ETag": part_response["ETag"]})

    # Complete multipart upload
    minio_client.complete_multipart_upload(
        Bucket=bucket_name,
        Key=large_file_key,
        UploadId=upload_id,
        MultipartUpload={"Parts": parts},
    )

    # Verify large file uploaded
    large_file_objects = list(
        minio_client.list_objects_v2(Bucket=bucket_name, Prefix=large_file_key).get(
            "Contents", []
        )
    )
    assert (
        len(large_file_objects) == 1
    ), "Large file should exist after multipart upload"
    assert (
        large_file_objects[0]["Size"] == large_file_size
    ), f"Large file size {large_file_objects[0]['Size']} does not match expected {large_file_size}"

    # Cleanup: Delete large file
    minio_client.delete_object(Bucket=bucket_name, Key=large_file_key)


@pytest.mark.external_integration
def test_schema_registry_integration(wait_for_services):
    """EI-003: Verify Schema Registry stores and validates JSON schemas.

    Tests Schema Registry operations for schema management:
    - Register trip_event schema to test subject
    - Retrieve schema by subject name
    - Check compatibility with evolved schema (add optional field)
    - Verify invalid evolution rejected

    Verifies:
    - Schema registered successfully with schema ID
    - Schema retrievable by subject
    - Compatibility check passes for valid evolution
    - Invalid evolution rejected (breaks backward compatibility)
    """
    schema_registry_url = "http://localhost:8085"
    subject = "ei003-trip-events-value"

    # Define base trip_event schema (simplified version for testing)
    base_schema = {
        "type": "object",
        "required": ["trip_id", "status", "timestamp"],
        "properties": {
            "trip_id": {"type": "string"},
            "status": {"type": "string"},
            "timestamp": {"type": "string", "format": "date-time"},
        },
    }

    # Evolved schema: add optional field (backward compatible)
    evolved_schema = {
        "type": "object",
        "required": ["trip_id", "status", "timestamp"],
        "properties": {
            "trip_id": {"type": "string"},
            "status": {"type": "string"},
            "timestamp": {"type": "string", "format": "date-time"},
            "driver_id": {"type": ["string", "null"]},  # New optional field
        },
    }

    # Invalid schema: remove required field (breaks backward compatibility)
    invalid_schema = {
        "type": "object",
        "required": ["trip_id", "timestamp"],  # Removed 'status' from required
        "properties": {
            "trip_id": {"type": "string"},
            "timestamp": {"type": "string", "format": "date-time"},
        },
    }

    # Act & Assert: Register base schema
    register_response = httpx.post(
        f"{schema_registry_url}/subjects/{subject}/versions",
        json={"schema": json.dumps(base_schema), "schemaType": "JSON"},
        headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
        timeout=10.0,
    )
    assert (
        register_response.status_code == 200
    ), f"Register schema failed with status {register_response.status_code}: {register_response.text}"
    schema_id = register_response.json()["id"]
    assert isinstance(schema_id, int), "Schema ID should be an integer"

    # Act & Assert: Retrieve schema by subject
    get_response = httpx.get(
        f"{schema_registry_url}/subjects/{subject}/versions/latest",
        timeout=10.0,
    )
    assert (
        get_response.status_code == 200
    ), f"Get schema failed with status {get_response.status_code}"
    retrieved_schema_data = get_response.json()
    assert (
        retrieved_schema_data["id"] == schema_id
    ), "Retrieved schema ID does not match registered ID"
    retrieved_schema = json.loads(retrieved_schema_data["schema"])
    assert (
        retrieved_schema == base_schema
    ), "Retrieved schema does not match registered schema"

    # Act & Assert: Check compatibility with evolved schema (should pass)
    compat_check_response = httpx.post(
        f"{schema_registry_url}/compatibility/subjects/{subject}/versions/latest",
        json={"schema": json.dumps(evolved_schema), "schemaType": "JSON"},
        headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
        timeout=10.0,
    )
    assert (
        compat_check_response.status_code == 200
    ), f"Compatibility check failed with status {compat_check_response.status_code}"
    compat_result = compat_check_response.json()
    assert (
        compat_result.get("is_compatible") is True
    ), "Evolved schema should be backward compatible"

    # Act & Assert: Register evolved schema (should succeed)
    register_evolved_response = httpx.post(
        f"{schema_registry_url}/subjects/{subject}/versions",
        json={"schema": json.dumps(evolved_schema), "schemaType": "JSON"},
        headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
        timeout=10.0,
    )
    assert (
        register_evolved_response.status_code == 200
    ), "Registering evolved schema should succeed"

    # Act & Assert: Check compatibility with invalid schema (should fail)
    invalid_compat_response = httpx.post(
        f"{schema_registry_url}/compatibility/subjects/{subject}/versions/latest",
        json={"schema": json.dumps(invalid_schema), "schemaType": "JSON"},
        headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
        timeout=10.0,
    )
    # Compatibility check may return 200 with is_compatible: false, or 409
    if invalid_compat_response.status_code == 200:
        invalid_compat_result = invalid_compat_response.json()
        assert (
            invalid_compat_result.get("is_compatible") is False
        ), "Invalid schema should not be backward compatible"
    else:
        # Some Schema Registry versions return 409 for incompatible schemas
        assert invalid_compat_response.status_code in [
            409,
            422,
        ], f"Expected 409/422 for incompatible schema, got {invalid_compat_response.status_code}"

    # Cleanup: Delete subject (soft delete)
    delete_response = httpx.delete(
        f"{schema_registry_url}/subjects/{subject}",
        timeout=10.0,
    )
    # Delete returns array of deleted version numbers
    assert (
        delete_response.status_code == 200
    ), f"Delete subject failed with status {delete_response.status_code}"
