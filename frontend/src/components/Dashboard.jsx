import React from 'react';

export default function Dashboard({ onSelect }) {
  return (
    <div className="landing-page" style={{ flex: 1, width: '100%', overflowY: 'auto' }}>
      <section className="landing-hero" style={{ paddingTop: '10vh', paddingBottom: '5vh' }}>
        <div className="landing-hero-content" style={{ maxWidth: '1000px', margin: '0 auto', textAlign: 'center' }}>
          <div className="badge-pill" style={{ margin: '0 auto 24px auto' }}>✨ Welcome back to Travelo AI</div>
          <h1 className="landing-title">
            Where to <span className="gradient-text">next?</span>
          </h1>
          <p className="landing-subtitle" style={{ margin: '0 auto 3rem auto' }}>
            Choose how you want to plan your trip. Our AI is ready to craft the perfect itinerary or brainstorm ideas with you.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '2rem', marginTop: '2rem', textAlign: 'left' }}>
          
          <div 
            onClick={() => onSelect('chat')}
            style={{
              background: 'var(--surface-color)',
              border: '1px solid var(--border-color)',
              borderRadius: '16px',
              padding: '2.5rem',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              textAlign: 'left'
            }}
            onMouseOver={e => {
              e.currentTarget.style.borderColor = 'var(--primary-color)';
              e.currentTarget.style.transform = 'translateY(-4px)';
            }}
            onMouseOut={e => {
              e.currentTarget.style.borderColor = 'var(--border-color)';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>💬</div>
            <h2 style={{ fontSize: '1.5rem', marginBottom: '1rem', color: 'var(--text-primary)' }}>Ask Anything</h2>
            <p style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}>
              Brainstorm ideas, ask questions, and explore features in an open-ended chat.
            </p>
          </div>

          <div 
            onClick={() => onSelect('wizard')}
            style={{
              background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(168, 85, 247, 0.1))',
              border: '1px solid var(--primary-color)',
              borderRadius: '16px',
              padding: '2.5rem',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              textAlign: 'left'
            }}
            onMouseOver={e => {
              e.currentTarget.style.boxShadow = '0 8px 32px rgba(99, 102, 241, 0.2)';
              e.currentTarget.style.transform = 'translateY(-4px)';
            }}
            onMouseOut={e => {
              e.currentTarget.style.boxShadow = 'none';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            <div style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>🗺️</div>
            <h2 style={{ fontSize: '1.5rem', marginBottom: '1rem', color: 'var(--text-primary)' }}>Guided Trip Builder</h2>
            <p style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}>
              Answer a few quick questions to generate a custom, day-by-day travel plan.
            </p>
          </div>

          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="landing-features" style={{ paddingBottom: '4rem' }}>
        <h2 className="section-heading">Why plan with Travelo AI?</h2>
        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon" style={{background: 'rgba(59, 130, 246, 0.1)', color: '#60a5fa'}}>🗺️</div>
            <h3>Smart Itineraries</h3>
            <p>AI-generated daily schedules tailored to your pace, interests, and budget.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon" style={{background: 'rgba(16, 185, 129, 0.1)', color: '#34d399'}}>👥</div>
            <h3>Crowd-Aware Planning</h3>
            <p>We analyze real-time foot traffic data to help you avoid peak hours at popular spots.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon" style={{background: 'rgba(245, 158, 11, 0.1)', color: '#fbbf24'}}>⛅</div>
            <h3>Weather Optimized</h3>
            <p>Schedules dynamically adapt to multi-day forecasts, pushing indoor activities to rainy hours.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon" style={{background: 'rgba(139, 92, 246, 0.1)', color: '#a78bfa'}}>⚡</div>
            <h3>Geo-Optimized Routes</h3>
            <p>Efficient travel paths computed via nearest-neighbor routing to save you transit time.</p>
          </div>
        </div>
      </section>
      
      {/* Footer */}
      <footer className="landing-footer" style={{ padding: '2rem 0', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
        <div className="footer-bottom">
          <p>&copy; {new Date().getFullYear()} Travelo AI. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
