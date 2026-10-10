#This is LF2
import os
import json
import random
import boto3
import urllib3

from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

REGION = "us-east-1"
QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/815398004115/ss22506-dining-bot-queue"
TABLE_NAME = "yelp-restaurants"
OPENSEARCH_ENDPOINT = "https://search-ss22506-bot-restaurants-xpfxklj5ikgni2d3igzbdon2cq.us-east-1.es.amazonaws.com"
SES_FROM_EMAIL = "swarnasweth@gmail.com"
NUM_RECOMMENDATIONS = 3

sqs = boto3.client("sqs", region_name=REGION)
dynamodb = boto3.resource("dynamodb", region_name=REGION)
ses = boto3.client("ses", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)
http = urllib3.PoolManager()


def opensearch_request(method, path, body=None):
    credentials = boto3.Session().get_credentials().get_frozen_credentials()
    url = f"{OPENSEARCH_ENDPOINT}{path}"

    payload = json.dumps(body) if body is not None else None

    headers = {}
    if payload is not None:
        headers["Content-Type"] = "application/json"

    request = AWSRequest(
        method=method,
        url=url,
        data=payload,
        headers=headers
    )
    SigV4Auth(credentials, "es", REGION).add_auth(request)

    response = http.request(
        method,
        url,
        body=payload.encode("utf-8") if payload is not None else None,
        headers=dict(request.headers),
        timeout=urllib3.Timeout(connect=5, read=30)
    )

    response_text = response.data.decode("utf-8")

    if response.status < 200 or response.status >= 300:
        raise RuntimeError(
            f"OpenSearch returned HTTP {response.status}: {response_text}"
        )

    return json.loads(response_text)


def find_restaurants(cuisine):
    result = opensearch_request(
        "POST",
        "/restaurants/_search",
        {
            "size": 500,
            "query": {
                "term": {
                    "Cuisine": {
                        "value": cuisine,
                        "case_insensitive": True
                    }
                }
            },
            "_source": ["RestaurantID", "Cuisine"]
        }
    )

    hits = result.get("hits", {}).get("hits", [])

    restaurant_ids = list({
        hit["_source"]["RestaurantID"]
        for hit in hits
        if hit.get("_source", {}).get("RestaurantID")
    })

    if not restaurant_ids:
        return []

    chosen_ids = random.sample(
        restaurant_ids,
        min(NUM_RECOMMENDATIONS, len(restaurant_ids))
    )

    restaurants = []

    for restaurant_id in chosen_ids:
        response = table.get_item(
            Key={"business_id": restaurant_id}
        )
        item = response.get("Item")

        if item:
            restaurants.append(item)

    return restaurants


def format_email(request_data, restaurants):
    cuisine = request_data.get("Cuisine", "your chosen cuisine")

    lines = [
        f"Here are your {cuisine} restaurant suggestions!",
        "",
        f"Location: {request_data.get('Location', 'Manhattan')}",
        f"Date: {request_data.get('Date', 'Not specified')}",
        f"Time: {request_data.get('Time', 'Not specified')}",
        f"Party size: {request_data.get('NumPeople', 'Not specified')}",
        ""
    ]

    if not restaurants:
        lines.append(
            "Sorry, we couldn't find restaurants matching that cuisine. "
            "Please try another cuisine."
        )
    else:
        for i, restaurant in enumerate(restaurants, start=1):
            lines.extend([
                f"{i}. {restaurant.get('name', 'Restaurant name unavailable')}",
                f"   Address: {restaurant.get('address', 'Not available')}",
                f"   Rating: {restaurant.get('rating', 'Not available')}",
                f"   Reviews: {restaurant.get('numberOfReviews', 'Not available')}",
                ""
            ])

    lines.extend(["Enjoy your meal!","","Dining Concierge"])

    return "\n".join(lines)


def process_message(message):
    request_data = json.loads(message["Body"])

    cuisine = request_data.get("Cuisine")
    email = request_data.get("Email")

    if not cuisine or not email:
        raise ValueError("SQS message must include Cuisine and Email.")

    restaurants = find_restaurants(cuisine)
    email_body = format_email(request_data, restaurants)

    ses.send_email(
        Source=SES_FROM_EMAIL,
        Destination={"ToAddresses": [email]},
        Message={
            "Subject": {
                "Data": f"Your {cuisine} Restaurant Suggestions",
                "Charset": "UTF-8"
            },
            "Body": {
                "Text": {
                    "Data": email_body,
                    "Charset": "UTF-8"
                }
            }
        }
    )

    sqs.delete_message(
        QueueUrl=QUEUE_URL,
        ReceiptHandle=message["ReceiptHandle"]
    )

    return "Email sent and SQS message deleted"


def lambda_handler(event, context):
    processed = 0
    failures = 0

    response = sqs.receive_message(
        QueueUrl=QUEUE_URL,
        MaxNumberOfMessages=5,
        WaitTimeSeconds=0,
        VisibilityTimeout=120
    )

    messages = response.get("Messages", [])

    for message in messages:
        try:
            result = process_message(message)
            print(result)
            processed += 1
        except Exception as exc:
            print(f"Failed to process message: {exc}")
            failures += 1

    return {
        "statusCode": 200,
        "body": json.dumps({
            "messages_received": len(messages),
            "messages_processed": processed,
            "messages_failed": failures
        })
    }

