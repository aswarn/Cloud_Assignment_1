#This is LF1 code hook
import json
import boto3

sqs = boto3.client("sqs", region_name="us-east-1")

QUEUE_URL = (
    "https://sqs.us-east-1.amazonaws.com/"
    "815398004115/ss22506-dining-bot-queue"
)


def get_slot_value(slots, slot_name):
    slot = slots.get(slot_name)

    if not slot:
        return None

    value = slot.get("value") or {}
    return value.get("interpretedValue") or value.get("originalValue")


def close_response(intent, message, state="Fulfilled"):
    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": {
                **intent,
                "state": state
            }
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": message
            }
        ]
    }


def lambda_handler(event, context):
    print("Debug")
    print("FULL EVENT:", json.dumps(event))
    session_state = event["sessionState"]
    intent = session_state["intent"]
    intent_name = intent["name"]
    slots = intent.get("slots") or {}
    invocation_source = event.get("invocationSource")

    # Handle slot validation during the conversation.
    if invocation_source == "DialogCodeHook":
        location = get_slot_value(slots, "Location")

        if location:
            normalized = location.strip().lower()

            accepted_locations = {
                "manhattan",
                "new york city",
                "nyc",
                "new york"
            }

            if normalized not in accepted_locations:
                # Clear the invalid slot so Lex can ask again.
                slots["Location"] = None
                intent["slots"] = slots

                return {
                    "sessionState": {
                        **session_state,
                        "intent": intent,
                        "dialogAction": {
                            "type": "ElicitSlot",
                            "slotToElicit": "Location"
                        }
                    },
                    "messages": [
                        {
                            "contentType": "PlainText",
                            "content": (
                                "Sorry, please enter a valid location (e.g. Manhattan)."
                            )
                        }
                    ]
                }

        # Let Lex continue collecting the remaining slots.
        return {
            "sessionState": {
                **session_state,
                "intent": intent,
                "dialogAction": {"type": "Delegate"}
            }
        }

    # Handle the completed request.
    if invocation_source == "FulfillmentCodeHook":
        if intent_name == "GreetingIntent":
            return close_response(intent, "Hi there, how can I help?")

        if intent_name == "ThankYouIntent":
            return close_response(intent, "You're welcome!")

        if intent_name == "DiningSuggestionsIntent":
            request_data = {
                "Location": get_slot_value(slots, "Location"),
                "Cuisine": get_slot_value(slots, "Cuisine"),
                "NumPeople": get_slot_value(slots, "NumPeople"),
                "Date": get_slot_value(slots, "Date"),
                "Time": get_slot_value(slots, "Time"),
                "Email": get_slot_value(slots, "Email")
            }
            required_fields = ["Location", "Cuisine", "Date","Time", "NumPeople", "Email"]

            missing = [
                field for field in required_fields
                if not request_data.get(field)
            ]

            if missing:
                print("Cannot fulfill request; missing:", missing)
                return close_response(
                        intent,
                        "Some dining details are missing. Please try again.",
                        state="Failed"
                    )

            # Send one complete request to SQS.
            response=sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps(request_data)
            )
            print("SQS MessageId:", response["MessageId"])
            print("SQS HTTP status:",response["ResponseMetadata"]["HTTPStatusCode"])
            return close_response(
                intent,
                "You're all set! I'll email you restaurant "
                "suggestions shortly. Have a good day."
            )
    print("No fulfillment branch matched.")
    print("Invocation source:", invocation_source)
         
    return close_response(
        intent,
        "Sorry, I couldn't process that request. Please try again.",
        state="Failed"
    )
     
