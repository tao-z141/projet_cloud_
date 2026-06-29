#!/bin/bash
set -e

REGION="${AWS_DEFAULT_REGION:-eu-west-3}"
KEY_PAIR="${1:-nyc-taxi-key}"

echo "========================================"
echo " NYC Taxi Platform — CloudFormation Deploy (6 stacks)"
echo " Region: $REGION | Key: $KEY_PAIR"
echo "========================================"

echo ""
echo "[1/6] Deploying Networking Stack..."
aws cloudformation deploy \
  --stack-name nyc-network \
  --template-file infrastructure/cloudformation/networking.yaml \
  --region "$REGION"
echo "    Networking OK"

echo ""
echo "[2/6] Deploying Storage Stack..."
aws cloudformation deploy \
  --stack-name nyc-storage \
  --template-file infrastructure/cloudformation/storage.yaml \
  --region "$REGION"
echo "    Storage OK"

echo ""
echo "[3/6] Deploying Databases Stack..."
aws cloudformation deploy \
  --stack-name nyc-db \
  --template-file infrastructure/cloudformation/databases.yaml \
  --capabilities CAPABILITY_IAM \
  --region "$REGION"
echo "    Databases OK"

echo ""
echo "[4/6] Deploying Kafka Stack..."
aws cloudformation deploy \
  --stack-name nyc-kafka \
  --template-file infrastructure/cloudformation/kafka.yaml \
  --parameter-overrides KeyPairName="$KEY_PAIR" \
  --region "$REGION"
echo "    Kafka OK"

echo ""
echo "[5/6] Deploying API Stack..."
aws cloudformation deploy \
  --stack-name nyc-api \
  --template-file infrastructure/cloudformation/api.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION"
echo "    API OK"

echo ""
echo "[6/6] Deploying Orchestration Stack (Step Functions + EventBridge)..."
aws cloudformation deploy \
  --stack-name nyc-orchestration \
  --template-file infrastructure/cloudformation/orchestration.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION"
echo "    Orchestration OK"

echo ""
echo "========================================"
echo " DEPLOYMENT COMPLETE"
echo "========================================"

echo ""
echo "--- Stack Outputs ---"
aws cloudformation describe-stacks \
  --stack-name nyc-kafka \
  --region "$REGION" \
  --query "Stacks[0].Outputs" \
  --output table 2>/dev/null || true

aws cloudformation describe-stacks \
  --stack-name nyc-db \
  --region "$REGION" \
  --query "Stacks[0].Outputs" \
  --output table 2>/dev/null || true

echo ""
echo "Tip: Update KAFKA_BROKER in streaming/kafka_producer.py and streaming/kafka_consumer.py"
echo "     with the KafkaPublicIP shown above."
