#!/usr/bin/env python3
"""
Idempotent SQS bootstrapper + smoke test (VERBOSE).

- Ensures 3 standard queues exist in us-east-1.
- Ensures each queue has a resource-based policy granting a role permissions.

Important constraints addressed:
1) SQS queue policies allow max 7 actions per statement -> split into 2 statements.
2) Some "*Batch" actions are rejected in SQS queue policies -> do NOT include:
   - sqs:SendMessageBatch
   - sqs:DeleteMessageBatch
   - sqs:ChangeMessageVisibilityBatch

Smoke test for each queue:
    * Send N messages
    * Receive them
    * Delete them

Usage:
  python3 setup_and_test_sqs.py

Optional env vars:
  AWS_REGION=us-east-1
  ACCOUNT_ID=704208842596
  TEST_MESSAGES=3
"""

import json
import os
import sys
import time
import uuid
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError


# -----------------------------
# Config
# -----------------------------

REGION = os.getenv("AWS_REGION", "us-east-1")
EXPECTED_ACCOUNT_ID = os.getenv("ACCOUNT_ID", "704208842596")

QUEUE_NAMES = [
    "dev-dst-integration-queue",
    "test-dst-integration-queue",
    "prod-dst-integration-queue",
]

ROLE_NAME = "EC2-Permissions-S4-BIDL"
TEST_MESSAGES = int(os.getenv("TEST_MESSAGES", "3"))


# -----------------------------
# Logging helpers
# -----------------------------

def banner(msg: str) -> None:
    print("\n" + "=" * 80)
    print(msg)
    print("=" * 80)


def sub(msg: str) -> None:
    print(f"--> {msg}")


def die(msg: str, code: int = 1) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return code


# -----------------------------
# AWS helpers
# -----------------------------

def get_account_id(sts_client) -> str:
    return sts_client.get_caller_identity()["Account"]


def ensure_queue(sqs, name: str) -> str:
    """
    Create queue if missing and return URL. Safe to call repeatedly.
    """
    sub(f"Ensuring queue exists: {name}")
    resp = sqs.create_queue(QueueName=name)
    url = resp["QueueUrl"]
    sub(f"Queue URL: {url}")
    return url


def get_queue_attrs(sqs, url: str, names: List[str]) -> Dict[str, str]:
    resp = sqs.get_queue_attributes(QueueUrl=url, AttributeNames=names)
    return resp.get("Attributes", {})


# -----------------------------
# Policy management
# -----------------------------

def normalize_policy(policy_str: Optional[str]) -> Dict[str, Any]:
    """
    Returns a valid policy dict. If none/empty, returns an empty baseline policy.
    Refuses to proceed if policy is invalid JSON (to avoid clobbering).
    """
    if not policy_str:
        return {"Version": "2012-10-17", "Statement": []}

    try:
        obj = json.loads(policy_str)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            "Existing queue policy is not valid JSON; refusing to overwrite."
        ) from e

    if "Statement" not in obj or obj["Statement"] is None:
        obj["Statement"] = []

    if isinstance(obj["Statement"], dict):
        obj["Statement"] = [obj["Statement"]]

    if "Version" not in obj:
        obj["Version"] = "2012-10-17"

    return obj


def role_statements(queue_arn: str, role_arn: str) -> List[Dict[str, Any]]:
    """
    SQS queue policies allow max 7 actions per statement.
    Also: avoid "*Batch" actions in queue policy (AWS rejects them in practice).
    """
    return [
        {
            "Sid": "AllowEC2PermissionsS4BIDL_Send",
            "Effect": "Allow",
            "Principal": {"AWS": role_arn},
            "Action": [
                "sqs:SendMessage",
            ],
            "Resource": queue_arn,
        },
        {
            "Sid": "AllowEC2PermissionsS4BIDL_Consume",
            "Effect": "Allow",
            "Principal": {"AWS": role_arn},
            "Action": [
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage",
                "sqs:ChangeMessageVisibility",
                "sqs:GetQueueAttributes",
                "sqs:GetQueueUrl",
            ],
            "Resource": queue_arn,
        },
    ]


def upsert_policy_statement(policy: Dict[str, Any], stmt: Dict[str, Any]) -> bool:
    """
    Upsert a statement by Sid. Returns True if policy changed.
    """
    if "Statement" not in policy or policy["Statement"] is None:
        policy["Statement"] = []
    if isinstance(policy["Statement"], dict):
        policy["Statement"] = [policy["Statement"]]

    sid = stmt.get("Sid")
    changed = False
    new_statements: List[Dict[str, Any]] = []
    replaced = False

    for s in policy["Statement"]:
        if isinstance(s, dict) and s.get("Sid") == sid:
            new_statements.append(stmt)
            replaced = True
            changed = True
        else:
            new_statements.append(s)

    if not replaced:
        new_statements.append(stmt)
        changed = True

    policy["Statement"] = new_statements
    if "Version" not in policy:
        policy["Version"] = "2012-10-17"
        changed = True

    return changed


def ensure_policy(sqs, url: str, queue_arn: str, role_arn: str) -> None:
    """
    Ensures the queue policy includes our statements (Send + Consume).
    Preserves existing statements.
    """
    sub("Checking existing queue policy")
    attrs = get_queue_attrs(sqs, url, ["Policy"])
    policy = normalize_policy(attrs.get("Policy"))

    stmts = role_statements(queue_arn, role_arn)
    any_changed = False

    for stmt in stmts:
        changed = upsert_policy_statement(policy, stmt)
        any_changed = any_changed or changed

    if any_changed:
        sub("Updating queue policy (no *Batch actions; <=7 actions per statement)")
        sqs.set_queue_attributes(
            QueueUrl=url,
            Attributes={"Policy": json.dumps(policy)},
        )
        sub("Policy updated")
    else:
        sub("Policy already contains required statements")


# -----------------------------
# Smoke test
# -----------------------------

def send_messages(sqs, url: str, n: int) -> List[str]:
    sub(f"Sending {n} test messages")
    ids: List[str] = []
    run_id = str(uuid.uuid4())

    for i in range(n):
        body = f"dst-smoke-test run={run_id} idx={i} ts={int(time.time())}"
        resp = sqs.send_message(QueueUrl=url, MessageBody=body)
        mid = resp.get("MessageId", "")
        sub(f"Sent message idx={i} MessageId={mid}")
        ids.append(mid)

    sub(f"Sent {n} messages for run_id={run_id}")
    return ids


def receive_and_delete(
    sqs,
    url: str,
    expected: int,
    wait_time_seconds: int = 5,
    max_attempts: int = 10,
) -> int:
    sub("Receiving messages")
    deleted = 0
    attempts = 0

    while deleted < expected and attempts < max_attempts:
        attempts += 1
        resp = sqs.receive_message(
            QueueUrl=url,
            MaxNumberOfMessages=min(10, expected - deleted),
            WaitTimeSeconds=wait_time_seconds,
            VisibilityTimeout=30,
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
        )

        msgs = resp.get("Messages", [])
        sub(f"Attempt {attempts}/{max_attempts}: received {len(msgs)} messages")

        for m in msgs:
            mid = m.get("MessageId", "")
            sqs.delete_message(QueueUrl=url, ReceiptHandle=m["ReceiptHandle"])
            deleted += 1
            sub(f"Deleted MessageId={mid} (total_deleted={deleted})")

    return deleted


# -----------------------------
# Main
# -----------------------------

def main() -> int:
    banner("Initializing AWS Clients")

    session = boto3.Session(region_name=REGION)
    sqs = session.client("sqs")
    sts = session.client("sts")

    acct = get_account_id(sts)
    print(f"AWS Account: {acct}")
    print(f"Expected   : {EXPECTED_ACCOUNT_ID}")
    print(f"Region     : {REGION}")

    if acct != EXPECTED_ACCOUNT_ID:
        print("WARNING: Account mismatch (continuing anyway)")

    role_arn = f"arn:aws:iam::{EXPECTED_ACCOUNT_ID}:role/{ROLE_NAME}"
    print(f"Role ARN   : {role_arn}")

    banner("Ensuring Queues And Policies")

    queue_urls: Dict[str, str] = {}

    for name in QUEUE_NAMES:
        print()
        print(f"Processing queue: {name}")

        try:
            url = ensure_queue(sqs, name)
            queue_urls[name] = url

            arn = get_queue_attrs(sqs, url, ["QueueArn"]).get("QueueArn", "")
            if not arn:
                return die(f"Could not fetch QueueArn for {name} ({url})")

            sub(f"Queue ARN: {arn}")
            ensure_policy(sqs, url, arn, role_arn)

        except ClientError as e:
            return die(f"AWS error while processing {name}: {e}")
        except Exception as e:
            return die(f"Unexpected error while processing {name}: {e}")

    banner("Running Smoke Tests")

    for name, url in queue_urls.items():
        print()
        print(f"Testing queue: {name}")

        try:
            send_messages(sqs, url, TEST_MESSAGES)
            deleted = receive_and_delete(sqs, url, TEST_MESSAGES)

            if deleted == TEST_MESSAGES:
                print(f"SUCCESS: {name} passed smoke test")
            else:
                print(f"WARNING: {name} deleted {deleted}/{TEST_MESSAGES} messages")

        except ClientError as e:
            return die(f"Smoke test failed for {name}: {e}")

    banner("All Done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
