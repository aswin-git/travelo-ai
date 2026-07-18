with open("frontend/src/App.jsx", "r") as f:
    content = f.read()

# Replace <div className="cards-container"> inside the Hotel, Restaurant, Attraction sections
# 1. Hotel
idx_hotel_start = content.find("latestData?.type === 'hotel_recommendation'")
if idx_hotel_start != -1:
    idx_hotel_cards = content.find('<div className="cards-container">', idx_hotel_start)
    content = content[:idx_hotel_cards] + '<div className="split-view-container">\n                  <div className="split-view-cards">' + content[idx_hotel_cards + len('<div className="cards-container">'):]
    
    idx_hotel_end = content.find(") : latestData?.type === 'restaurant_recommendation'", idx_hotel_start)
    # the closing </div> is right before </>\n            )
    idx_closing_div = content.rfind('</div>', idx_hotel_cards, idx_hotel_end)
    content = content[:idx_closing_div] + '</div>\n                  <div className="split-view-map">\n                    <MapComponent data={latestData} type="hotel" />\n                  </div>\n                </div>' + content[idx_closing_div + len('</div>'):]

# 2. Restaurant
idx_rest_start = content.find("latestData?.type === 'restaurant_recommendation'")
if idx_rest_start != -1:
    idx_rest_cards = content.find('<div className="cards-container">', idx_rest_start)
    content = content[:idx_rest_cards] + '<div className="split-view-container">\n                  <div className="split-view-cards">' + content[idx_rest_cards + len('<div className="cards-container">'):]
    
    idx_rest_end = content.find(") : latestData?.type === 'attraction_recommendation'", idx_rest_start)
    idx_closing_div = content.rfind('</div>', idx_rest_cards, idx_rest_end)
    content = content[:idx_closing_div] + '</div>\n                  <div className="split-view-map">\n                    <MapComponent data={latestData} type="restaurant" />\n                  </div>\n                </div>' + content[idx_closing_div + len('</div>'):]

# 3. Attraction
idx_attr_start = content.find("latestData?.type === 'attraction_recommendation'")
if idx_attr_start != -1:
    idx_attr_cards = content.find('<div className="cards-container">', idx_attr_start)
    content = content[:idx_attr_cards] + '<div className="split-view-container">\n                  <div className="split-view-cards">' + content[idx_attr_cards + len('<div className="cards-container">'):]
    
    idx_attr_end = content.find(") : latestData?.type === 'event_recommendation'", idx_attr_start)
    idx_closing_div = content.rfind('</div>', idx_attr_cards, idx_attr_end)
    content = content[:idx_closing_div] + '</div>\n                  <div className="split-view-map">\n                    <MapComponent data={latestData} type="attraction" />\n                  </div>\n                </div>' + content[idx_closing_div + len('</div>'):]

with open("frontend/src/App.jsx", "w") as f:
    f.write(content)
