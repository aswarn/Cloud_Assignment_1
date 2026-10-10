import os
import boto3
import requests
from requests_aws4auth import AWS4Auth
from boto3.dynamodb.conditions import Attr

REGION = "us-east-1"
TABLE_NAME = "yelp-restaurants"
ENDPOINT = os.environ["OPENSEARCH_ENDPOINT"].rstrip("/")

credentials = boto3.Session().get_credentials().get_frozen_credentials()

auth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    "es",
    session_token=credentials.token,
)

dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

response = table.scan()
items = response.get("Items", [])

while "LastEvaluatedKey" in response:
    response = table.scan(
        ExclusiveStartKey=response["LastEvaluatedKey"]
    )
    items.extend(response.get("Items", []))

uploaded = 0

for item in items:
    restaurant_id = item.get("business_id")
    cuisines = item.get("cuisines", [])

    if not restaurant_id:
        continue

    if isinstance(cuisines, str):
        cuisines = [cuisines]

    for cuisine in cuisines:
        if not cuisine:
            continue

        document = {
            "RestaurantID": restaurant_id,
            "Cuisine": cuisine,
        }

        document_id = f"{restaurant_id}#{cuisine}"

        result = requests.put(
            f"{ENDPOINT}/restaurants/_doc/{document_id}",
            auth=auth,
            json=document,
            timeout=30,
        )
        result.raise_for_status()
        uploaded += 1

print(f"Restaurants in DynamoDB: {len(items)}")
print(f"Restaurant-cuisine documents uploaded: {uploaded}")

