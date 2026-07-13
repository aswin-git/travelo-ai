import { useState, useRef, useEffect, useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './index.css'
import { useAuth } from './contexts/AuthContext'
import { API_BASE } from './config'
import LoginPage from './components/LoginPage'
import LandingPage from './components/LandingPage'
import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'
import ItineraryWizard from './components/ItineraryWizard'
import ItineraryView from './components/ItineraryView'

const FALLBACK_IMAGES = {
  restaurant: "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=600&q=80",
  hotel: "https://images.unsplash.com/photo-1455587734955-081b22074882?auto=format&fit=crop&w=600&q=80",
  attraction: "https://images.unsplash.com/photo-1528543606781-2f6e6857f318?auto=format&fit=crop&w=600&q=80",
  event: "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=600&q=80",
  default: "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?auto=format&fit=crop&w=600&q=80"
};

export default function App() {
  const { user, session, loading: authLoading } = useAuth()
  const hasInitialized = useRef(false)
  const [currentView, setCurrentView] = useState('dashboard') // dashboard, chat, wizard, itinerary_only
  const [chatHistory, setChatHistory] = useState([
    { role: 'ai', content: 'Hi there! I\'m Travelo AI. How can I help you plan your next trip?' }
  ])
  const [message, setMessage] = useState('')
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID())
  const [budget, setBudget] = useState('')
  const [loading, setLoading] = useState(false)
  const [latestData, setLatestData] = useState(null)
  const [activeTab, setActiveTab] = useState('Hotels')
  const [destination, setDestination] = useState('Explore')
  const [missingInfo, setMissingInfo] = useState(null)
  const [travelerType, setTravelerType] = useState('')
  const [cuisine, setCuisine] = useState('')
  const [adults, setAdults] = useState(2)
  const [checkIn, setCheckIn] = useState('')
  const [checkOut, setCheckOut] = useState('')
  const [startLocation, setStartLocation] = useState('')
  const [endLocation, setEndLocation] = useState('')
  const [travelMode, setTravelMode] = useState('')
  const [lastMessage, setLastMessage] = useState('')
  const [lastIntent, setLastIntent] = useState(null)
  const [expandedRoute, setExpandedRoute] = useState(null)
  const [numDays, setNumDays] = useState('')
  const [pacing, setPacing] = useState('')
  const [activeDay, setActiveDay] = useState(1)
  const [itineraryData, setItineraryData] = useState(null)
  const [mealPreference, setMealPreference] = useState('')
  const [interests, setInterests] = useState('')
  const [activityLevel, setActivityLevel] = useState('')
  const [kidsFriendly, setKidsFriendly] = useState(false)
  const [dietaryRestrictions, setDietaryRestrictions] = useState('')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [saveStatus, setSaveStatus] = useState(null)
  const [savedItems, setSavedItems] = useState([])
  const [pinPopover, setPinPopover] = useState(null) // { id, name }
  const [crowdAware, setCrowdAware] = useState(null) // null = not set, true/false
  const [crowdPrecision, setCrowdPrecision] = useState('approximate') // "precise" or "approximate"
  const [weatherAware, setWeatherAware] = useState(null) // null = not set, true/false
  const [showLogin, setShowLogin] = useState(false)
  const [loadingMessage, setLoadingMessage] = useState('Analyzing request...')
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [selectedNewPlaces, setSelectedNewPlaces] = useState([])
  const [isEditingItinerary, setIsEditingItinerary] = useState(false)
  const [searchLoading, setSearchLoading] = useState(false)
  const [fullScreenImage, setFullScreenImage] = useState(null)

  const chatEndRef = useRef(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatHistory, loading])

  // Cycle through loading phrases while waiting for AI response
  useEffect(() => {
    let intervalId;
    if (loading) {
      const lastUserMsg = chatHistory.filter(m => m.role === 'user').pop()?.content?.toLowerCase() || '';
      const isPlanning = ['plan', 'itinerary', 'trip', 'schedule', 'days'].some(k => lastUserMsg.includes(k));

      const phrases = isPlanning ? [
        'Analyzing request...',
        'Searching for best places...',
        'Checking real-time crowd data...',
        'Optimizing geographic routes...',
        'Generating perfect itinerary...',
        'Finalizing details...'
      ] : [
        'Thinking...',
        'Drafting response...',
        'Analyzing...'
      ];

      let currentIndex = 0;
      setLoadingMessage(phrases[0]);

      intervalId = setInterval(() => {
        currentIndex = (currentIndex + 1) % phrases.length;
        setLoadingMessage(phrases[currentIndex]);
      }, 3000); // Change phrase every 3 seconds
    }
    return () => clearInterval(intervalId);
  }, [loading]); // chatHistory intentionally omitted to avoid restarts

  // Reset state when user logs in initially to prevent data bleeding
  useEffect(() => {
    if (user && !hasInitialized.current) {
      hasInitialized.current = true
      setSessionId(crypto.randomUUID())
      setChatHistory([{ role: 'ai', content: 'Hi there! I\'m Travelo AI. How can I help you plan your next trip?' }])
      setDestination('Explore')
      setLatestData(null)
      setItineraryData(null)
      setCurrentView('dashboard')
      fetchSavedItems()
    } else if (!user) {
      hasInitialized.current = false
    }
  }, [user])

  const accessToken = session?.access_token
  const API = API_BASE

  const authHeaders = useCallback(() => {
    const h = { 'Content-Type': 'application/json' }
    if (accessToken) h['Authorization'] = `Bearer ${accessToken}`
    return h
  }, [accessToken])

  const fetchSavedItems = useCallback(async () => {
    if (!accessToken) return
    try {
      const res = await fetch(`${API}/user/saved-items`, { headers: authHeaders() })
      if (res.ok) setSavedItems(await res.json())
    } catch (err) {
      console.error('Failed to fetch saved items:', err)
    }
  }, [accessToken, authHeaders])

  // Expose refresh for sidebar
  useEffect(() => {
    window.__refreshSavedItems = fetchSavedItems
    return () => delete window.__refreshSavedItems
  }, [fetchSavedItems])

  // Auto-save chat after each message exchange
  const saveChatSession = useCallback(async (messages, dest) => {
    if (!accessToken) return
    try {
      const firstUserMsg = messages.find(m => m.role === 'user')
      const title = firstUserMsg ? firstUserMsg.content.slice(0, 50) : 'New Chat'
      await fetch(`${API}/user/chat-sessions`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          session_id: sessionId,
          title,
          messages,
          destination: dest || destination,
        }),
      })
      window.__refreshSidebarSessions?.()
    } catch (err) {
      console.error('Failed to save chat session:', err)
    }
  }, [accessToken, sessionId, destination, authHeaders])

  const handleNewChat = () => {
    setSessionId(crypto.randomUUID())
    setChatHistory([{ role: 'ai', content: 'Hi there! I\'m Travelo AI. How can I help you plan your next trip?' }])
    setLatestData(null)
    setItineraryData(null)
    setDestination('Explore')
    setActiveTab('Hotels')
    setCurrentView('dashboard')
  }

  const handleLoadSession = async (sid) => {
    if (!accessToken) return
    try {
      const res = await fetch(`${API}/user/chat-sessions/${sid}`, { headers: authHeaders() })
      if (!res.ok) return
      const data = await res.json()
      setSessionId(data.session_id)
      setChatHistory(data.messages || [])
      setDestination(data.destination || 'Explore')
      setLatestData(null)

      // Auto-load the most recent itinerary if one exists in this chat
      const messages = data.messages || []
      const lastItineraryMsg = [...messages].reverse().find(m => m.itinerary)

      if (lastItineraryMsg) {
        setItineraryData(lastItineraryMsg.itinerary)
        setActiveTab('Itinerary')
      } else {
        setItineraryData(null)
        setActiveTab('Hotels')
      }
      setCurrentView('chat')
    } catch (err) {
      console.error('Failed to load session:', err)
    }
  }

  const handleLoadItinerary = async (id) => {
    if (!accessToken) return
    try {
      const res = await fetch(`${API}/user/itineraries/${id}`, { headers: authHeaders() })
      if (!res.ok) return
      const data = await res.json()
      setItineraryData(data.itinerary_data)
      setDestination(data.destination || 'Explore')
      setActiveDay(1)
      setActiveTab('Itinerary')
      setCurrentView('itinerary_only')
    } catch (err) {
      console.error('Failed to load itinerary:', err)
    }
  }

  const handleSaveItinerary = async () => {
    if (!accessToken || !itineraryData) return
    setSaveStatus('saving')
    try {
      await fetch(`${API}/user/itineraries`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          title: `${itineraryData.total_days}-Day ${itineraryData.destination} Trip`,
          destination: itineraryData.destination,
          itinerary_data: itineraryData,
          total_days: itineraryData.total_days,
          pacing: itineraryData.pacing,
        }),
      })
      setSaveStatus('saved')
      window.__refreshSidebarItineraries?.()
      setTimeout(() => setSaveStatus(null), 2000)
    } catch (err) {
      setSaveStatus('error')
      setTimeout(() => setSaveStatus(null), 2000)
    }
  }

  const handleDeletePlace = (dayNumber, slotIndex) => {
    setItineraryData(prev => {
      if (!prev) return prev;
      const newData = JSON.parse(JSON.stringify(prev)); // deep copy
      const dayIndex = newData.days.findIndex(d => d.day_number === dayNumber);
      if (dayIndex > -1) {
        newData.days[dayIndex].slots = newData.days[dayIndex].slots.filter((_, idx) => idx !== slotIndex);
      }
      return newData;
    });
  };

  const handleSearchPlaces = async () => {
    if (!searchQuery.trim()) return;
    setSearchLoading(true);
    try {
      const res = await fetch(`${API}/itinerary/search-similar`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ destination, query: searchQuery })
      });
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setSearchLoading(false);
    }
  };

  const handleConfirmAdd = async () => {
    if (selectedNewPlaces.length === 0) return;
    setIsEditingItinerary(true);
    setIsEditModalOpen(false);
    try {
      const res = await fetch(`${API}/itinerary/edit`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          existing_itinerary: itineraryData,
          added_places: selectedNewPlaces,
          removed_places: []
        })
      });
      if (res.ok) {
        const updatedItinerary = await res.json();
        setItineraryData(updatedItinerary);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsEditingItinerary(false);
      setSearchQuery('');
      setSearchResults(null);
      setSelectedNewPlaces([]);
    }
  };

  // ═══════ Saved Items ═══════
  const isItemSaved = (itemType, itemName) => {
    return savedItems.find(i => i.item_type === itemType && i.item_name === itemName)
  }

  const handleSaveItem = async (itemType, itemName, itemData) => {
    if (!accessToken) return
    try {
      const res = await fetch(`${API}/user/saved-items`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          item_type: itemType,
          item_name: itemName,
          destination: destination,
          item_data: itemData,
        }),
      })
      if (res.ok) {
        const newItem = await res.json()
        setSavedItems(prev => [newItem, ...prev.filter(i => i.id !== newItem.id)])
        window.__refreshSidebarSavedItems?.()

        // If event, show pin popover immediately
        if (itemType === 'event') {
          setPinPopover({ id: newItem.id, name: itemName })
        }
      }
    } catch (err) {
      console.error('Failed to save item:', err)
    }
  }

  const handleUnsaveItem = async (id) => {
    try {
      await fetch(`${API}/user/saved-items/${id}`, { method: 'DELETE', headers: authHeaders() })
      setSavedItems(prev => prev.filter(i => i.id !== id))
      window.__refreshSidebarSavedItems?.()
    } catch (err) {
      console.error('Failed to unsave item:', err)
    }
  }

  const handlePinItem = async (id, day) => {
    try {
      const res = await fetch(`${API}/user/saved-items/${id}/pin`, {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({ pinned_day: day ? Number(day) : null }),
      })
      if (res.ok) {
        const updated = await res.json()
        setSavedItems(prev => prev.map(i => i.id === id ? updated : i))
        setPinPopover(null)
        window.__refreshSidebarSavedItems?.()
      }
    } catch (err) {
      console.error('Failed to pin item:', err)
    }
  }

  async function sendDirectMessage(text, skipAppend = false, forceIntent = null, overrideData = null) {
    if (!skipAppend) {
      const userMsg = { role: 'user', content: text }
      setChatHistory(prev => [...prev, userMsg])
      setLastMessage(text)
      setLastIntent(forceIntent)
    }
    setLoading(true)
    let wasMissingInfo = false
    try {
      const dest = overrideData?.destination || destination
      const payload = {
        message: text,
        intent: forceIntent,
        destination: (dest && dest !== 'Explore') ? dest : null,
        budget: overrideData?.budget ? Number(overrideData.budget) : (budget ? Number(budget) : null),
        session_id: sessionId,
        traveler_type: overrideData?.traveler_type || travelerType || null,
        cuisine: cuisine || null,
        adults: overrideData?.adults ? Number(overrideData.adults) : (adults ? Number(adults) : null),
        check_in: overrideData?.check_in || checkIn || null,
        check_out: overrideData?.check_out || checkOut || null,
        start_location: overrideData?.start_location || startLocation || null,
        end_location: overrideData?.end_location || endLocation || null,
        travel_mode: travelMode || null,
        num_days: overrideData?.num_days ? Number(overrideData.num_days) : (numDays ? Number(numDays) : null),
        pacing: overrideData?.pacing || pacing || null,
        meal_preference: mealPreference || null,
        crowd_aware: crowdAware,
        crowd_precision: crowdAware ? crowdPrecision : null,
        weather_aware: weatherAware,
        interests: interests || null,
        activity_level: activityLevel || null,
        kids_friendly: kidsFriendly || null,
        dietary_restrictions: dietaryRestrictions || null,
        conversation_history: chatHistory
          .filter(m => m.content)
          .map(m => ({ role: m.role === 'ai' ? 'assistant' : m.role, content: m.content }))
      }

      const res = await fetch(`${API}/chat/stream`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let streamedText = ''
      let firstTokenReceived = false

      // Add placeholder AI message that we'll update with streamed tokens
      const aiMsgIndex = { current: -1 }
      setChatHistory(prev => {
        aiMsgIndex.current = prev.length
        return [...prev, { role: 'ai', content: '', streaming: true }]
      })

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Parse SSE events from buffer
        const lines = buffer.split('\n')
        buffer = ''

        let eventType = 'token'
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i]

          if (line.startsWith('event: ')) {
            eventType = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6)
            try {
              const eventData = JSON.parse(jsonStr)

              if (eventType === 'token') {
                if (!firstTokenReceived) {
                  firstTokenReceived = true
                  setLoading(false)
                }
                streamedText += eventData.text || ''
                // Update the AI message content with accumulated text
                const currentText = streamedText
                setChatHistory(prev => {
                  const updated = [...prev]
                  if (aiMsgIndex.current >= 0 && updated[aiMsgIndex.current]) {
                    updated[aiMsgIndex.current] = { ...updated[aiMsgIndex.current], content: currentText }
                  }
                  return updated
                })
              } else if (eventType === 'done') {
                // Process structured data from done event
                const data = eventData

                if (data.missing_info && data.missing_info.length > 0) {
                  // Remove the streaming AI message and show missing info modal
                  setChatHistory(prev => prev.filter((_, idx) => idx !== aiMsgIndex.current))
                  setMissingInfo(data.missing_info)
                  setLastMessage(text)
                  // Save the detected intent so resubmission uses it as forced_intent
                  // (prevents classify_intent from re-running and resetting fields)
                  if (data.intent) setLastIntent(data.intent)
                  setLoading(false)
                  wasMissingInfo = true
                  return
                }

                // Use full response text from done event (may differ from streamed if non-streamable)
                const finalText = data.response || streamedText || "I've updated your recommendations on the right."

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
                } else if (data.directions && data.directions.length > 0) {
                  setLatestData({ type: 'directions_recommendation', results: data.directions })
                  setActiveTab('Directions')
                } else if (data.itinerary) {
                  setItineraryData(data.itinerary)
                  setActiveDay(1)
                  setActiveTab('Itinerary')
                  if (currentView === 'wizard') {
                    setCurrentView('itinerary_only')
                  }
                }

                if (data.place_info) {
                  setDestination(data.place_info.name)
                }

                // Finalize the AI message with full text and action prompts
                setChatHistory(prev => {
                  const updated = [...prev]
                  if (aiMsgIndex.current >= 0 && updated[aiMsgIndex.current]) {
                    updated[aiMsgIndex.current] = {
                      role: 'ai',
                      content: finalText,
                      streaming: false,
                      show_review_prompt: data.show_review_prompt,
                      show_attractions_prompt: data.show_attractions_prompt,
                      show_restaurants_prompt: data.show_restaurants_prompt,
                      show_events_prompt: data.show_events_prompt,
                      ...(data.itinerary && { itinerary: data.itinerary })
                    }
                  }
                  const newHistory = [...updated]
                  saveChatSession(newHistory, data.place_info?.name || destination)
                  return newHistory
                })
              } else if (eventType === 'error') {
                setChatHistory(prev => {
                  const updated = [...prev]
                  if (aiMsgIndex.current >= 0 && updated[aiMsgIndex.current]) {
                    updated[aiMsgIndex.current] = { role: 'ai', content: eventData.message || 'Something went wrong.' }
                  }
                  return updated
                })
              }
            } catch {
              // Incomplete JSON, put line back in buffer
              buffer = lines.slice(i).join('\n')
              break
            }
            eventType = 'token' // reset for next event
          } else if (line === '') {
            // Empty line = end of event, reset
            eventType = 'token'
          } else {
            // Incomplete line, keep in buffer
            buffer = line + '\n' + lines.slice(i + 1).join('\n')
            break
          }
        }
      }
    } catch (err) {
      console.error('Stream error:', err)
      setChatHistory(prev => [...prev, { role: 'ai', content: 'Sorry, I failed to connect to the backend.' }])
    } finally {
      setLoading(false)
      // Reset per-query preferences so next search prompts fresh, UNLESS we need missing info
      if (!wasMissingInfo) {
        setBudget('')
        setTravelerType('')
        setCuisine('')
        setAdults(2)
        setCheckIn('')
        setCheckOut('')
        setStartLocation('')
        setEndLocation('')
        setTravelMode('')
        setNumDays('')
        setPacing('')
        setMealPreference('')
        setCrowdAware(null)
        setWeatherAware(null)
        setInterests('')
        setActivityLevel('')
        setKidsFriendly(false)
        setDietaryRestrictions('')
      }
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!message.trim()) return
    const text = message
    setMessage('')
    await sendDirectMessage(text)
  }

  const handleMissingInfoSubmit = (e) => {
    e.preventDefault()
    setMissingInfo(null)
    sendDirectMessage(lastMessage, true, lastIntent) // skip appending user message again
  }

  const handleReviewRequest = async (placeName) => {
    setLoading(true)
    const userMsg = { role: 'user', content: `What do real users say about ${placeName}?` }
    setChatHistory(prev => [...prev, userMsg])
    try {
      const res = await fetch(`${API}/chat/summarize-place?place_name=${encodeURIComponent(placeName)}`, {
        method: 'POST',
        headers: authHeaders()
      })
      const data = await res.json()
      const aiMsg = { role: 'ai', content: data.response }
      setChatHistory(prev => {
        const newHistory = [...prev, aiMsg]
        saveChatSession(newHistory, destination)
        return newHistory
      })
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'ai', content: 'Failed to fetch reviews.' }])
    } finally {
      setLoading(false)
    }
  }

  const handleHotelReviewRequest = async (hotelName, propertyToken) => {
    setLoading(true)
    const userMsg = { role: 'user', content: `Summarize reviews for ${hotelName}` }
    setChatHistory(prev => [...prev, userMsg])
    try {
      const res = await fetch(`${API}/chat/summarize-hotel?hotel_name=${encodeURIComponent(hotelName)}&property_token=${propertyToken}`, {
        method: 'POST',
        headers: authHeaders()
      })
      const data = await res.json()
      const aiMsg = { role: 'ai', content: data.response }
      setChatHistory(prev => {
        const newHistory = [...prev, aiMsg]
        saveChatSession(newHistory, destination)
        return newHistory
      })
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'ai', content: 'Failed to fetch reviews for this hotel.' }])
    } finally {
      setLoading(false)
    }
  }

  const handleAttractionReviewRequest = async (attractionName, dataId) => {
    setLoading(true)
    const userMsg = { role: 'user', content: `Summarize reviews for ${attractionName}` }
    setChatHistory(prev => [...prev, userMsg])
    try {
      const res = await fetch(`${API}/chat/summarize-attraction?attraction_name=${encodeURIComponent(attractionName)}&data_id=${encodeURIComponent(dataId)}`, {
        method: 'POST',
        headers: authHeaders()
      })
      const data = await res.json()
      const aiMsg = { role: 'ai', content: data.response }
      setChatHistory(prev => {
        const newHistory = [...prev, aiMsg]
        saveChatSession(newHistory, destination)
        return newHistory
      })
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'ai', content: 'Failed to fetch reviews for this attraction.' }])
    } finally {
      setLoading(false)
    }
  }

  const handleRestaurantReviewRequest = async (restaurantName, dataId) => {
    setLoading(true)
    const userMsg = { role: 'user', content: `Summarize reviews for ${restaurantName}` }
    setChatHistory(prev => [...prev, userMsg])
    try {
      const res = await fetch(`${API}/chat/summarize-restaurant?restaurant_name=${encodeURIComponent(restaurantName)}&data_id=${encodeURIComponent(dataId)}`, {
        method: 'POST',
        headers: authHeaders()
      })
      const data = await res.json()
      const aiMsg = { role: 'ai', content: data.response }
      setChatHistory(prev => {
        const newHistory = [...prev, aiMsg]
        saveChatSession(newHistory, destination)
        return newHistory
      })
    } catch (err) {
      setChatHistory(prev => [...prev, { role: 'ai', content: 'Failed to fetch reviews for this restaurant.' }])
    } finally {
      setLoading(false)
    }
  }

  if (authLoading) {
    return (
      <div className="app-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ color: 'var(--text-secondary)', fontSize: '1.1rem' }}>Loading...</div>
      </div>
    )
  }

  if (!user) {
    if (showLogin) {
      return <LoginPage onBack={() => setShowLogin(false)} />
    }
    return <LandingPage onGetStarted={() => setShowLogin(true)} />
  }

  const todayDateStr = new Date().toISOString().split('T')[0]
  const tomorrowDate = new Date()
  tomorrowDate.setDate(tomorrowDate.getDate() + 1)
  const tomorrowDateStr = tomorrowDate.toISOString().split('T')[0]

  return (
    <div className="app-container">
      {/* Global Background Orbs */}
      <div className="landing-bg-orb landing-bg-orb-1" style={{ opacity: 0.15 }}></div>
      <div className="landing-bg-orb landing-bg-orb-2" style={{ opacity: 0.15 }}></div>
      <div className="landing-bg-orb login-bg-orb-3" style={{ opacity: 0.1 }}></div>

      {currentView === 'dashboard' && (
        <Dashboard onSelect={(view) => setCurrentView(view)} />
      )}

      {currentView === 'wizard' && (
        <ItineraryWizard
          onCancel={() => setCurrentView('dashboard')}
          onFinish={(wizardData) => {
            setDestination(wizardData.destination);
            setStartLocation(wizardData.start_location);
            setCheckIn(wizardData.check_in);
            setNumDays(wizardData.num_days);

            // Calculate check_out for backend compat
            const checkInDate = new Date(wizardData.check_in);
            checkInDate.setDate(checkInDate.getDate() + (parseInt(wizardData.num_days) || 1) - 1);
            const computedCheckOut = checkInDate.toISOString().split('T')[0];
            setCheckOut(computedCheckOut);

            // Set preferences from wizard to state
            setMealPreference(wizardData.meal_preference);
            setCrowdAware(wizardData.crowd_aware);
            setCrowdPrecision(wizardData.crowd_precision);
            setWeatherAware(wizardData.weather_aware);
            setInterests(wizardData.interests);
            setActivityLevel(wizardData.activity_level);
            setCuisine(wizardData.cuisine);
            setKidsFriendly(wizardData.kids_friendly);

            setTravelerType(wizardData.traveler_type);
            setAdults(wizardData.adults);
            setBudget(wizardData.budget);
            setPacing(wizardData.pacing);
            setCurrentView('itinerary_only');

            const prompt = `Plan a trip to ${wizardData.destination} for ${wizardData.traveler_type} (${wizardData.adults} adults) starting on ${wizardData.check_in} for ${wizardData.num_days} days. Budget: ${wizardData.budget}. Pacing: ${wizardData.pacing}.`;
            const enrichedData = {
              ...wizardData,
              check_out: computedCheckOut,
            };
            sendDirectMessage(prompt, false, "itinerary_search", enrichedData);
          }}
        />
      )}

      {(currentView === 'chat' || currentView === 'itinerary_only') && (
        <>
          <Sidebar
            collapsed={sidebarCollapsed}
            onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
            onNewChat={handleNewChat}
            onLoadSession={handleLoadSession}
            onLoadItinerary={handleLoadItinerary}
            currentSessionId={sessionId}
            accessToken={accessToken}
          />
          <div className="main-wrapper">
            {missingInfo && (
              <div className="modal-overlay">
                <div className="modal-content">
                  <h3>I need a few more details! 🌍</h3>
                  <p style={{ color: 'var(--text-secondary)', marginBottom: '16px', fontSize: '0.9rem' }}>To give you the best recommendations, please fill in:</p>
                  <form onSubmit={handleMissingInfoSubmit} className="missing-info-form">
                    {missingInfo.includes('dates') && (
                      <div className="form-group">
                        <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                          <button
                            type="button"
                            onClick={() => { setCheckIn(todayDateStr); setCheckOut(tomorrowDateStr); }}
                            style={{ padding: '6px 12px', fontSize: '0.85rem', borderRadius: '4px', background: 'var(--surface-color)', border: '1px solid var(--border-color)', color: 'var(--text-primary)', cursor: 'pointer' }}
                          >
                            Today & Tomorrow
                          </button>
                          <button
                            type="button"
                            onClick={() => { setCheckIn(tomorrowDateStr); const next = new Date(tomorrowDate); next.setDate(next.getDate() + 1); setCheckOut(next.toISOString().split('T')[0]); }}
                            style={{ padding: '6px 12px', fontSize: '0.85rem', borderRadius: '4px', background: 'var(--surface-color)', border: '1px solid var(--border-color)', color: 'var(--text-primary)', cursor: 'pointer' }}
                          >
                            Tomorrow
                          </button>
                        </div>
                        <label>Check-in Date</label>
                        <input type="date" value={checkIn} min={todayDateStr} onChange={e => setCheckIn(e.target.value)} required />
                        <label>Check-out Date</label>
                        <input type="date" value={checkOut} min={checkIn || todayDateStr} onChange={e => setCheckOut(e.target.value)} required />
                      </div>
                    )}
                    {missingInfo.includes('destination') && (
                      <div className="form-group">
                        <label>Where do you want to go?</label>
                        <input type="text" value={destination} onChange={e => setDestination(e.target.value)} placeholder="e.g. Kochi, Paris, Tokyo" required />
                      </div>
                    )}
                    {missingInfo.includes('traveler_type') && (
                      <div className="form-group">
                        <label>Who are you traveling with?</label>
                        <select value={travelerType} onChange={e => setTravelerType(e.target.value)} required>
                          <option value="" disabled>Select traveler type...</option>
                          <option value="solo">Solo</option>
                          <option value="couple">Couple</option>
                          <option value="family">Family</option>
                          <option value="business">Business</option>
                          <option value="budget">Budget Backpacker</option>
                        </select>
                        <label style={{ marginTop: '8px' }}>Number of Adults</label>
                        <input type="number" value={adults} onChange={e => setAdults(e.target.value)} min="1" />
                      </div>
                    )}
                    {missingInfo.includes('budget') && (
                      <div className="form-group">
                        <label>Target Budget (₹)</label>
                        <input type="number" value={budget} onChange={e => setBudget(e.target.value)} required />
                      </div>
                    )}
                    {missingInfo.includes('cuisine') && (
                      <div className="form-group">
                        <label>Cuisine Preference</label>
                        <input type="text" value={cuisine} onChange={e => setCuisine(e.target.value)} placeholder="e.g. Italian, Mexican, Seafood" required />
                      </div>
                    )}
                    {missingInfo.includes('start_location') && (
                      <div className="form-group">
                        <label>Start Location</label>
                        <input type="text" value={startLocation} onChange={e => setStartLocation(e.target.value)} placeholder="e.g. JFK Airport" required />
                      </div>
                    )}
                    {missingInfo.includes('end_location') && (
                      <div className="form-group">
                        <label>End Location</label>
                        <input type="text" value={endLocation} onChange={e => setEndLocation(e.target.value)} placeholder="e.g. Times Square" required />
                      </div>
                    )}
                    {missingInfo.includes('travel_mode') && (
                      <div className="form-group">
                        <label>Travel Mode</label>
                        <select value={travelMode} onChange={e => setTravelMode(e.target.value)} required>
                          <option value="" disabled>Select mode...</option>
                          <option value="driving">Driving 🚗</option>
                          <option value="transit">Transit 🚆</option>
                          <option value="walking">Walking 🚶</option>
                          <option value="flight">Flight ✈️</option>
                        </select>
                      </div>
                    )}
                    {missingInfo.includes('num_days') && (
                      <div className="form-group">
                        <label>How many days?</label>
                        <input type="number" value={numDays} onChange={e => setNumDays(e.target.value)} min="1" max="14" required />
                      </div>
                    )}
                    {missingInfo.includes('pacing') && (
                      <div className="form-group">
                        <label>Trip Pacing</label>
                        <select value={pacing} onChange={e => setPacing(e.target.value)} required>
                          <option value="" disabled>Select pacing...</option>
                          <option value="relaxed">🍃 Relaxed (2-3 stops/day)</option>
                          <option value="packed">🏃 Packed (5-6 stops/day)</option>
                        </select>
                      </div>
                    )}
                    {missingInfo.includes('itinerary_start_location') && (
                      <div className="form-group">
                        <label>Where are you starting from?</label>
                        <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', margin: '4px 0 8px' }}>This helps us plan your Day 1 starting from the nearest attractions.</p>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <input
                            type="text"
                            value={startLocation}
                            onChange={e => setStartLocation(e.target.value)}
                            placeholder="e.g. Kochi, Coimbatore"
                            style={{ flex: 1 }}
                          />
                          <button
                            type="button"
                            onClick={() => {
                              setStartLocation('__skip__')
                            }}
                            style={{
                              background: 'rgba(255,255,255,0.05)',
                              border: '1px solid rgba(255,255,255,0.15)',
                              color: 'var(--text-secondary)',
                              padding: '8px 14px',
                              borderRadius: '8px',
                              cursor: 'pointer',
                              fontSize: '0.85rem',
                              whiteSpace: 'nowrap'
                            }}
                          >
                            Skip ⏭️
                          </button>
                        </div>
                      </div>
                    )}
                    {missingInfo.includes('meal_preference') && (
                      <div className="form-group">
                        <label>Meal Scheduling</label>
                        <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', margin: '4px 0 8px' }}>How should restaurants be placed in your itinerary?</p>
                        <select value={mealPreference} onChange={e => setMealPreference(e.target.value)} required>
                          <option value="" disabled>Select preference...</option>
                          <option value="fixed">🕐 Fixed Times (Breakfast → Lunch → Dinner)</option>
                          <option value="flexible">📍 Flexible (restaurants placed on the route)</option>
                        </select>
                      </div>
                    )}
                    {missingInfo.includes('crowd_aware') && (
                      <div className="form-group">
                        <label>👥 Crowd-Aware Planning</label>
                        <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', margin: '4px 0 8px' }}>Should we check how crowded each place is and factor it into your itinerary?</p>
                        <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                          <button
                            type="button"
                            onClick={() => setCrowdAware(true)}
                            style={{
                              flex: 1,
                              padding: '10px',
                              borderRadius: '8px',
                              border: crowdAware === true ? '2px solid #3b82f6' : '1px solid rgba(255,255,255,0.15)',
                              background: crowdAware === true ? 'rgba(59, 130, 246, 0.15)' : 'rgba(255,255,255,0.05)',
                              color: crowdAware === true ? '#60a5fa' : 'var(--text-secondary)',
                              cursor: 'pointer',
                              fontWeight: crowdAware === true ? '600' : '400',
                              fontSize: '0.9rem'
                            }}
                          >
                            ✅ Yes, avoid crowds
                          </button>
                          <button
                            type="button"
                            onClick={() => { setCrowdAware(false); setCrowdPrecision('approximate'); }}
                            style={{
                              flex: 1,
                              padding: '10px',
                              borderRadius: '8px',
                              border: crowdAware === false ? '2px solid #3b82f6' : '1px solid rgba(255,255,255,0.15)',
                              background: crowdAware === false ? 'rgba(59, 130, 246, 0.15)' : 'rgba(255,255,255,0.05)',
                              color: crowdAware === false ? '#60a5fa' : 'var(--text-secondary)',
                              cursor: 'pointer',
                              fontWeight: crowdAware === false ? '600' : '400',
                              fontSize: '0.9rem'
                            }}
                          >
                            ⏭️ No, skip it
                          </button>
                        </div>
                        {crowdAware === true && (
                          <div style={{ marginTop: '8px' }}>
                            <label style={{ fontSize: '0.85rem' }}>Crowd Data Precision</label>
                            <p style={{ color: 'var(--text-secondary)', fontSize: '0.78rem', margin: '4px 0 8px' }}>Precise uses real-time data (uses API credits). Approximate lets AI estimate based on patterns.</p>
                            <select value={crowdPrecision} onChange={e => setCrowdPrecision(e.target.value)}>
                              <option value="approximate">🤖 Approximate (AI estimates, free)</option>
                              <option value="precise">📊 Precise (real-time SerpAPI data)</option>
                            </select>
                          </div>
                        )}
                      </div>
                    )}
                    {missingInfo.includes('weather_aware') && (
                      <div className="form-group">
                        <label>🌤️ Weather-Aware Planning</label>
                        <p style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', margin: '4px 0 8px' }}>Should we check the weather forecast and adjust your itinerary accordingly?</p>
                        <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
                          <button
                            type="button"
                            onClick={() => setWeatherAware(true)}
                            style={{
                              flex: 1,
                              padding: '10px',
                              borderRadius: '8px',
                              border: weatherAware === true ? '2px solid #3b82f6' : '1px solid rgba(255,255,255,0.15)',
                              background: weatherAware === true ? 'rgba(59, 130, 246, 0.15)' : 'rgba(255,255,255,0.05)',
                              color: weatherAware === true ? '#60a5fa' : 'var(--text-secondary)',
                              cursor: 'pointer',
                              fontWeight: weatherAware === true ? '600' : '400',
                              fontSize: '0.9rem'
                            }}
                          >
                            ✅ Yes, check weather
                          </button>
                          <button
                            type="button"
                            onClick={() => setWeatherAware(false)}
                            style={{
                              flex: 1,
                              padding: '10px',
                              borderRadius: '8px',
                              border: weatherAware === false ? '2px solid #3b82f6' : '1px solid rgba(255,255,255,0.15)',
                              background: weatherAware === false ? 'rgba(59, 130, 246, 0.15)' : 'rgba(255,255,255,0.05)',
                              color: weatherAware === false ? '#60a5fa' : 'var(--text-secondary)',
                              cursor: 'pointer',
                              fontWeight: weatherAware === false ? '600' : '400',
                              fontSize: '0.9rem'
                            }}
                          >
                            ⏭️ No, skip it
                          </button>
                        </div>
                      </div>
                    )}

                    {(missingInfo.includes('num_days') || missingInfo.includes('pacing') || missingInfo.includes('meal_preference')) && (
                      <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                        <h4 style={{ margin: '0 0 12px 0', fontSize: '0.95rem', color: '#fff' }}>✨ Optional Preferences</h4>

                        <div className="form-group">
                          <label>Specific Interests / Vibes</label>
                          <input
                            type="text"
                            value={interests}
                            onChange={e => setInterests(e.target.value)}
                            placeholder="e.g. history, art, nature, nightlife"
                          />
                        </div>

                        <div className="form-group" style={{ display: 'flex', gap: '12px' }}>
                          <div style={{ flex: 1 }}>
                            <label>Activity Level</label>
                            <select value={activityLevel} onChange={e => setActivityLevel(e.target.value)}>
                              <option value="">Any</option>
                              <option value="high">High (Hiking, walking)</option>
                              <option value="low">Low (Museums, scenic drives)</option>
                            </select>
                          </div>

                          <div style={{ flex: 1 }}>
                            <label>Dietary Restrictions</label>
                            <input
                              type="text"
                              value={dietaryRestrictions}
                              onChange={e => setDietaryRestrictions(e.target.value)}
                              placeholder="e.g. Vegan, Halal"
                            />
                          </div>
                        </div>

                        <div className="form-group">
                          <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', margin: '4px 0' }}>
                            <input
                              type="checkbox"
                              checked={kidsFriendly}
                              onChange={e => setKidsFriendly(e.target.checked)}
                              style={{ width: '16px', height: '16px', margin: 0 }}
                            />
                            <span>👨‍👩‍👧‍👦 Prioritize Kids/Family Friendly Places</span>
                          </label>
                        </div>
                      </div>
                    )}

                    <button type="submit" className="modal-btn" style={{ marginTop: '16px', width: '100%', background: '#3b82f6', color: 'white', padding: '10px', borderRadius: '8px', border: 'none', fontWeight: 'bold', cursor: 'pointer' }}>Apply & Continue</button>
                  </form>
                </div>
              </div>
            )}

            {currentView === 'itinerary_only' ? (
              <ItineraryView
                itineraryData={itineraryData}
                loading={loading}
                loadingMessage={loadingMessage}
                onBack={() => setCurrentView('dashboard')}
                onSave={handleSaveItinerary}
                saveStatus={saveStatus}
                onDeletePlace={handleDeletePlace}
                onAddPlace={() => setIsEditModalOpen(true)}
              />
            ) : (
              <>
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
                          {msg.role === 'ai' ? (
                            <div className={`markdown-content${msg.streaming ? ' streaming-cursor' : ''}`}>
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                            </div>
                          ) : (
                            msg.content
                          )}
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
                          {msg.role === 'ai' && msg.itinerary && (
                            <div style={{ marginTop: '12px' }}>
                              <button
                                onClick={() => {
                                  setItineraryData(msg.itinerary)
                                  setActiveTab('Itinerary')
                                }}
                                style={{ background: 'rgba(168, 85, 247, 0.2)', border: '1px solid #a855f7', color: '#c084fc', padding: '6px 12px', borderRadius: '8px', cursor: 'pointer', fontSize: '0.8rem' }}
                              >
                                🗺️ View Itinerary
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                      {loading && (
                        <div className="message ai loading-bubble">
                          <div className="modern-loader-container">
                            <div className="modern-spinner"></div>
                            <span className="loading-text">{loadingMessage}</span>
                          </div>
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
                      <button className={`tab ${activeTab === 'Hotels' ? 'active' : ''}`} onClick={() => setActiveTab('Hotels')}>Hotels</button>
                      <button className={`tab ${activeTab === 'Places' ? 'active' : ''}`} onClick={() => setActiveTab('Places')}>Attractions</button>
                      <button className={`tab ${activeTab === 'Food' ? 'active' : ''}`} onClick={() => setActiveTab('Food')}>Food</button>
                      <button className={`tab ${activeTab === 'Events' ? 'active' : ''}`} onClick={() => setActiveTab('Events')}>Events</button>
                      <button className={`tab ${activeTab === 'Directions' ? 'active' : ''}`} onClick={() => setActiveTab('Directions')}>Directions</button>
                      <button className={`tab ${activeTab === 'Itinerary' ? 'active' : ''}`} onClick={() => setActiveTab('Itinerary')}>Itinerary</button>
                    </div>

                    {activeTab === 'Directions' && latestData?.type === 'directions_recommendation' && (
                      <div>
                        <h2 className="section-title">Best Routes to {latestData.results.length > 0 ? latestData.results[0].mode : "Destination"}</h2>
                        <div className="cards-container">
                          {latestData.results.map((dir, i) => (
                            <div
                              key={i}
                              className="hotel-card"
                              style={{
                                borderLeft: `4px solid ${dir.route_type.includes('Fastest') ? '#10b981' : dir.route_type.includes('Cheapest') ? '#f59e0b' : '#3b82f6'}`,
                                cursor: 'pointer'
                              }}
                              onClick={() => setExpandedRoute(expandedRoute === i ? null : i)}
                            >
                              <div className="card-header" style={{ marginBottom: '8px' }}>
                                <div className="card-title" style={{ fontSize: '1.1rem' }}>
                                  {dir.route_type}
                                  <span style={{ fontSize: '0.8rem', marginLeft: '10px', color: 'var(--primary)', fontWeight: 'normal' }}>
                                    {expandedRoute === i ? '▲ Hide Details' : '▼ View Steps'}
                                  </span>
                                </div>
                                <div className="card-price">
                                  <div className="price-val" style={{ color: 'var(--text-main)' }}>{dir.duration}</div>
                                </div>
                              </div>
                              <div className="card-subtitle" style={{ marginBottom: '16px', color: 'var(--primary)' }}>
                                {dir.distance} • {dir.transfers > 0 ? `${dir.transfers} transfers` : 'Direct'}
                              </div>
                              <p className="card-summary">{dir.summary}</p>

                              {expandedRoute === i && dir.steps && (
                                <div className="route-steps" style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.1)' }}>
                                  <h4 style={{ marginBottom: '12px', color: 'var(--text-main)' }}>Step-by-step:</h4>
                                  <ul style={{ listStyleType: 'none', paddingLeft: '0', margin: '0' }}>
                                    {dir.steps.map((step, idx) => (
                                      <li key={idx} style={{ marginBottom: '8px', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                                        {step}
                                      </li>
                                    ))}
                                  </ul>
                                </div>
                              )}

                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px' }}>
                                {dir.price ? (
                                  <div className="price-tag" style={{ fontSize: '0.85rem' }}>
                                    Est. Cost: {dir.price}
                                  </div>
                                ) : <div></div>}

                                {dir.link && (
                                  <a
                                    href={dir.link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="modal-btn"
                                    style={{ textDecoration: 'none', background: '#10b981', color: 'white', padding: '6px 12px', borderRadius: '6px', fontSize: '0.85rem', fontWeight: 'bold' }}
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    Open in Google Maps 🗺️
                                  </a>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {activeTab === 'Itinerary' && itineraryData && (
                      <div className="itinerary-container">
                        <div className="itinerary-header">
                          <h2 className="section-title" style={{ marginBottom: '4px' }}>
                            🗺️ {itineraryData.total_days}-Day {itineraryData.pacing === 'packed' ? '🏃 Packed' : '🍃 Relaxed'} Itinerary
                          </h2>
                          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', margin: '0 0 16px 0' }}>
                            {itineraryData.destination}
                          </p>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <button
                              className="save-itinerary-btn"
                              onClick={() => setIsEditModalOpen(true)}
                            >
                              ➕ Add Place
                            </button>
                            <button
                              className="save-itinerary-btn"
                              onClick={handleSaveItinerary}
                              disabled={saveStatus === 'saving'}
                            >
                              {saveStatus === 'saving' ? '⏳ Saving...' : saveStatus === 'saved' ? '✅ Saved!' : saveStatus === 'error' ? '❌ Failed' : '💾 Save Itinerary'}
                            </button>
                          </div>
                        </div>

                        {isEditingItinerary && (
                          <div style={{ background: 'rgba(59, 130, 246, 0.1)', border: '1px solid #3b82f6', color: '#60a5fa', padding: '12px', borderRadius: '8px', marginBottom: '16px', textAlign: 'center' }}>
                            <div className="modern-spinner" style={{ width: '20px', height: '20px', borderTopColor: '#60a5fa', display: 'inline-block', verticalAlign: 'middle', marginRight: '8px' }}></div>
                            Re-optimizing your itinerary with new places...
                          </div>
                        )}

                        {/* Day tabs */}
                        <div className="day-tabs">
                          {itineraryData.days.map(day => (
                            <button
                              key={day.day_number}
                              className={`day-tab ${activeDay === day.day_number ? 'active' : ''}`}
                              onClick={() => setActiveDay(day.day_number)}
                            >
                              <span className="day-tab-num">Day {day.day_number}</span>
                              <span className="day-tab-theme">{day.theme}</span>
                            </button>
                          ))}
                        </div>

                        {/* Timeline for active day */}
                        {itineraryData.days.filter(d => d.day_number === activeDay).map(day => (
                          <div key={day.day_number} className="timeline">
                            {day.weather_summary && (
                              <div style={{ background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.2)', padding: '12px 16px', borderRadius: '8px', marginBottom: '24px' }}>
                                <div style={{ fontWeight: 'bold', color: '#60a5fa', marginBottom: '4px', fontSize: '0.95rem' }}>
                                  {day.weather_summary}
                                </div>
                                {day.weather_tip && (
                                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                                    💡 {day.weather_tip}
                                  </div>
                                )}
                              </div>
                            )}
                            {day.slots.map((slot, idx) => {
                              const categoryColors = {
                                attraction: '#14b8a6',
                                restaurant: '#f59e0b',
                                hotel: '#3b82f6',
                                travel: '#8b5cf6',
                                activity: '#ec4899'
                              }
                              const categoryIcons = {
                                attraction: '🏛️',
                                restaurant: '🍽️',
                                hotel: '🏨',
                                travel: '🚗',
                                activity: '🎯'
                              }
                              const color = categoryColors[slot.category] || '#6b7280'
                              const icon = categoryIcons[slot.category] || '📍'

                              return (
                                <div key={idx} className="timeline-item">
                                  <div className="timeline-dot" style={{ background: color }}>
                                    <span style={{ fontSize: '0.75rem' }}>{icon}</span>
                                  </div>
                                  <div className="timeline-connector" style={{ borderColor: color + '40' }}></div>
                                  <div className="timeline-card">
                                    <div style={{ display: 'flex', gap: '16px' }}>
                                      <div style={{ flex: 1, minWidth: 0, position: 'relative' }}>
                                        <button
                                          onClick={() => handleDeletePlace(day.day_number, idx)}
                                          style={{
                                            position: 'absolute', right: 0, top: 0, background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '1.2rem', padding: '4px'
                                          }}
                                          title="Delete Place"
                                        >
                                          🗑️
                                        </button>
                                        <div className="timeline-time">
                                          <span className="time-label">{slot.time_label}</span>
                                          <span className="time-slot-badge" style={{ background: color + '20', color: color }}>
                                            {slot.time_slot}
                                          </span>
                                        </div>
                                        <h4 className="timeline-title">{slot.activity_name}</h4>
                                        <p className="timeline-desc">{slot.description}</p>
                                        <div className="timeline-meta">
                                          <span className="meta-tag">⏱️ {slot.duration_minutes} min</span>
                                          {slot.rating && <span className="meta-tag">⭐ {slot.rating}</span>}
                                          {slot.cost_estimate && <span className="meta-tag">💰 {slot.cost_estimate}</span>}
                                          {slot.crowd_status && slot.crowd_status.toLowerCase() !== 'unknown' && (() => {
                                            const cs = slot.crowd_status.toLowerCase()
                                            const isLow = cs.includes('not') || cs.includes('low') || cs.includes('quiet') || cs.includes('empty')
                                            const isMod = cs.includes('moderate') || cs.includes('medium') || cs.includes('average')
                                            const bgColor = isLow ? 'rgba(16, 185, 129, 0.2)' : isMod ? 'rgba(245, 158, 11, 0.2)' : 'rgba(239, 68, 68, 0.2)'
                                            const textColor = isLow ? '#34d399' : isMod ? '#fbbf24' : '#f87171'
                                            const emoji = isLow ? '🟢' : isMod ? '🟡' : '🔴'
                                            return (
                                              <span
                                                className="meta-tag"
                                                style={{
                                                  background: bgColor,
                                                  color: textColor,
                                                  fontWeight: '600',
                                                  border: `1px solid ${textColor}30`
                                                }}
                                              >
                                                {emoji} {slot.crowd_status}
                                              </span>
                                            )
                                          })()}
                                        </div>
                                      </div>
                                      <div style={{ width: '240px', aspectRatio: '16 / 9', flexShrink: 0, overflow: 'hidden', borderRadius: '8px' }}>
                                        <img
                                          src={slot.thumbnail || FALLBACK_IMAGES[slot.category?.toLowerCase()] || FALLBACK_IMAGES.default}
                                          alt={slot.activity_name}
                                          referrerPolicy="no-referrer"
                                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                          onError={(e) => { e.target.src = FALLBACK_IMAGES[slot.category?.toLowerCase()] || FALLBACK_IMAGES.default; e.target.onerror = null; }}
                                        />
                                      </div>
                                    </div>
                                    {slot.travel_to_next && (
                                      <div className="travel-connector">
                                        {slot.travel_to_next}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              )
                            })}
                          </div>
                        ))}
                      </div>
                    )}

                    {latestData?.type === 'hotel_recommendation' && activeTab === 'Hotels' ? (
                      <>
                        <div className="context-banner">
                          🎯 Best matches found in {destination} based on current availability.
                        </div>

                        <div className="section-title">Top Recommendations</div>

                        <div className="cards-container">
                          {latestData.results.map((hotel, idx) => (
                            <div key={idx} className="hotel-card">
                              <div className="card-image-container" style={{ cursor: 'zoom-in' }} onClick={() => setFullScreenImage(hotel.thumbnail || FALLBACK_IMAGES.hotel)}>
                                <img src={hotel.thumbnail || FALLBACK_IMAGES.hotel} alt={hotel.name} className="card-image" referrerPolicy="no-referrer" onError={(e) => { e.target.src = FALLBACK_IMAGES.hotel; e.target.onerror = null; }} />
                              </div>
                              <div className="card-header">
                                <div>
                                  <h3 className="card-title">
                                    <span style={{ color: '#f59e0b', marginRight: '6px' }}>★</span>
                                    {hotel.name}
                                  </h3>
                                  <div className="card-subtitle">{hotel.address || destination}</div>
                                </div>
                                <div className="card-actions" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>
                                  <button
                                    className={`save-item-btn ${isItemSaved('hotel', hotel.name) ? 'saved' : ''}`}
                                    onClick={() => {
                                      const saved = isItemSaved('hotel', hotel.name);
                                      if (saved) handleUnsaveItem(saved.id);
                                      else handleSaveItem('hotel', hotel.name, hotel);
                                    }}
                                    title={isItemSaved('hotel', hotel.name) ? 'Remove from Preferences' : 'Add to Preferences'}
                                  >
                                    {isItemSaved('hotel', hotel.name) ? '🔖' : '📑'}
                                  </button>
                                  <div className="card-price" style={{ textAlign: 'right' }}>
                                    <div className="price-val">₹{hotel.price}</div>
                                    <div className="price-tag">Per Night</div>
                                  </div>
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
                              <div className="card-image-container" style={{ cursor: 'zoom-in' }} onClick={() => setFullScreenImage(rest.thumbnail || FALLBACK_IMAGES.restaurant)}>
                                <img src={rest.thumbnail || FALLBACK_IMAGES.restaurant} alt={rest.name} className="card-image" referrerPolicy="no-referrer" onError={(e) => { e.target.src = FALLBACK_IMAGES.restaurant; e.target.onerror = null; }} />
                              </div>
                              <div className="card-header">
                                <div>
                                  <h3 className="card-title">
                                    <span style={{ color: '#ef4444', marginRight: '6px' }}>🍽️</span>
                                    {rest.name}
                                  </h3>
                                </div>
                                <div className="card-actions" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                  {rest.rating && (
                                    <div className="card-price" style={{ textAlign: 'right' }}>
                                      <div className="price-val">★ {rest.rating}</div>
                                      <div className="price-tag">{rest.reviews} Reviews</div>
                                    </div>
                                  )}
                                  <button
                                    className={`save-item-btn ${isItemSaved('restaurant', rest.name) ? 'saved' : ''}`}
                                    onClick={() => {
                                      const saved = isItemSaved('restaurant', rest.name);
                                      if (saved) handleUnsaveItem(saved.id);
                                      else handleSaveItem('restaurant', rest.name, rest);
                                    }}
                                    title={isItemSaved('restaurant', rest.name) ? 'Remove from Preferences' : 'Add to Preferences'}
                                  >
                                    {isItemSaved('restaurant', rest.name) ? '🔖' : '📑'}
                                  </button>
                                </div>
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
                              <div className="card-image-container" style={{ cursor: 'zoom-in' }} onClick={() => setFullScreenImage(attr.thumbnail || FALLBACK_IMAGES.attraction)}>
                                <img src={attr.thumbnail || FALLBACK_IMAGES.attraction} alt={attr.name} className="card-image" referrerPolicy="no-referrer" onError={(e) => { e.target.src = FALLBACK_IMAGES.attraction; e.target.onerror = null; }} />
                              </div>
                              <div className="card-header">
                                <div>
                                  <h3 className="card-title">
                                    <span style={{ color: '#10b981', marginRight: '6px' }}>🏛️</span>
                                    {attr.name}
                                  </h3>
                                </div>
                                <div className="card-actions" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                  {attr.rating && (
                                    <div className="card-price" style={{ textAlign: 'right' }}>
                                      <div className="price-val">★ {attr.rating}</div>
                                      <div className="price-tag">{attr.reviews} Reviews</div>
                                    </div>
                                  )}
                                  <button
                                    className={`save-item-btn ${isItemSaved('attraction', attr.name) ? 'saved' : ''}`}
                                    onClick={() => {
                                      const saved = isItemSaved('attraction', attr.name);
                                      if (saved) handleUnsaveItem(saved.id);
                                      else handleSaveItem('attraction', attr.name, attr);
                                    }}
                                    title={isItemSaved('attraction', attr.name) ? 'Remove from Preferences' : 'Add to Preferences'}
                                  >
                                    {isItemSaved('attraction', attr.name) ? '🔖' : '📑'}
                                  </button>
                                </div>
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
                              <div className="card-image-container" style={{ cursor: 'zoom-in' }} onClick={() => setFullScreenImage(evt.thumbnail || FALLBACK_IMAGES.event)}>
                                <img src={evt.thumbnail || FALLBACK_IMAGES.event} alt={evt.title} className="card-image" referrerPolicy="no-referrer" onError={(e) => { e.target.src = FALLBACK_IMAGES.event; e.target.onerror = null; }} />
                              </div>
                              <div className="card-header">
                                <div>
                                  <h3 className="card-title">
                                    <span style={{ color: '#8b5cf6', marginRight: '6px' }}>📅</span>
                                    {evt.title}
                                  </h3>
                                </div>
                                <button
                                  className={`save-item-btn ${isItemSaved('event', evt.title) ? 'saved' : ''}`}
                                  onClick={() => {
                                    const saved = isItemSaved('event', evt.title);
                                    if (saved) handleUnsaveItem(saved.id);
                                    else handleSaveItem('event', evt.title, evt);
                                  }}
                                  title={isItemSaved('event', evt.title) ? 'Remove from Preferences' : 'Add to Preferences'}
                                >
                                  {isItemSaved('event', evt.title) ? '🔖' : '📑'}
                                </button>
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
                        {activeTab === 'Hotels' && (
                          <>
                            <div style={{ fontSize: '3rem', marginBottom: '16px' }}>🏨</div>
                            <div style={{ fontWeight: '500', marginBottom: '16px' }}>Find the perfect place to stay</div>
                            <button className="empty-state-btn" onClick={() => sendDirectMessage("Find hotels for me", false, "hotel_search")}>Find Hotels</button>
                          </>
                        )}
                        {activeTab === 'Food' && (
                          <>
                            <div style={{ fontSize: '3rem', marginBottom: '16px' }}>🍽️</div>
                            <div style={{ fontWeight: '500', marginBottom: '16px' }}>Discover local cuisine</div>
                            <button className="empty-state-btn" onClick={() => sendDirectMessage("Find restaurants for me", false, "restaurant_search")}>Find Restaurants</button>
                          </>
                        )}
                        {activeTab === 'Places' && (
                          <>
                            <div style={{ fontSize: '3rem', marginBottom: '16px' }}>🏛️</div>
                            <div style={{ fontWeight: '500', marginBottom: '16px' }}>Explore top attractions</div>
                            <button className="empty-state-btn" onClick={() => sendDirectMessage("What are the top attractions?", false, "attraction_search")}>Discover Attractions</button>
                          </>
                        )}
                        {activeTab === 'Events' && (
                          <>
                            <div style={{ fontSize: '3rem', marginBottom: '16px' }}>🎫</div>
                            <div style={{ fontWeight: '500', marginBottom: '16px' }}>See what's happening</div>
                            <button className="empty-state-btn" onClick={() => sendDirectMessage("Find events and concerts", false, "event_search")}>Find Events</button>
                          </>
                        )}
                        {activeTab === 'Itinerary' && (
                          <>
                            <div style={{ fontSize: '3rem', marginBottom: '16px' }}>🗺️</div>
                            <div style={{ fontWeight: '500', marginBottom: '16px' }}>Plan your entire trip</div>
                            <button className="empty-state-btn" onClick={() => sendDirectMessage("Create a travel itinerary for me", false, "itinerary_search")}>Create Itinerary</button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                {/* Pin to Day Popover */}
                {pinPopover && (
                  <div className="modal-overlay" onClick={() => setPinPopover(null)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()} style={{ textAlign: 'center' }}>
                      <h3 style={{ fontSize: '1.5rem', marginBottom: '8px' }}>📌 Pin Event</h3>
                      <p style={{ color: 'var(--text-secondary)', marginBottom: '20px', fontSize: '0.9rem' }}>
                        Pin <strong>{pinPopover.name}</strong> to a specific day in your itinerary. The travel planner will schedule your day around this event.
                      </p>
                      <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', flexWrap: 'wrap' }}>
                        {[1, 2, 3, 4, 5].map(day => (
                          <button
                            key={day}
                            onClick={() => handlePinItem(pinPopover.id, day)}
                            style={{
                              background: 'var(--bg-darker)',
                              border: '1px solid var(--border-color)',
                              color: 'var(--text-main)',
                              padding: '12px 20px',
                              borderRadius: '8px',
                              cursor: 'pointer',
                              fontWeight: '600'
                            }}
                          >
                            Day {day}
                          </button>
                        ))}
                      </div>
                      <button
                        onClick={() => setPinPopover(null)}
                        style={{
                          marginTop: '20px',
                          background: 'transparent',
                          color: 'var(--text-secondary)',
                          border: 'none',
                          cursor: 'pointer',
                          textDecoration: 'underline'
                        }}
                      >
                        Skip for now
                      </button>
                    </div>
                  </div>
                )}

                {/* Edit Itinerary Modal */}
                {isEditModalOpen && (
                  <div className="modal-overlay" onClick={() => setIsEditModalOpen(false)}>
                    <div className="modal-content" onClick={e => e.stopPropagation()} style={{ width: '500px', maxWidth: '90vw', padding: '24px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                        <h3 style={{ fontSize: '1.4rem', margin: 0 }}>Add Place to Itinerary</h3>
                        <button onClick={() => setIsEditModalOpen(false)} style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '1.2rem' }}>✕</button>
                      </div>

                      <div style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
                        <input
                          type="text"
                          value={searchQuery}
                          onChange={e => setSearchQuery(e.target.value)}
                          placeholder="Search for a place..."
                          style={{ flex: 1, padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--bg-darker)', color: 'white' }}
                          onKeyDown={e => e.key === 'Enter' && handleSearchPlaces()}
                        />
                        <button
                          onClick={handleSearchPlaces}
                          disabled={searchLoading || !searchQuery.trim()}
                          style={{ background: '#3b82f6', color: 'white', border: 'none', padding: '0 20px', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}
                        >
                          {searchLoading ? 'Searching...' : 'Search'}
                        </button>
                      </div>

                      {searchResults && (
                        <div style={{ maxHeight: '60vh', overflowY: 'auto', paddingRight: '4px' }}>
                          {searchResults.exact_match && (
                            <div style={{ marginBottom: '24px' }}>
                              <h4 style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>Exact Match</h4>
                              {(() => {
                                const place = searchResults.exact_match;
                                const isSelected = selectedNewPlaces.some(p => p.name === place.name);
                                return (
                                  <div
                                    onClick={() => {
                                      if (isSelected) {
                                        setSelectedNewPlaces(prev => prev.filter(p => p.name !== place.name));
                                      } else {
                                        setSelectedNewPlaces(prev => [...prev, place]);
                                      }
                                    }}
                                    style={{
                                      display: 'flex', gap: '12px', padding: '12px', background: isSelected ? 'rgba(59, 130, 246, 0.1)' : 'var(--bg-darker)',
                                      border: isSelected ? '1px solid #3b82f6' : '1px solid var(--border-color)', borderRadius: '12px', cursor: 'pointer', alignItems: 'center'
                                    }}
                                  >
                                    <img src={place.thumbnail || FALLBACK_IMAGES.attraction} style={{ width: '60px', height: '60px', borderRadius: '8px', objectFit: 'cover' }} referrerPolicy="no-referrer" alt={place.name} onError={(e) => { e.target.src = FALLBACK_IMAGES.attraction; e.target.onerror = null; }} />
                                    <div style={{ flex: 1 }}>
                                      <div style={{ fontWeight: 'bold', fontSize: '1.05rem', color: isSelected ? '#60a5fa' : 'white' }}>{place.name}</div>
                                      {place.rating && <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>⭐ {place.rating}</div>}
                                    </div>
                                    <div style={{ width: '24px', height: '24px', borderRadius: '50%', border: isSelected ? 'none' : '2px solid var(--border-color)', background: isSelected ? '#3b82f6' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 'bold' }}>
                                      {isSelected ? '✓' : ''}
                                    </div>
                                  </div>
                                )
                              })()}
                            </div>
                          )}

                          {searchResults.similar_places && searchResults.similar_places.length > 0 && (
                            <div>
                              <h4 style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>Recommended Similar Places</h4>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                {searchResults.similar_places.map((place, idx) => {
                                  const isSelected = selectedNewPlaces.some(p => p.name === place.name);
                                  return (
                                    <div
                                      key={idx}
                                      onClick={() => {
                                        if (isSelected) {
                                          setSelectedNewPlaces(prev => prev.filter(p => p.name !== place.name));
                                        } else {
                                          setSelectedNewPlaces(prev => [...prev, place]);
                                        }
                                      }}
                                      style={{
                                        display: 'flex', gap: '12px', padding: '12px', background: isSelected ? 'rgba(59, 130, 246, 0.1)' : 'var(--bg-darker)',
                                        border: isSelected ? '1px solid #3b82f6' : '1px solid var(--border-color)', borderRadius: '12px', cursor: 'pointer', alignItems: 'center'
                                      }}
                                    >
                                      <img src={place.thumbnail || FALLBACK_IMAGES.attraction} style={{ width: '50px', height: '50px', borderRadius: '8px', objectFit: 'cover' }} referrerPolicy="no-referrer" alt={place.name} onError={(e) => { e.target.src = FALLBACK_IMAGES.attraction; e.target.onerror = null; }} />
                                      <div style={{ flex: 1 }}>
                                        <div style={{ fontWeight: 'bold', fontSize: '1rem', color: isSelected ? '#60a5fa' : 'white' }}>{place.name}</div>
                                        {place.rating && <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>⭐ {place.rating}</div>}
                                      </div>
                                      <div style={{ width: '24px', height: '24px', borderRadius: '50%', border: isSelected ? 'none' : '2px solid var(--border-color)', background: isSelected ? '#3b82f6' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 'bold' }}>
                                        {isSelected ? '✓' : ''}
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'flex-end', gap: '12px', borderTop: '1px solid var(--border-color)', paddingTop: '16px' }}>
                        <button onClick={() => setIsEditModalOpen(false)} style={{ background: 'transparent', color: 'white', border: '1px solid var(--border-color)', padding: '10px 16px', borderRadius: '8px', cursor: 'pointer' }}>Cancel</button>
                        <button
                          onClick={handleConfirmAdd}
                          disabled={selectedNewPlaces.length === 0}
                          style={{ background: '#3b82f6', color: 'white', border: 'none', padding: '10px 24px', borderRadius: '8px', cursor: selectedNewPlaces.length > 0 ? 'pointer' : 'not-allowed', fontWeight: 'bold', opacity: selectedNewPlaces.length > 0 ? 1 : 0.5 }}
                        >
                          Add {selectedNewPlaces.length > 0 ? `(${selectedNewPlaces.length})` : ''} to Itinerary
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </>
      )}

      {/* Fullscreen Image Viewer Modal */}
      {fullScreenImage && (
        <div 
          className="modal-overlay" 
          onClick={() => setFullScreenImage(null)}
          style={{ zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem', background: 'rgba(0,0,0,0.85)' }}
        >
          <div style={{ position: 'relative', maxWidth: '100%', maxHeight: '100%' }}>
            <button 
              onClick={() => setFullScreenImage(null)}
              style={{ position: 'absolute', top: '-40px', right: '0', background: 'transparent', border: 'none', color: 'white', fontSize: '2rem', cursor: 'pointer', zIndex: 10000 }}
            >
              ✕
            </button>
            <img 
              src={fullScreenImage} 
              alt="Fullscreen view" 
              referrerPolicy="no-referrer"
              style={{ maxWidth: '100%', maxHeight: '85vh', objectFit: 'contain', borderRadius: '8px', boxShadow: '0 10px 25px rgba(0,0,0,0.5)' }} 
              onClick={e => e.stopPropagation()}
            />
          </div>
        </div>
      )}
    </div>
  )
}
