import json
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("realtime_events")

def lambda_handler(event, context):

    response = table.scan()

    items = response.get("Items", [])

    return {
        "statusCode": 200,
        "body": json.dumps({
            "events_count": len(items),
            "data": items[:10]
        })
    }
