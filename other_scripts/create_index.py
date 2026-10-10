#Lambda to create index
import os
import json
import boto3
import urllib3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

REGION = "us-east-1"
ENDPOINT = "https://search-ss22506-bot-restaurants-xpfxklj5ikgni2d3igzbdon2cq.us-east-1.es.amazonaws.com"

http = urllib3.PoolManager()
def lambda_handler(event, context):
    url = f"{ENDPOINT}/restaurants"

    mapping = {
        "mappings": {
            "properties": {
                "RestaurantID": {"type": "keyword"},
                "Cuisine": {"type": "keyword"}
            }
        }
    }

    session = boto3.Session()
    credentials = session.get_credentials().get_frozen_credentials()

    body = json.dumps(mapping)

    request = AWSRequest(
        method="PUT",
        url=url,
        data=body,
        headers={"Content-Type": "application/json"}
    )

    SigV4Auth(
        credentials,
        "es",
        REGION
    ).add_auth(request)

    response = http.request(
        "PUT",
        url,
        body=body.encode("utf-8"),
        headers=dict(request.headers),
        timeout=urllib3.Timeout(connect=5, read=30)
    )

    result = response.data.decode("utf-8")

    if response.status == 200:
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "restaurants index created successfully",
                "result": result
            })
        }

    if response.status == 201:
        return {
            "statusCode": 201,
            "body": json.dumps({
                "message": "restaurants index created successfully",
                "result": result
            })
        }

    return {
        "statusCode": response.status,
        "body": json.dumps({
            "message": "Failed to create index",
            "details": result
        })
    }
