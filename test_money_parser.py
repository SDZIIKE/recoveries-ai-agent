from agent_modules.recovery_agent import extract_monetary_amount

tests = [
    "$800",
    "$1,000",
    "$10,000",
    "$100,000",
    "1,000 dollars",
    "USD 1,000",
    "I want to change my monthly payment to $1,000.",
]

for text in tests:
    print(f"{text!r} -> {extract_monetary_amount(text)}")