import re

with open("frontend/src/App.jsx", "r") as f:
    content = f.read()

# For Hotels
hotel_search = r'(<div className="cards-container">)(\s*\{latestData\.results\.map\(\(hotel, idx\).*?)(</>\s*\) : latestData\?\.type === \'restaurant_recommendation\')'
hotel_replace = r'''<div className="split-view-container">
                  <div className="split-view-cards">
                    {latestData.results.map((hotel, idx)\2
                  </div>
                  <div className="split-view-map">
                    <MapComponent data={latestData} type="hotel" />
                  </div>
                </div>\3'''
content = re.sub(hotel_search, hotel_replace, content, flags=re.DOTALL)

# For Restaurants
rest_search = r'(<div className="cards-container">)(\s*\{latestData\.results\.map\(\(rest, idx\).*?)(</>\s*\) : latestData\?\.type === \'attraction_recommendation\')'
rest_replace = r'''<div className="split-view-container">
                  <div className="split-view-cards">
                    {latestData.results.map((rest, idx)\2
                  </div>
                  <div className="split-view-map">
                    <MapComponent data={latestData} type="restaurant" />
                  </div>
                </div>\3'''
content = re.sub(rest_search, rest_replace, content, flags=re.DOTALL)

# For Attractions
attr_search = r'(<div className="cards-container">)(\s*\{latestData\.results\.map\(\(attr, idx\).*?)(</>\s*\) : latestData\?\.type === \'event_recommendation\')'
attr_replace = r'''<div className="split-view-container">
                  <div className="split-view-cards">
                    {latestData.results.map((attr, idx)\2
                  </div>
                  <div className="split-view-map">
                    <MapComponent data={latestData} type="attraction" />
                  </div>
                </div>\3'''
content = re.sub(attr_search, attr_replace, content, flags=re.DOTALL)

with open("frontend/src/App.jsx", "w") as f:
    f.write(content)

