#This is LF0
import json
import uuid
import boto3

lex = boto3.client("lexv2-runtime", region_name="us-east-1")

BOT_ID = "TOAIWWM3MG"
BOT_ALIAS_ID = "TSTALIASID"
LOCALE_ID = "en_US"


def lambda_handler(event, context):
    print("LF0_INVOKED_FROM_API_GATEWAY")
    print("Incoming event:", json.dumps(event))

    try:
        # Support both API Gateway proxy and direct event formats
        body = event.get("body")

        if isinstance(body, str):
            body = json.loads(body)

        if not isinstance(body, dict):
            body = event

        messages = body.get("messages") or []

        if not messages:
            raise ValueError("No messages provided")

        user_text = messages[-1]["unstructured"]["text"]

        session_id = (
            body.get("sessionId")
            or body.get("userId")
            or event.get("requestContext", {}).get("requestId")
            or str(uuid.uuid4())
        )

        response = lex.recognize_text(
            botId=BOT_ID,
            botAliasId=BOT_ALIAS_ID,
            localeId=LOCALE_ID,
            sessionId=str(session_id),
            text=user_text
        )

        replies = [
            {
                "type": "text",
                "unstructured": {
                    "id": str(index + 1),
                    "text": message["content"]
                }
            }
            for index, message in enumerate(response.get("messages", []))
            if message.get("contentType") == "PlainText"
        ]

        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Allow-Methods": "OPTIONS,POST",
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "messages": replies,
                "sessionId": str(session_id)
            })
        }

    except Exception as error:
        print("LF0 error:", str(error))

        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "error": str(error),
                "messages": [
                    {
                        "type": "text",
                        "unstructured": {
                            "id": "1",
                            "text": "Sorry, something went wrong."
                        }
                    }
                ]
            })
        }
