"""One example request against the API."""

from api import handle_request

response = handle_request(
    {
        "method": "POST",
        "path": "/orders",
        "payload": {"order_id": "ORD-7", "token": "tok_test_1a2b3c4d", "qty": "2"},
    }
)
print(response)
