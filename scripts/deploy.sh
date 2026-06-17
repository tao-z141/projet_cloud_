#!/bin/bash

# =========================
# Deploy NYC Taxi Platform
# CloudFormation Stacks
# =========================

set -e

REGION="${AWS_DEFAULT_REGION:-eu-west-3}"
KEY_PAIR="${1:-my-key}"   # Passer le nom de la key pair en argument: ./deploy.sh mon-keypair

echo "========================================"
echo " NYC Taxi Platform — CloudFormation Deploy"
echo " Region: $REGION | Key: $KEY_PAIR"
echo "========================================"

# ORDRE CORRECT : Networking d'abord (exporte MainVPC, PublicSubnetId, KafkaSecurityGroupId)
# puis Storage, puis Databases (importe MainVPC), puis Kafka (importe MainVPC + SubnetId + SG), puis API

echo ""
echo "[1/5] Deploying Networking Stack..."
aws cloudformation deploy \
  --stack-name nyc-network \
  --template-file infrastructure/cloudformation/networking.yaml \
  --region "$REGION"
echo "    Networking OK"

echo ""
echo "[2/5] Deploying Storage Stack..."
aws cloudformation deploy \
  --stack-name nyc-storage \
  --template-file infrastructure/cloudformation/storage.yaml \
  --region "$REGION"
echo "    Storage OK"

echo ""
echo "[3/5] Deploying Databases Stack..."
aws cloudformation deploy \
  --stack-name nyc-db \
  --template-file infrastructure/cloudformation/databases.yaml \
  --capabilities CAPABILITY_IAM \
  --region "$REGION"
echo "    Databases OK"

echo ""
echo "[4/5] Deploying Kafka Stack..."
aws cloudformation deploy \
  --stack-name nyc-kafka \
  --template-file infrastructure/cloudformation/kafka.yaml \
  --parameter-overrides KeyPairName="$KEY_PAIR" \
  --region "$REGION"
echo "    Kafka OK"

echo ""
echo "[5/5] Deploying API Stack..."
aws cloudformation deploy \
  --stack-name nyc-api \
  --template-file infrastructure/cloudformation/api.yaml \
  --capabilities CAPABILITY_IAM \
  --region "$REGION"
echo "    API OK"

echo ""
echo "========================================"
echo " DEPLOYMENT COMPLETE"
echo "========================================"

# Afficher les outputs clés
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
