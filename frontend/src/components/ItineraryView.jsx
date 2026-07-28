import React, { useState } from 'react';

const FALLBACK_IMAGES = {
  restaurant: "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=600&q=80",
  hotel: "https://images.unsplash.com/photo-1455587734955-081b22074882?auto=format&fit=crop&w=600&q=80",
  attraction: "https://images.unsplash.com/photo-1528543606781-2f6e6857f318?auto=format&fit=crop&w=600&q=80",
  event: "https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=600&q=80",
  default: "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?auto=format&fit=crop&w=600&q=80"
};

export default function ItineraryView({ itineraryData, loading, loadingMessage, onBack, onSave, saveStatus, onDeletePlace, onAddPlace, onOpenTripView }) {
  const [activeDay, setActiveDay] = useState(1);
  const [fullScreenImage, setFullScreenImage] = useState(null);

  if (!itineraryData && !loading) return null;

  if (loading && !itineraryData) {
    return (
      <div style={{ padding: '2rem', maxWidth: '1000px', margin: '0 auto', width: '100%', height: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <div className="modern-spinner" style={{ width: '60px', height: '60px', borderTopColor: 'var(--primary-color)', marginBottom: '2rem' }}></div>
        <h2 style={{ fontSize: '2rem', color: 'var(--text-primary)', marginBottom: '1rem' }}>Building your perfect trip...</h2>
        <p style={{ fontSize: '1.2rem', color: 'var(--text-secondary)' }}>{loadingMessage || 'Optimizing routes and checking crowd data...'}</p>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, width: '100%', overflowY: 'auto', height: '100vh' }}>
      <div style={{ padding: '2rem', maxWidth: '1000px', margin: '0 auto', width: '100%' }}>
        <button
          onClick={onBack}
          style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', fontSize: '1.2rem', cursor: 'pointer', marginBottom: '1rem' }}
        >
          ← Back to Dashboard
        </button>

        <div className="itinerary-container" style={{ margin: 0, height: 'auto', maxHeight: 'none', padding: '2rem', border: 'none', background: 'var(--bg-color)' }}>
          <div className="itinerary-header">
            <h2 className="section-title" style={{ marginBottom: '4px', fontSize: '2rem' }}>
              🗺️ {itineraryData.total_days}-Day {itineraryData.pacing === 'packed' ? '🏃 Packed' : '🍃 Relaxed'} Itinerary
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '1.2rem', margin: '0 0 24px 0' }}>
              {itineraryData.destination}
            </p>
            <div style={{ display: 'flex', gap: '12px' }}>
              <button className="save-itinerary-btn" onClick={onAddPlace}>
                ➕ Add Place
              </button>
              <button className="save-itinerary-btn" onClick={onSave} disabled={saveStatus === 'saving'}>
                {saveStatus === 'saving' ? '⏳ Saving...' : saveStatus === 'saved' ? '✅ Saved!' : saveStatus === 'error' ? '❌ Failed' : '💾 Save Itinerary'}
              </button>
            </div>
            {/* Map action buttons */}
            <div className="itinerary-map-actions">
              <button
                className="map-action-btn view-map"
                onClick={() => onOpenTripView?.('map')}
              >
                🗺️ View Map
              </button>
              <button
                className="map-action-btn start-trip"
                onClick={() => onOpenTripView?.('trip')}
              >
                🚀 Start Trip
              </button>
            </div>
          </div>

          <div className="day-tabs" style={{ marginTop: '2rem', marginBottom: '2rem' }}>
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

          {itineraryData.days.filter(d => d.day_number === activeDay).map(day => (
            <div key={day.day_number} className="timeline">
              {day.weather_summary && (
                <div style={{ background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.2)', padding: '16px', borderRadius: '8px', marginBottom: '32px' }}>
                  <div style={{ fontWeight: 'bold', color: '#60a5fa', marginBottom: '8px', fontSize: '1.1rem' }}>
                    {day.weather_summary}
                  </div>
                  {day.weather_tip && (
                    <div style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>
                      💡 {day.weather_tip}
                    </div>
                  )}
                </div>
              )}

              {day.slots.map((slot, idx) => {
                const categoryColors = { attraction: '#14b8a6', restaurant: '#f59e0b', hotel: '#3b82f6', travel: '#8b5cf6', activity: '#ec4899' };
                const categoryIcons = { attraction: '🏛️', restaurant: '🍽️', hotel: '🏨', travel: '🚗', activity: '🎯' };
                const color = categoryColors[slot.category] || '#6b7280';
                const icon = categoryIcons[slot.category] || '📍';

                return (
                  <div key={idx} className="timeline-item">
                    <div className="timeline-dot" style={{ background: color }}>
                      <span style={{ fontSize: '0.9rem' }}>{icon}</span>
                    </div>
                    <div className="timeline-connector" style={{ borderColor: color + '40' }}></div>
                    <div className="timeline-card" style={{ padding: '24px' }}>
                      <div style={{ display: 'flex', gap: '24px' }}>
                        <div style={{ flex: 1, minWidth: 0, position: 'relative' }}>
                          <button
                            onClick={() => onDeletePlace(day.day_number, idx)}
                            style={{ position: 'absolute', right: 0, top: 0, background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '1.2rem', padding: '4px' }}
                            title="Delete Place"
                          >
                            🗑️
                          </button>
                          <div className="timeline-time">
                            <span className="time-label" style={{ fontSize: '1.1rem' }}>{slot.time_label}</span>
                            <span className="time-slot-badge" style={{ background: color + '20', color: color, fontSize: '0.9rem', padding: '4px 10px' }}>
                              {slot.time_slot}
                            </span>
                          </div>
                          <h4 className="timeline-title" style={{ fontSize: '1.3rem', marginTop: '12px', marginBottom: '8px' }}>{slot.activity_name}</h4>
                          <p className="timeline-desc" style={{ fontSize: '1.1rem', lineHeight: '1.6' }}>{slot.description}</p>
                          <div className="timeline-meta" style={{ marginTop: '16px' }}>
                            <span className="meta-tag">⏱️ {slot.duration_minutes} min</span>
                            {slot.rating && <span className="meta-tag">⭐ {slot.rating}</span>}
                            {slot.cost_estimate && <span className="meta-tag">💰 {slot.cost_estimate}</span>}
                            {slot.crowd_status && slot.crowd_status.toLowerCase() !== 'unknown' && (() => {
                              const cs = slot.crowd_status.toLowerCase();
                              const isLow = cs.includes('not') || cs.includes('low') || cs.includes('quiet') || cs.includes('empty');
                              const isMod = cs.includes('moderate') || cs.includes('medium') || cs.includes('average');
                              const bgColor = isLow ? 'rgba(16, 185, 129, 0.2)' : isMod ? 'rgba(245, 158, 11, 0.2)' : 'rgba(239, 68, 68, 0.2)';
                              const textColor = isLow ? '#34d399' : isMod ? '#fbbf24' : '#f87171';
                              const emoji = isLow ? '🟢' : isMod ? '🟡' : '🔴';
                              return (
                                <span className="meta-tag" style={{ background: bgColor, color: textColor, fontWeight: '600', border: `1px solid ${textColor}30` }}>
                                  {emoji} {slot.crowd_status}
                                </span>
                              )
                            })()}
                          </div>
                        </div>
                        <div style={{ width: '300px', aspectRatio: '16 / 9', flexShrink: 0, overflow: 'hidden', borderRadius: '12px', cursor: 'zoom-in' }} onClick={() => setFullScreenImage(slot.thumbnail || FALLBACK_IMAGES[slot.category?.toLowerCase()] || FALLBACK_IMAGES.default)}>
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
                        <div className="travel-connector" style={{ fontSize: '1rem', marginTop: '16px' }}>
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
      </div>
      
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
  );
}
