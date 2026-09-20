from __future__ import annotations

from itertools import cycle

from jev_bench.models import BenchmarkCase, QuestionSpec

ROUTING_CRITERIA = {
    "billing": "Charges, invoices, refunds, subscriptions, or payment issues.",
    "technical": "Bugs, outages, integrations, authentication, or product malfunction.",
    "sales": "Pricing, plans, procurement, demos, or purchase questions.",
    "account": "Account profile, access ownership, or account administration.",
    "shipping": "Delivery, tracking, address, or physical shipment issues.",
    "cancellation": "Requests to cancel or close a service/order.",
}


def routing_questions() -> list[QuestionSpec]:
    return [
        QuestionSpec(
            id="department",
            type="choice",
            instructions="Which department should handle this customer request?",
            criteria=ROUTING_CRITERIA,
        )
    ]


def routing_cases() -> list[BenchmarkCase]:
    examples = {
        "billing": [
            "I was charged twice for the same monthly subscription.",
            "The invoice total is wrong and I need a corrected bill.",
            "My refund still has not reached my card.",
            "Why did my subscription renewal cost more this month?",
        ],
        "technical": [
            "The API returns 500 every time I create a webhook.",
            "Login via SSO stopped working after today's update.",
            "The mobile app crashes when I upload a receipt.",
            "Our integration cannot sync any new records.",
        ],
        "sales": [
            "Can you send pricing for 200 enterprise seats?",
            "We want a product demo for our procurement team.",
            "Do you offer annual contracts with volume discounts?",
            "Which plan includes advanced analytics?",
        ],
        "account": [
            "I need to transfer workspace ownership to another admin.",
            "Please change the email associated with my account.",
            "I lost access to the organization after our admin left.",
            "How do I add a second account administrator?",
        ],
        "shipping": [
            "The package tracking has not moved for five days.",
            "Can I change the delivery address before dispatch?",
            "My order says delivered but nothing arrived.",
            "When will the replacement device be shipped?",
        ],
        "cancellation": [
            "Cancel my subscription at the end of this billing period.",
            "I want to close the account and stop future renewals.",
            "Please cancel order 8821 before it ships.",
            "Do not renew our plan next month.",
        ],
    }
    cases: list[BenchmarkCase] = []
    for label, texts in examples.items():
        for i, text in enumerate(texts):
            cases.append(BenchmarkCase(f"routing-{label}-{i}", text, {"department": label}))
    return cases


def calibration_cases() -> list[BenchmarkCase]:
    clear = routing_cases()
    ambiguous = [
        ("I can't use the product after my card was charged. Help me fix this.", "technical"),
        ("Before I renew, tell me why the price changed and what the enterprise plan costs.", "sales"),
        ("My replacement is late and I may just cancel everything.", "shipping"),
        ("I need access restored so I can download the invoice.", "account"),
        ("Please stop the renewal; I also think the last charge is incorrect.", "cancellation"),
        ("The checkout page errors when I try to pay for the annual plan.", "technical"),
    ]
    cases = [
        BenchmarkCase(
            case_id=f"cal-clear-{i}",
            state=c.state,
            expected=c.expected,
            metadata={"difficulty": "clear"},
        )
        for i, c in enumerate(clear)
    ]
    cases.extend(
        BenchmarkCase(
            case_id=f"cal-ambiguous-{i}",
            state=text,
            expected={"department": label},
            metadata={"difficulty": "ambiguous"},
        )
        for i, (text, label) in enumerate(ambiguous)
    )
    return cases


def scaling_question_bank() -> list[QuestionSpec]:
    yes_no = [
        ("urgent", "Does the message express urgency or time pressure?"),
        ("refund", "Does the customer explicitly request a refund?"),
        ("human", "Does the customer explicitly request a human agent?"),
        ("legal", "Does the customer threaten legal action?"),
        ("security", "Does the message indicate unauthorized account activity?"),
        ("churn", "Does the customer indicate they may stop using the service?"),
        ("pii", "Does the message include personally identifying information?"),
        ("outage", "Does the message describe a service outage or unavailable product?"),
        ("payment", "Does the message mention a payment or charge?"),
        ("integration", "Does the message mention an API or software integration?"),
        ("deadline", "Does the message mention a concrete deadline?"),
        ("repeat", "Does the customer say the problem has happened repeatedly?"),
        ("angry", "Does the message contain clearly angry language?"),
        ("data_loss", "Does the message suggest data has been lost?"),
        ("blocked", "Is the customer blocked from completing a core task?"),
        ("workaround", "Does the customer mention an available workaround?"),
    ]
    bank = [QuestionSpec(i, "noul", text) for i, text in yes_no]
    for idx, (base_id, text) in enumerate(cycle(yes_no)):
        if len(bank) >= 32:
            break
        bank.append(QuestionSpec(f"{base_id}_alt_{idx}", "noul", f"Independent check: {text}"))
    return bank


def scaling_state() -> str:
    return (
        "URGENT: our Stripe integration has failed three times today and checkout is blocked. "
        "We were charged for the service and are losing sales. If this is not fixed by 5 PM, "
        "we may cancel. Please get a human engineer involved."
    )


def expense_questions() -> list[QuestionSpec]:
    return [
        QuestionSpec("receipt_readable", "noul", "Is the receipt clearly readable?"),
        QuestionSpec(
            "category",
            "choice",
            "What type of business expense is this?",
            {"meal": "Food or restaurant", "travel": "Transport or lodging", "equipment": "Equipment or hardware"},
        ),
        QuestionSpec("description_matches", "noul", "Does the claim description match the receipt?"),
        QuestionSpec("fraud_pattern", "noul", "Does the state describe a clear fraud or tampering pattern?"),
    ]


def expense_cases() -> list[BenchmarkCase]:
    raw = [
        ("Dinner with client, €62. Receipt is sharp and says Trattoria Centro €62. No tampering.", "meal", True, True, False),
        ("Team dinner, €110. Receipt readable and says restaurant €110, while claim says taxi. No tampering.", "meal", True, False, False),
        ("Train to client office, €48. Receipt readable, train operator and claim match. No tampering.", "travel", True, True, False),
        ("Laptop dock, €180. Receipt unreadable because the image is heavily blurred.", "equipment", False, False, False),
        ("Hotel, €240. Receipt appears edited: vendor name and total use inconsistent fonts and overwritten pixels.", "travel", True, True, True),
        ("Keyboard, €89. Receipt readable, hardware store, description matches.", "equipment", True, True, False),
    ]
    cases = []
    for i, (state, category, readable, matches, fraud) in enumerate(raw):
        if fraud:
            action = "review"
        elif not readable:
            action = "request_receipt"
        elif category == "meal" and "€110" in state and not matches:
            action = "manager_review"
        else:
            action = "approve"
        cases.append(
            BenchmarkCase(
                f"expense-{i}",
                state,
                {
                    "receipt_readable": float(readable),
                    "category": category,
                    "description_matches": float(matches),
                    "fraud_pattern": float(fraud),
                    "final_action": action,
                },
            )
        )
    return cases


def support_questions() -> list[QuestionSpec]:
    return [
        QuestionSpec(
            "intent",
            "choice",
            "What is the customer's primary intent?",
            {
                "refund": "Get money returned",
                "technical": "Resolve a product or integration problem",
                "cancel": "Cancel service",
                "information": "Ask for information",
            },
        ),
        QuestionSpec("urgent", "noul", "Is this request time-sensitive or urgent?"),
        QuestionSpec("human_requested", "noul", "Does the customer explicitly request a human?"),
        QuestionSpec("angry", "noul", "Is the customer clearly angry or hostile?"),
    ]


def support_cases() -> list[BenchmarkCase]:
    raw = [
        ("Please refund yesterday's duplicate charge.", "refund", False, False, False),
        ("API is down and production is blocked. I need an engineer now.", "technical", True, True, False),
        ("Cancel the subscription before it renews tomorrow.", "cancel", True, False, False),
        ("What does the enterprise plan include?", "information", False, False, False),
        ("This is ridiculous. Refund me and let me speak to a person.", "refund", False, True, True),
    ]
    cases = []
    for i, (text, intent, urgent, human, angry) in enumerate(raw):
        if human or angry:
            action = "handoff"
        elif intent == "refund":
            action = "refund_flow"
        elif intent == "cancel":
            action = "cancel_flow"
        elif intent == "technical" and urgent:
            action = "priority_support"
        else:
            action = "answer"
        cases.append(
            BenchmarkCase(
                f"support-{i}",
                text,
                {
                    "intent": intent,
                    "urgent": float(urgent),
                    "human_requested": float(human),
                    "angry": float(angry),
                    "final_action": action,
                },
            )
        )
    return cases
