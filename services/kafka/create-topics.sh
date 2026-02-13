#!/bin/sh
set -e

BOOTSTRAP_SERVER="${KAFKA_BOOTSTRAP_SERVER:-kafka:29092}"
TOPICS_FILE="${TOPICS_CONFIG_PATH:-/etc/kafka/topics.yaml}"
COMMAND_CONFIG_ARGS=""
if [ -n "${KAFKA_COMMAND_CONFIG}" ]; then
    COMMAND_CONFIG_ARGS="--command-config ${KAFKA_COMMAND_CONFIG}"
fi

echo "Creating Kafka topics from ${TOPICS_FILE}..."

topic_name=""
topic_partitions=""
topic_replication=""

create_topic() {
    if [ -n "$topic_name" ] && [ -n "$topic_partitions" ] && [ -n "$topic_replication" ]; then
        echo "  ${topic_name} (partitions=${topic_partitions}, replication=${topic_replication})"
        kafka-topics \
            --bootstrap-server "${BOOTSTRAP_SERVER}" \
            ${COMMAND_CONFIG_ARGS} \
            --create --if-not-exists \
            --topic "${topic_name}" \
            --partitions "${topic_partitions}" \
            --replication-factor "${topic_replication}"
    fi
    topic_name=""
    topic_partitions=""
    topic_replication=""
}

while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
        "#"*|"") continue ;;
        "---") create_topic ;;
        name:*)          topic_name=$(echo "$line" | cut -d: -f2 | tr -d ' ') ;;
        partitions:*)    topic_partitions=$(echo "$line" | cut -d: -f2 | tr -d ' ') ;;
        replication_factor:*) topic_replication=$(echo "$line" | cut -d: -f2 | tr -d ' ') ;;
    esac
done < "${TOPICS_FILE}"

# Handle last entry (no trailing ---)
create_topic

echo ""
echo "Kafka topics created successfully"
kafka-topics --bootstrap-server "${BOOTSTRAP_SERVER}" ${COMMAND_CONFIG_ARGS} --list
