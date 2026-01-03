
from endpoint_classifier import EndpointClassifier
import asyncio
import json

dataset = ""
with open('classification_dataset.json', 'r') as file:
    dataset = json.load(file)



results = []
for item in dataset:
    classifier = EndpointClassifier(item["url"])
    prediction = asyncio.run(classifier.classify())

    results.append({
        "url": item["url"],
        "true_label": item["label"],
        "predicted_label": prediction["type"]
    })


print(results) 

correct = sum(
    1 for r in results
    if r["true_label"] == r["predicted_label"]
)

accuracy = correct / len(results)

print(accuracy)
print(f"Endpoint Classification Result: {accuracy}")
