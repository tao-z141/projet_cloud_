#!/bin/bash

echo "Deploying Storage Stack..."

aws cloudformation deploy \
  --stack-name nyc-storage \
  --template-file infrastructure/cloudformation/storage.yaml

echo "Deploying Database Stack..."

aws cloudformation deploy \
  --stack-name nyc-database \
  --template-file infrastructure/cloudformation/databases.yaml

echo "Deploying Kafka Stack..."

aws cloudformation deploy \
  --stack-name nyc-kafka \
  --template-file infrastructure/cloudformation/kafka.yaml \
  --parameter-overrides KeyPairName=my-key

echo "Deployment Finished"
