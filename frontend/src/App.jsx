import { useState, useRef, useEffect } from 'react'
import './index.css'

export default function App() {
  const [chatHistory, setChatHistory] = useState([
    { role: 'ai', content: 'Hi there! I\'m Travelo AI. How can I help you plan your next trip?' }
  ])
  const [message, setMessage] = useState('')
  const [sessionId] = useState(() => crypto.randomUUID())  // Stable per browser tab
  const [budget, setBudget] = useState(5000)
  const [loading, setLoading] = useState(false)
  const [latestData, setLatestData] = useState(null)
  const [activeTab, setActiveTab] = useState('Hotels')
  const [destination, setDestination] = useState('Explore')

  const chatEndRef = useRef(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory, loading])

  async function sendDirectMessage(text) {
    const userMsg = { role: 'user', content: text }
    setChatHistory(prev => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await fetch('http://127.0.0.1:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, budget: Number(budget), session_id: sessionId })
      })
      const data = await res.json()
      
      let aiContent = data.response || 'I\'ve updated your recommendations on the right.'
      
      if (data.hotels && data.hotels.length > 0) {
        setLatestData({ type: 'hotel_recommendation', results: data.hotels })
        setActiveTab('Hotels')
      } else if (data.attractions && data.attractions.length > 0) {
        setLatestData({ type: 'attraction_recommendation', results: data.attractions })
        setActiveTab('Places')
      } else if (data.restaurants && data.restaurants.length > 0) {
        setLatestData({ type: 'restaurant_recommendation', results: data.restaurants })
        setActiveTab('Food')
      } else if (data.events && data.events.length > 0) {
        setLatestData({ type: 'event_recommendation', results: data.events })
        setActiveTab('Events')
      }

      if (data.place_info) {
        setDestination(data.place_info.name)
      }

      setChatHistory(prev => [...prev, { role: 'ai', content: aiContent, show_review_prompt: data.show_review_prompt, show_attractions_prompt: data.show_attractions_prompt, show_restaurants_prompt: data.show_restaurants_prompt, show_events_prompt: data.show_events_prompt }])
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'ai', content: 'Sorry, I failed to connect to the backend.' }])
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!message.trim()) return
    const text = message
    setMessage('')
    await sendDirectMessage(text)
  }

  const handleReviewRequest = async (placeName) => {
    setLoading(true)
    setChatHistory(prev => [...prev, { role: 'user', content: `What do real users say about ${placeName}?` }])
    try {
      const res = await fetch(`http://127.0.0.1:8000/chat/summarize-place?place_name=${encodeURIComponent(placeName)}`, {
        method: 'POST'
      })
      const data = await res.json()
      setChatHistory(prev => [...prev, { role: 'ai', content: data.response }])
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'ai', content: 'Failed to fetch reviews.' }])
    } finally {
      setLoading(false)
    }
  }

  const handleHotelReviewRequest = async (hotelName, propertyToken) => {
    setLoading(true)
    setChatHistory(prev => [...prev, { role: 'user', content: `Summarize reviews for ${hotelName}` }])
    try {
      const res = await fetch(`http://127.0.0.1:8000/chat/summarize-hotel?hotel_name=${encodeURIComponent(hotelName)}&property_token=${propertyToken}`, {
        method: 'POST'
      })
      const data = await res.json()
      setChatHistory(prev => [...prev, { role: 'ai', content: data.response }])
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'ai', content: 'Failed to fetch reviews for this hotel.' }])
    } finally {
      setLoading(false)
    }
  }

  const handleAttractionReviewRequest = async (attractionName, dataId) => {
    setLoading(true)
    setChatHistory(prev => [...prev, { role: 'user', content: `Summarize reviews for ${attractionName}` }])
    try {
      const res = await fetch(`http://127.0.0.1:8000/chat/summarize-attraction?attraction_name=${encodeURIComponent(attractionName)}&data_id=${encodeURIComponent(dataId)}`, {
        method: 'POST'
      })
      const data = await res.json()
      setChatHistory(prev => [...prev, { role: 'ai', content: data.response }])
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'ai', content: 'Failed to fetch reviews for this attraction.' }])
    } finally {
      setLoading(false)
    }
  }

  const handleRestaurantReviewRequest = async (restaurantName, dataId) => {
    setLoading(true)
    setChatHistory(prev => [...prev, { role: 'user', content: `Summarize reviews for ${restaurantName}` }])
    try {
      const res = await fetch(`http://127.0.0.1:8000/chat/summarize-restaurant?restaurant_name=${encodeURIComponent(restaurantName)}&data_id=${encodeURIComponent(dataId)}`, {
        method: 'POST'
      })
      const data = await res.json()
      setChatHistory(prev => [...prev, { role: 'ai', content: data.response }])
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'ai', content: 'Failed to fetch reviews for this restaurant.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app-container">
      {/* Top Bar */}
      <header className="top-bar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ background: '#3b82f6', color: 'white', width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '8px', fontWeight: 'bold' }}>T</div>
          <div>
            <h1>TRAVELO AI</h1>
            <div className="trip-info">{destination} • Flexible Dates</div>
          </div>
        </div>
        <div style={{ color: '#4ade80', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '8px', fontWeight: '500' }}>
          <span style={{ width: 8, height: 8, background: '#4ade80', borderRadius: '50%', display: 'inline-block' }}></span>
          System Ready
        </div>
      </header>

      <div className="main-content">
        {/* Left Pane: Chat */}
        <div className="chat-pane">
          <div className="chat-history">
            {chatHistory.map((msg, idx) => (
              <div key={idx} className={`message ${msg.role}`}>
                {msg.content}
                {msg.role === 'ai' && msg.show_review_prompt && (
                  <div style={{ marginTop: '12px' }}>
                    <button 
                      onClick={() => handleReviewRequest(destination)}
                      style={{ background: 'rgba(59, 130, 246, 0.2)', border: '1px solid #3b82f6', color: '#60a5fa', padding: '6px 12px', borderRadius: '8px', cursor: 'pointer', fontSize: '0.8rem' }}
                    >
                      💬 See user experiences
                    </button>
                  </div>
                )}
                {msg.role === 'ai' && msg.show_attractions_prompt && (
                  <div style={{ marginTop: '12px' }}>
                    <button 
                      onClick={() => sendDirectMessage(`Show nearby attractions for ${destination}`)}
                      style={{ background: 'rgba(16, 185, 129, 0.2)', border: '1px solid #10b981', color: '#34d399', padding: '6px 12px', borderRadius: '8px', cursor: 'pointer', fontSize: '0.8rem' }}
                    >
                      🏛️ Show nearby attractions
                    </button>
                  </div>
                )}
                {msg.role === 'ai' && msg.show_restaurants_prompt && (
                  <div style={{ marginTop: '12px' }}>
                    <button 
                      onClick={() => sendDirectMessage(`Where to eat in ${destination}?`)}
                      style={{ background: 'rgba(239, 68, 68, 0.2)', border: '1px solid #ef4444', color: '#f87171', padding: '6px 12px', borderRadius: '8px', cursor: 'pointer', fontSize: '0.8rem' }}
                    >
                      🍽️ Show top restaurants
                    </button>
                  </div>
                )}
                {msg.role === 'ai' && msg.show_events_prompt && (
                  <div style={{ marginTop: '12px' }}>
                    <button 
                      onClick={() => sendDirectMessage(`What is happening in ${destination}?`)}
                      style={{ background: 'rgba(139, 92, 246, 0.2)', border: '1px solid #8b5cf6', color: '#a78bfa', padding: '6px 12px', borderRadius: '8px', cursor: 'pointer', fontSize: '0.8rem' }}
                    >
                      📅 Show local events
                    </button>
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="message ai loader">
                <div className="dot"></div>
                <div className="dot"></div>
                <div className="dot"></div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <div className="input-area">
            <form className="input-form" onSubmit={handleSubmit}>
              <input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Where do you want to go?"
                disabled={loading}
              />
              <button type="submit" className="send-btn" disabled={loading || !message.trim()}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13"></line>
                  <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                </svg>
              </button>
            </form>
          </div>
        </div>

        {/* Right Pane: Context & Results */}
        <div className="context-pane">
          <div className="tabs">
            {['Hotels', 'Food', 'Places', 'Events'].map(tab => (
              <button 
                key={tab} 
                className={`tab ${activeTab === tab ? 'active' : ''}`}
                onClick={() => setActiveTab(tab)}
              >
                {tab}
              </button>
            ))}
          </div>

          {latestData?.type === 'hotel_recommendation' && activeTab === 'Hotels' ? (
            <>
              <div className="context-banner">
                🎯 Best matches found in {destination} based on current availability.
              </div>

              <div className="section-title">Top Recommendations</div>
              
              <div className="cards-container">
                {latestData.results.map((hotel, idx) => (
                  <div key={idx} className="hotel-card">
                    <div className="card-header">
                      <div>
                        <h3 className="card-title">
                          <span style={{ color: '#f59e0b', marginRight: '6px' }}>★</span>
                          {hotel.name}
                        </h3>
                        <div className="card-subtitle">{hotel.address || destination}</div>
                      </div>
                      <div className="card-price">
                        <div className="price-val">₹{hotel.price}</div>
                        <div className="price-tag">Per Night</div>
                      </div>
                    </div>

                    <div className="pills">
                      <span className="pill">Verified</span>
                      <span className="pill">Free Wifi</span>
                      {hotel.rating && <span className="pill">{hotel.rating} Rating</span>}
                    </div>

                    <div className="card-summary">
                      {hotel.description || "A highly rated stay options with modern amenities and great service."}
                    </div>

                    <div className="score-bar">
                      <div className="progress-bg">
                        <div className="progress-fill" style={{ width: `${(hotel.rating / 5) * 100 || 85}%` }}></div>
                      </div>
                      <span className="score-val">Match {Math.round((hotel.rating / 5) * 100 || 85)}%</span>
                    </div>

                    <button 
                      className="add-btn" 
                      style={{ marginTop: '16px', width: '100%', borderColor: '#3b82f6', color: '#60a5fa', fontWeight: '500' }}
                      onClick={() => handleHotelReviewRequest(hotel.name, hotel.property_token)}
                    >
                      💬 Summarize Reviews
                    </button>
                  </div>
                ))}
              </div>
            </>
          ) : latestData?.type === 'restaurant_recommendation' && activeTab === 'Food' ? (
            <>
              <div className="context-banner">
                🎯 Top dining spots found in {destination}.
              </div>

              <div className="section-title">Top Restaurants</div>
              
              <div className="cards-container">
                {latestData.results.map((rest, idx) => (
                  <div key={idx} className="hotel-card">
                    <div className="card-header">
                      <div>
                        <h3 className="card-title">
                          <span style={{ color: '#ef4444', marginRight: '6px' }}>🍽️</span>
                          {rest.name}
                        </h3>
                      </div>
                      {rest.rating && (
                        <div className="card-price">
                          <div className="price-val">★ {rest.rating}</div>
                          <div className="price-tag">{rest.reviews} Reviews</div>
                        </div>
                      )}
                    </div>

                    <div className="pills">
                      {rest.price_level && <span className="pill">{rest.price_level}</span>}
                    </div>

                    <div className="card-summary">
                      {rest.description || "A highly rated restaurant offering great food and ambiance."}
                    </div>

                    <button 
                      className="add-btn" 
                      style={{ marginTop: '16px', width: '100%', borderColor: '#ef4444', color: '#f87171', fontWeight: '500' }}
                      onClick={() => handleRestaurantReviewRequest(rest.name, rest.data_id)}
                    >
                      💬 Summarize Reviews
                    </button>
                  </div>
                ))}
              </div>
            </>
          ) : latestData?.type === 'attraction_recommendation' && activeTab === 'Places' ? (
            <>
              <div className="context-banner">
                🎯 Top attractions found in {destination}.
              </div>

              <div className="section-title">Top Attractions</div>
              
              <div className="cards-container">
                {latestData.results.map((attr, idx) => (
                  <div key={idx} className="hotel-card">
                    <div className="card-header">
                      <div>
                        <h3 className="card-title">
                          <span style={{ color: '#10b981', marginRight: '6px' }}>🏛️</span>
                          {attr.name}
                        </h3>
                      </div>
                      {attr.rating && (
                        <div className="card-price">
                          <div className="price-val">★ {attr.rating}</div>
                          <div className="price-tag">{attr.reviews} Reviews</div>
                        </div>
                      )}
                    </div>

                    <div className="card-summary">
                      {attr.description || "A popular point of interest worth exploring."}
                    </div>

                    <button 
                      className="add-btn" 
                      style={{ marginTop: '16px', width: '100%', borderColor: '#10b981', color: '#34d399', fontWeight: '500' }}
                      onClick={() => handleAttractionReviewRequest(attr.name, attr.data_id)}
                    >
                      💬 Summarize Reviews
                    </button>
                  </div>
                ))}
              </div>
            </>
          ) : latestData?.type === 'event_recommendation' && activeTab === 'Events' ? (
            <>
              <div className="context-banner">
                🎯 Top events happening in {destination}.
              </div>

              <div className="section-title">Upcoming Events</div>
              
              <div className="cards-container">
                {latestData.results.map((evt, idx) => (
                  <div key={idx} className="hotel-card">
                    <div className="card-header">
                      <div>
                        <h3 className="card-title">
                          <span style={{ color: '#8b5cf6', marginRight: '6px' }}>📅</span>
                          {evt.title}
                        </h3>
                      </div>
                    </div>

                    <div className="pills">
                      {evt.date_string && <span className="pill">{evt.date_string}</span>}
                      {evt.venue_name && <span className="pill" style={{ background: 'rgba(139, 92, 246, 0.1)', color: '#a78bfa' }}>{evt.venue_name}</span>}
                    </div>

                    <div className="card-summary">
                      {evt.description || evt.address || "An upcoming event you might be interested in."}
                    </div>

                    {evt.link && (
                      <button 
                        className="add-btn" 
                        style={{ marginTop: '16px', width: '100%', borderColor: '#8b5cf6', color: '#a78bfa', fontWeight: '500' }}
                        onClick={() => window.open(evt.link, '_blank')}
                      >
                        🎟️ View Event / Get Tickets
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '60%', color: 'var(--text-secondary)' }}>
              <div style={{ fontSize: '3rem', marginBottom: '16px' }}>🌍</div>
              <div style={{ fontWeight: '500' }}>Your travel insights will appear here</div>
              <div style={{ fontSize: '0.85rem', marginTop: '8px' }}>Try searching for "hotels in Kochi" or "tell me about Alappuzha"</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
