from app.services.graph_orchestrator import travel_graph

from IPython.display import Image, display

# Generate and display the image inline
image_data = travel_graph.get_graph().draw_mermaid_png()

with open("travel_graph.png", "wb") as f:
    f.write(image_data)

print("Graph saved to travel_graph.png")