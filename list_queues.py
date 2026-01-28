#!/usr/bin/env python3
"""
Interactively list messages from one of the DST integration SQS queues.

Queues:
  1) dev-dst-integration-queue
  2) test-dst-integration-queue
  3) prod-dst-integration-queue

Behavior:
- Lists messages (no delete)
- Pretty-prints JSON bodies
- After listing, optionally prompts to PURGE queue (y/N)
"""

import boto3
import json

REGION = "us-east-1"
ACCOUNT_ID = "704208842596"

QUEUES = [
    "dev-dst-integration-queue",
    "test-dst-integration-queue",
    "prod-dst-integration-queue",
]


# ------------------------------------------------------------

def choose_queue() -> str:
    print("\nSelect queue:\n")
    for i, q in enumerate(QUEUES, start=1):
        print(f"  {i}) {q}")

    while True:
        choice = input("\nEnter number: ").strip()
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(QUEUES):
                return QUEUES[idx - 1]
        print("Invalid selection. Try again.")


def get_queue_url(sqs, queue_name: str) -> str:
    return sqs.get_queue_url(
        QueueName=queue_name,
        QueueOwnerAWSAccountId=ACCOUNT_ID
    )["QueueUrl"]


def pretty_print_body(body: str) -> None:
    try:
        obj = json.loads(body)
        print(json.dumps(obj, indent=2))
    except Exception:
        print(body)


# ------------------------------------------------------------

def list_messages(sqs, queue_url: str) -> int:
    shown = 0

    while True:
        resp = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=2,
            VisibilityTimeout=5,
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
        )

        messages = resp.get("Messages", [])
        if not messages:
            break

        for m in messages:
            shown += 1
            print(f"\nMessage #{shown}")
            print(f"MessageId : {m.get('MessageId')}")
            print("Body:")
            pretty_print_body(m.get("Body", ""))
            print(f"Attributes: {m.get('MessageAttributes')}")
            print("-" * 80)

    print(f"\nDisplayed {shown} messages")
    print("Messages were NOT deleted and will reappear shortly.")
    return shown


# ------------------------------------------------------------

def prompt_purge(sqs, queue_url: str) -> None:
    answer = input("\nDelete ALL messages in this queue? (y/N): ").strip().lower()

    if answer != "y":
        print("Leaving queue untouched.")
        return

    sqs.purge_queue(QueueUrl=queue_url)
    print("Purge initiated.")
    print("Queue will be empty within ~60 seconds.")


# ------------------------------------------------------------

def main():
    sqs = boto3.client("sqs", region_name=REGION)

    queue_name = choose_queue()
    queue_url = get_queue_url(sqs, queue_name)

    print("\nQueue Selected:", queue_name)
    print("Queue URL     :", queue_url)
    print("-" * 80)

    count = list_messages(sqs, queue_url)

    if count > 0:
        prompt_purge(sqs, queue_url)


# ------------------------------------------------------------

if __name__ == "__main__":
    main()
