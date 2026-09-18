"""Conservative, local-only eligibility checks for customer case emails."""

from __future__ import annotations

from dataclasses import dataclass


AUTOMATED_SENDER_MARKERS = (
    "no-reply",
    "noreply",
    "do-not-reply",
    "donotreply",
    "mailer-daemon",
    "notification",
    "notifications",
    "newsletter",
    "alerts",
    "alert",
)
AUTOMATED_CONTENT_MARKERS = (
    "automated message",
    "automated notification",
    "do not reply",
    "unsubscribe",
    "security alert",
    "verify your account",
    "sign-in alert",
)
UNRELATED_CONTENT_MARKERS = (
    "newsletter",
    "promotion",
    "promotional",
    "sale ends",
    "special offer",
    "marketing",
    "webinar",
    "meeting invitation",
)
CASE_KEYWORDS = (
    "issue",
    "problem",
    "complaint",
    "support",
    "service",
    "help",
    "assistance",
    "not working",
    "faulty",
    "defective",
    "damaged",
    "replacement",
    "return",
    "warranty",
    "installation",
    "install",
    "technician",
    "repair",
    "order",
    "delivery",
    "invoice",
    "product issue",
)


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    category: str
    reason: str


def assess_customer_case_email(sender: str, subject: str, snippet: str) -> Eligibility:
    """Allow only messages with a clear customer-case signal; uncertainty is skipped."""
    sender_text = sender.casefold().strip()
    content = f"{subject}\n{snippet}".casefold()
    domain = sender_text.rpartition("@")[2]

    if domain in {"accounts.google.com", "google.com"}:
        return Eligibility(False, "AUTOMATED/SYSTEM", "sender is a Google system or security address")
    if any(marker in sender_text for marker in AUTOMATED_SENDER_MARKERS):
        return Eligibility(False, "AUTOMATED/SYSTEM", "sender address appears automated or no-reply")
    if any(marker in content for marker in AUTOMATED_CONTENT_MARKERS):
        return Eligibility(False, "AUTOMATED/SYSTEM", "subject or message snippet appears automated or system-generated")
    if any(marker in content for marker in UNRELATED_CONTENT_MARKERS):
        return Eligibility(False, "UNRELATED", "subject or message snippet appears promotional or unrelated")

    matched_keywords = [keyword for keyword in CASE_KEYWORDS if keyword in content]
    if matched_keywords:
        return Eligibility(
            True,
            "ELIGIBLE",
            "clear customer-case signal: " + ", ".join(matched_keywords[:3]),
        )
    return Eligibility(False, "UNRELATED", "no clear customer support or case-request signal")


def _demo() -> None:
    """Run fake examples only; this function does not connect to Gmail."""
    examples = (
        ("customer@example.com", "Need technician for faulty product", "Product is not working."),
        ("no-reply@accounts.google.com", "Security alert", "Review sign-in activity."),
        ("offers@example.com", "Special offer", "Unsubscribe from this promotion."),
        ("person@example.com", "Hello", "Just checking in."),
    )
    for sender, subject, snippet in examples:
        result = assess_customer_case_email(sender, subject, snippet)
        print(f"{sender}: {result.category} — {result.reason}")


if __name__ == "__main__":
    _demo()
