"""
Golden evaluation dataset for Travelo AI RAG pipeline.

Each sample contains:
- question:     The user query to evaluate
- place_name:   The place entity extracted (simulates intent extraction)
- ground_truth: A reference answer containing key facts a correct response must cover
"""

EVAL_DATASET = [
    # ── Munnar ────────────────────────────────────────────────────────────
    {
        "question": "Tell me about Munnar",
        "place_name": "Munnar",
        "ground_truth": (
            "Munnar is a hill station in the Western Ghats of Kerala, India, "
            "situated at around 1,600 metres above sea level. It is known for "
            "its sprawling tea plantations, misty mountains, and cool climate. "
            "Key attractions include Eravikulam National Park, Top Station, "
            "and Mattupetty Dam."
        ),
    },
    {
        "question": "What are the best things to do in Munnar?",
        "place_name": "Munnar",
        "ground_truth": (
            "Popular activities in Munnar include visiting tea plantations and "
            "the Tea Museum, trekking in Eravikulam National Park to spot the "
            "Nilgiri tahr, boating at Mattupetty Dam, exploring the flower "
            "gardens at Blossom Park, and enjoying panoramic views from Top Station."
        ),
    },
    {
        "question": "What is the best time to visit Munnar?",
        "place_name": "Munnar",
        "ground_truth": (
            "The best time to visit Munnar is from September to May. "
            "The monsoon season (June-August) brings heavy rainfall. "
            "Winter months (December-February) are cool and ideal for sightseeing, "
            "while summer (March-May) is pleasant with temperatures around 15-25°C."
        ),
    },

    # ── Alappuzha (Alleppey) ──────────────────────────────────────────────
    {
        "question": "Tell me about Alappuzha",
        "place_name": "Alappuzha",
        "ground_truth": (
            "Alappuzha, also known as Alleppey, is a city in Kerala famous for "
            "its houseboat cruises through the backwaters, a network of lagoons, "
            "canals, and lakes. It is often called the 'Venice of the East'. "
            "The Nehru Trophy Boat Race is a major annual event held here."
        ),
    },
    {
        "question": "What can I do in Alappuzha?",
        "place_name": "Alappuzha",
        "ground_truth": (
            "In Alappuzha you can take a houseboat cruise through the Kerala "
            "backwaters, visit Alappuzha Beach, explore Marari Beach, see the "
            "Revi Karunakaran Museum, visit Krishnapuram Palace, and experience "
            "the Nehru Trophy Snake Boat Race (held in August)."
        ),
    },
    {
        "question": "How do I get to Alappuzha from Kochi?",
        "place_name": "Alappuzha",
        "ground_truth": (
            "Alappuzha is about 53 km from Kochi. You can reach it by road "
            "(approximately 1.5 hours by car or bus via NH66), by train "
            "(Alappuzha railway station is well-connected), or by boat through "
            "the scenic backwater routes."
        ),
    },

    # ── Wayanad ───────────────────────────────────────────────────────────
    {
        "question": "Tell me about Wayanad",
        "place_name": "Wayanad",
        "ground_truth": (
            "Wayanad is a lush green district in the Western Ghats of Kerala, "
            "known for its wildlife sanctuaries, spice plantations, caves, and "
            "waterfalls. It is home to Wayanad Wildlife Sanctuary, Edakkal Caves "
            "with ancient petroglyphs, and Chembra Peak with its heart-shaped lake."
        ),
    },
    {
        "question": "What wildlife can I see in Wayanad?",
        "place_name": "Wayanad",
        "ground_truth": (
            "The Wayanad Wildlife Sanctuary is part of the Nilgiri Biosphere "
            "Reserve and is home to elephants, tigers, leopards, deer, and "
            "various bird species. Tholpetty and Muthanga are the two main "
            "ranges for wildlife safaris."
        ),
    },
    {
        "question": "Is Wayanad good for trekking?",
        "place_name": "Wayanad",
        "ground_truth": (
            "Yes, Wayanad is excellent for trekking. Popular treks include "
            "Chembra Peak (which has a heart-shaped lake), Pakshipathalam, "
            "Brahmagiri Hills, and Banasura Hill. The best trekking season "
            "is from September to May."
        ),
    },

    # ── Varkala ───────────────────────────────────────────────────────────
    {
        "question": "Tell me about Varkala",
        "place_name": "Varkala",
        "ground_truth": (
            "Varkala is a coastal town in Kerala known for its dramatic cliff "
            "overlooking the Arabian Sea, called Varkala Cliff or North Cliff. "
            "It is famous for its beach, mineral water springs, the ancient "
            "Janardanaswamy Temple, and housing the Samadhi of the revered saint Sree Narayana Guru."
        ),
    },

    {
        "question": "What makes Varkala Beach unique?",
        "place_name": "Varkala",
        "ground_truth": (
            "Varkala Beach is unique because of the dramatic laterite cliff "
            "formations adjacent to the shoreline, known as Varkala Formation. "
            "Natural mineral water springs flow from these cliffs, believed to "
            "have medicinal properties. The cliff-top stretch is lined with "
            "cafes, shops, and offers stunning sunset views over the Arabian Sea."
        ),
    },
    {
        "question": "Is Varkala suitable for surfing?",
        "place_name": "Varkala",
        "ground_truth": (
            "Yes, Varkala has decent waves for surfing, especially for beginners "
            "and intermediate surfers. Several surf schools operate along the "
            "beach. The best surfing conditions are typically from June to "
            "September during the monsoon season when swells are larger."
        ),
    },

    # ── Kumarakom ─────────────────────────────────────────────────────────
    {
        "question": "Tell me about Kumarakom",
        "place_name": "Kumarakom",
        "ground_truth": (
            "Kumarakom is a cluster of small islands on Vembanad Lake in Kerala. "
            "It is a popular backwater destination known for its bird sanctuary, "
            "houseboat cruises, and Ayurvedic resorts. The Kumarakom Bird "
            "Sanctuary attracts migratory birds from around the world."
        ),
    },
    {
        "question": "What birds can I see in Kumarakom?",
        "place_name": "Kumarakom",
        "ground_truth": (
            "The Kumarakom Bird Sanctuary, spread across 14 acres, is home to "
            "local and migratory birds including egrets, herons, cormorants, "
            "teals, waterfowl, cuckoos, and Siberian cranes. The best time for "
            "bird watching is from November to February when migratory birds arrive."
        ),
    },
    {
        "question": "Can I do a houseboat trip from Kumarakom?",
        "place_name": "Kumarakom",
        "ground_truth": (
            "Yes, Kumarakom is one of the top starting points for houseboat "
            "cruises in Kerala. Houseboats (kettuvallam) cruise through the "
            "scenic Vembanad Lake backwaters. You can book overnight stays with "
            "meals included. Routes often pass through paddy fields, villages, "
            "and narrow canals."
        ),
    },

    # ── Kovalam ───────────────────────────────────────────────────────────
    {
        "question": "Tell me about Kovalam",
        "place_name": "Kovalam",
        "ground_truth": (
            "Kovalam is a beach town near Thiruvananthapuram in Kerala, known "
            "for its crescent-shaped coastline with three adjacent beaches: "
            "Lighthouse Beach, Hawa Beach, and Samudra Beach. It became popular "
            "with international tourists in the 1930s and is also known for "
            "Ayurvedic health resorts."
        ),
    },
    {
        "question": "Which is the best beach in Kovalam?",
        "place_name": "Kovalam",
        "ground_truth": (
            "Lighthouse Beach is the most popular and vibrant beach in Kovalam. "
            "Named after the Vizhinjam Lighthouse at its southern end, it has a "
            "wide stretch of sand, numerous cafes and shops along the promenade, "
            "and is ideal for swimming and sunbathing. Hawa Beach is more laid-back "
            "and Samudra Beach is the quietest of the three."
        ),
    },
    {
        "question": "What is there to do in Kovalam besides the beach?",
        "place_name": "Kovalam",
        "ground_truth": (
            "Beyond the beaches, Kovalam offers Ayurvedic spa treatments and "
            "wellness resorts, visits to the Vizhinjam Rock Cut Cave Temple "
            "(8th century), the Halcyon Castle, fishing village tours at "
            "Vizhinjam Harbour, and day trips to nearby Poovar Island and "
            "Thiruvananthapuram city attractions like the Padmanabhaswamy Temple."
        ),
    },

    # ── Cross-cutting / edge-case queries ─────────────────────────────────
    {
        "question": "Compare Munnar and Wayanad for a family trip",
        "place_name": "Munnar",
        "ground_truth": (
            "Both Munnar and Wayanad are hill stations in Kerala's Western Ghats. "
            "Munnar is known for tea plantations, cooler climate, and scenic "
            "viewpoints. Wayanad offers more wildlife, tribal heritage, and "
            "adventure activities like trekking. Munnar is more developed for "
            "tourism, while Wayanad has a more rustic, nature-immersive feel. "
            "Both are suitable for families."
        ),
    },
    {
        "question": "Is Kovalam safe for swimming?",
        "place_name": "Kovalam",
        "ground_truth": (
            "Kovalam's Lighthouse Beach and Hawa Beach are generally safe for "
            "swimming, with lifeguards on duty during the day. However, during "
            "monsoon season (June-August) strong currents and rough seas make "
            "swimming dangerous. It is advisable to swim only in designated areas "
            "and heed local safety flags."
        ),
    },
]
