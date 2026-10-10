import os
import json
import boto3
import urllib3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

REGION = "us-east-1"
TABLE_NAME = "yelp-restaurants"
ENDPOINT = "https://search-ss22506-bot-restaurants-xpfxklj5ikgni2d3igzbdon2cq.us-east-1.es.amazonaws.com"

http = urllib3.PoolManager()
table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE_NAME)


def signed_request(method, url, body, content_type):
    credentials = boto3.Session().get_credentials().get_frozen_credentials()

    request = AWSRequest(
        method=method,
        url=url,
        data=body,
        headers={"Content-Type": content_type}
    )

    SigV4Auth(credentials, "es", REGION).add_auth(request)

    response = http.request(
        method,
        url,
        body=body.encode("utf-8"),
        headers=dict(request.headers),
        timeout=urllib3.Timeout(connect=5, read=30)
    )

    return response.status, response.data.decode("utf-8")


def lambda_handler(event, context):
    uploaded = 0
    response = table.scan()

    while True:
        for item in response.get("Items", []):
            restaurant_id = item.get("business_id")
            cuisines = item.get("cuisines", [])

            if not restaurant_id:
                continue

            if isinstance(cuisines, str):
                cuisines = [cuisines]

            lines = []

            for cuisine in cuisines:
                if not cuisine:
                    continue

                doc_id = f"{restaurant_id}#{cuisine}"

                lines.append(json.dumps({
                    "index": {
                        "_index": "restaurants",
                        "_id": doc_id
                    }
                }))
                lines.append(json.dumps({
                    "RestaurantID": restaurant_id,
                    "Cuisine": cuisine
                }))
                uploaded += 1

            # Send this restaurant's cuisine documents in one request.
            if lines:
                body = "\n".join(lines) + "\n"

                status, result = signed_request(
                    "POST",
                    f"{ENDPOINT}/_bulk",
                    body,
                    "application/x-ndjson"
                )

                if status not in (200, 201):
                    raise RuntimeError(
                        f"OpenSearch bulk request failed: {status} {result}"
                    )

                bulk_result = json.loads(result)

                if bulk_result.get("errors"):
                    failures = [
                        entry for entry in bulk_result["items"]
                        if entry.get("index", {}).get("error")
                    ]
                    raise RuntimeError(
                        f"Some documents failed: {json.dumps(failures[:3])}"
                    )

        if "LastEvaluatedKey" not in response:
            break

        response = table.scan(
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "OpenSearch ingestion completed",
            "restaurant_cuisine_documents": uploaded
        })
    }

