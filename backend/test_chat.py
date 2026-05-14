import requests
import json

response = requests.post(
    "http://127.0.0.1:8000/chat",
    json={"message": "where to eat in idukki"}
)
print(json.dumps(response.json(), indent=2))
