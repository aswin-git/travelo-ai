import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'

export default function Sidebar({
  collapsed,
  onToggle,
  onNewChat,
  onLoadSession,
  onLoadItinerary,
  currentSessionId,
  accessToken,
}) {
  const { user, signOut } = useAuth()
  const [chatSessions, setChatSessions] = useState([])
  const [savedItineraries, setSavedItineraries] = useState([])
  const [showUserMenu, setShowUserMenu] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState(null) // { type, id }

  const API = 'http://127.0.0.1:8000'

  const authHeaders = useCallback(() => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${accessToken}`,
  }), [accessToken])

  // Fetch chat sessions and itineraries
  const fetchSessions = useCallback(async () => {
    if (!accessToken) return
    try {
      const res = await fetch(`${API}/user/chat-sessions`, { headers: authHeaders() })
      if (res.ok) setChatSessions(await res.json())
    } catch (err) {
      console.error('Failed to fetch chat sessions:', err)
    }
  }, [accessToken, authHeaders])

  const fetchItineraries = useCallback(async () => {
    if (!accessToken) return
    try {
      const res = await fetch(`${API}/user/itineraries`, { headers: authHeaders() })
      if (res.ok) setSavedItineraries(await res.json())
    } catch (err) {
      console.error('Failed to fetch itineraries:', err)
    }
  }, [accessToken, authHeaders])

  useEffect(() => {
    fetchSessions()
    fetchItineraries()
  }, [fetchSessions, fetchItineraries])

  // Expose refresh methods via window for App.jsx to call after saves
  useEffect(() => {
    window.__refreshSidebarSessions = fetchSessions
    window.__refreshSidebarItineraries = fetchItineraries
    return () => {
      delete window.__refreshSidebarSessions
      delete window.__refreshSidebarItineraries
    }
  }, [fetchSessions, fetchItineraries])

  const handleDeleteSession = async (sessionId) => {
    try {
      await fetch(`${API}/user/chat-sessions/${sessionId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      })
      setChatSessions(prev => prev.filter(s => s.session_id !== sessionId))
      setDeleteConfirm(null)
    } catch (err) {
      console.error('Failed to delete session:', err)
    }
  }

  const handleDeleteItinerary = async (id) => {
    try {
      await fetch(`${API}/user/itineraries/${id}`, {
        method: 'DELETE',
        headers: authHeaders(),
      })
      setSavedItineraries(prev => prev.filter(i => i.id !== id))
      setDeleteConfirm(null)
    } catch (err) {
      console.error('Failed to delete itinerary:', err)
    }
  }

  const handleSignOut = async () => {
    try {
      await signOut()
    } catch (err) {
      console.error('Sign out failed:', err)
    }
  }

  const displayName = user?.user_metadata?.full_name || user?.email?.split('@')[0] || 'Traveler'
  const avatarUrl = user?.user_metadata?.avatar_url

  return (
    <div className={`sidebar ${collapsed ? 'sidebar-collapsed' : ''}`}>
      {/* Header */}
      <div className="sidebar-header">
        {!collapsed && (
          <div className="sidebar-brand">
            <div className="sidebar-logo-icon">🌍</div>
            <span className="sidebar-logo-text">TRAVELO AI</span>
          </div>
        )}
        <button className="sidebar-toggle" onClick={onToggle} title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            {collapsed ? (
              <>
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </>
            ) : (
              <>
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </>
            )}
          </svg>
        </button>
      </div>

      {!collapsed && (
        <>
          {/* New Chat Button */}
          <button className="sidebar-new-chat" onClick={onNewChat}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            New Chat
          </button>

          {/* Chat History */}
          <div className="sidebar-section">
            <div className="sidebar-section-title">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
              Chat History
            </div>
            <div className="sidebar-list">
              {chatSessions.length === 0 ? (
                <div className="sidebar-empty">No conversations yet</div>
              ) : (
                chatSessions.map(session => (
                  <div
                    key={session.session_id}
                    className={`sidebar-item ${currentSessionId === session.session_id ? 'sidebar-item-active' : ''}`}
                    onClick={() => onLoadSession(session.session_id)}
                  >
                    <div className="sidebar-item-content">
                      <div className="sidebar-item-title">{session.title || 'New Chat'}</div>
                      <div className="sidebar-item-meta">
                        {session.destination && <span>{session.destination}</span>}
                        {session.updated_at && (
                          <span>{new Date(session.updated_at).toLocaleDateString()}</span>
                        )}
                      </div>
                    </div>
                    <button
                      className="sidebar-item-delete"
                      onClick={(e) => {
                        e.stopPropagation()
                        if (deleteConfirm?.type === 'session' && deleteConfirm?.id === session.session_id) {
                          handleDeleteSession(session.session_id)
                        } else {
                          setDeleteConfirm({ type: 'session', id: session.session_id })
                          setTimeout(() => setDeleteConfirm(null), 3000)
                        }
                      }}
                      title={deleteConfirm?.type === 'session' && deleteConfirm?.id === session.session_id ? 'Click again to confirm' : 'Delete'}
                    >
                      {deleteConfirm?.type === 'session' && deleteConfirm?.id === session.session_id ? '✓' : '×'}
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Saved Itineraries */}
          <div className="sidebar-section">
            <div className="sidebar-section-title">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
              Saved Itineraries
            </div>
            <div className="sidebar-list">
              {savedItineraries.length === 0 ? (
                <div className="sidebar-empty">No saved itineraries</div>
              ) : (
                savedItineraries.map(itin => (
                  <div
                    key={itin.id}
                    className="sidebar-item"
                    onClick={() => onLoadItinerary(itin.id)}
                  >
                    <div className="sidebar-item-content">
                      <div className="sidebar-item-title">{itin.title}</div>
                      <div className="sidebar-item-meta">
                        <span>{itin.destination}</span>
                        <span>{itin.total_days} days • {itin.pacing}</span>
                      </div>
                    </div>
                    <button
                      className="sidebar-item-delete"
                      onClick={(e) => {
                        e.stopPropagation()
                        if (deleteConfirm?.type === 'itinerary' && deleteConfirm?.id === itin.id) {
                          handleDeleteItinerary(itin.id)
                        } else {
                          setDeleteConfirm({ type: 'itinerary', id: itin.id })
                          setTimeout(() => setDeleteConfirm(null), 3000)
                        }
                      }}
                      title={deleteConfirm?.type === 'itinerary' && deleteConfirm?.id === itin.id ? 'Click again to confirm' : 'Delete'}
                    >
                      {deleteConfirm?.type === 'itinerary' && deleteConfirm?.id === itin.id ? '✓' : '×'}
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* User Profile */}
          <div className="sidebar-user">
            <div className="sidebar-user-info" onClick={() => setShowUserMenu(!showUserMenu)}>
              <div className="sidebar-avatar">
                {avatarUrl ? (
                  <img src={avatarUrl} alt="" />
                ) : (
                  <span>{displayName[0]?.toUpperCase()}</span>
                )}
              </div>
              <div className="sidebar-user-details">
                <div className="sidebar-user-name">{displayName}</div>
                <div className="sidebar-user-email">{user?.email}</div>
              </div>
            </div>
            {showUserMenu && (
              <button className="sidebar-signout" onClick={handleSignOut}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                  <polyline points="16 17 21 12 16 7" />
                  <line x1="21" y1="12" x2="9" y2="12" />
                </svg>
                Sign Out
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )
}
