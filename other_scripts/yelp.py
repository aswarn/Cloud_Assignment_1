
import os
import json
import time
from datetime import datetime, timezone
from decimal import Decimal

import boto3
import requests
from botocore.exceptions import ClientError

API_KEY = os.environ["YELP_API_KEY"]
REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
TABLE_NAME = "yelp-restaurants"

SEARCH_URL = "https://api.yelp.com/v3/businesses/search"
HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# Five cuisine types required by the assignment.
CUISINES = [
    "Japanese",
    "Chinese",
    "Italian",
    "Indian",
    "Mexican",
    "Thai",
    "Korean",
    "Vietnamese",
    "French",
    "Mediterranean",
    "Spanish",
    "Greek",
    "American",
    "Middle Eastern",
]

# Yelp documents a maximum of 240 results per search.
PAGE_SIZE = 50
MAX_RESULTS_PER_SEARCH = 240

session = requests.Session()
session.headers.update(HEADERS)

restaurants = {}



def search_yelp(cuisine):
    """Collect one cuisine's search results with pagination."""
    found = 0

    for offset in range(0, MAX_RESULTS_PER_SEARCH, PAGE_SIZE):
        limit = min(PAGE_SIZE, MAX_RESULTS_PER_SEARCH - offset)

        params = {
            "term": f"{cuisine} restaurants",
            "location": "Manhattan, New York, NY",
            "limit": limit,
            "offset": offset,
            "sort_by": "best_match",
        }

        response = session.get(
            SEARCH_URL,
            params=params,
            timeout=30,
        )

        if response.status_code == 429:
            print("Yelp rate limit reached. Try again later.")
            break

        response.raise_for_status()
        data = response.json()
        businesses = data.get("businesses", [])

        if not businesses:
            break

        for business in businesses:
            business_id = business.get("id")

            if not business_id:
                continue

            categories = business.get("categories", [])
            cuisine_tag = cuisine

            location = business.get("location", {})
            coordinates = business.get("coordinates", {})

            zip_code = location.get("zip_code", "")

            if business_id not in restaurants:
                restaurants[business_id] = {
                    "business_id": business_id,
                    "name": business.get("name", ""),
                    "address": ", ".join(
                        location.get("display_address", [])
                    ),
                    "coordinates": {
                        "latitude": Decimal(str(
                            coordinates.get("latitude", 0)
                        )),
                        "longitude": Decimal(str(
                            coordinates.get("longitude", 0)
                        )),
                    },
                    "numberOfReviews": business.get(
                        "review_count", 0
                    ),
                    "rating": Decimal(str(
                        business.get("rating", 0)
                    )),
                    "zipCode": zip_code,
                    "cuisines": [cuisine_tag],
                    "yelpCategories": [
                        c.get("title", "") for c in categories
                    ],
                    "insertedAtTimestamp": datetime.now(
                        timezone.utc
                    ).isoformat(),
                }
            elif cuisine_tag not in restaurants[business_id]["cuisines"]:
                restaurants[business_id]["cuisines"].append(
                    cuisine_tag
                )

            found += 1

        print(
            f"{cuisine}: fetched page at offset {offset}; "
            f"{len(businesses)} returned"
        )

        if len(businesses) < limit:
            break

        time.sleep(0.2)

    print(f"{cuisine}: {found} results processed")




def main():
    for cuisine in CUISINES:
        try:
            search_yelp(cuisine)
        except requests.RequestException as exc:
            print(f"Search failed for {cuisine}: {exc}")
            raise

    print(f"\nUnique Manhattan restaurants: {len(restaurants)}")

    # Save locally
    with open("yelp_restaurants.json", "w") as file:
        json.dump(
            list(restaurants.values()),
            file,
            indent=2,
            default=str,
        )

    print("Saved yelp_restaurants.json")

    if len(restaurants) < 1000:
        print(
            "WARNING: Fewer than 1,000 unique restaurants. "
            "Try additional cuisine terms or searches over "
            "different Manhattan areas, then deduplicate again."
        )

    # Step 2: Upload the collected data to DynamoDB.
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=REGION,
    )
    table = dynamodb.Table("yelp-restaurants")

    table.load()

    with table.batch_writer() as batch:
        for item in restaurants.values():
            batch.put_item(Item=item)

    print(f"Uploaded {len(restaurants)} unique items to {TABLE_NAME}")


if __name__ == "__main__":
    main()