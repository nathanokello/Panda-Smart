"""Phone number normalisation for Kenyan numbers.

Login, self-registration and agent registration all store and compare phone
numbers in one form (+2547XXXXXXXX), so "0712 345 678", "254712345678" and
"+254 712 345 678" are the same account.

This does NOT verify that the person owns the number. That needs an SMS
code (planned, through Africa's Talking).
"""
import re


def normalize_phone(value: str) -> str:
    if value is None:
        return ""
    phone = re.sub(r"[\s\-().]", "", str(value))
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    if re.fullmatch(r"0[17]\d{8}", phone):
        phone = "+254" + phone[1:]
    elif re.fullmatch(r"254[17]\d{8}", phone):
        phone = "+" + phone
    return phone


def is_valid_phone(value: str) -> bool:
    """True for a normalised international number such as +254712345678."""
    return bool(re.fullmatch(r"\+\d{9,15}", value or ""))
