with open("frontend/src/App.jsx", "r") as f:
    content = f.read()

content = content.replace(
    "{latestData.results.map((hotel, idx)\n                  {latestData.results.map((hotel, idx) => (",
    "{latestData.results.map((hotel, idx) => ("
)
content = content.replace(
    "{latestData.results.map((rest, idx)\n                  {latestData.results.map((rest, idx) => (",
    "{latestData.results.map((rest, idx) => ("
)
content = content.replace(
    "{latestData.results.map((attr, idx)\n                  {latestData.results.map((attr, idx) => (",
    "{latestData.results.map((attr, idx) => ("
)

with open("frontend/src/App.jsx", "w") as f:
    f.write(content)
