import requests
import json

response = requests.post(
    "http://127.0.0.1:8000/chat",
    json={"message": "what is happening in Kochi"}
)
print(json.dumps(response.json(), indent=2))
