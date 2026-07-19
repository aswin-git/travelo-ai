import React from 'react';
import { useTheme } from '../contexts/ThemeContext';

export default function LandingPage({ onGetStarted }) {
  const { theme, toggleTheme } = useTheme();
  return (
    <div className="landing-page">
      {/* Background Effects */}
      <div className="landing-bg-orb landing-bg-orb-1"></div>
      <div className="landing-bg-orb landing-bg-orb-2"></div>

      {/* Navigation */}
      <nav className="landing-nav">
        <div className="landing-logo">
          <img src="/logo.png" alt="Travelo AI Logo" style={{ width: '32px', height: '32px', objectFit: 'contain' }} />
          <span className="landing-brand">TRAVELO AI</span>
        </div>
        <div className="landing-nav-links">
          <button className="theme-toggle" onClick={toggleTheme} title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}>
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
          <button className="landing-btn-nav" onClick={onGetStarted}>Sign In</button>
          <button className="landing-btn-primary nav-cta" onClick={onGetStarted}>Get Started</button>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="landing-hero">
        <div className="landing-hero-content">
          <div className="badge-pill">✨ The Future of Travel Planning</div>
          <h1 className="landing-title">
            Plan Your Perfect Trip <br/>
            <span className="gradient-text">with AI</span>
          </h1>
          <p className="landing-subtitle">
            Let our advanced AI assistant craft personalized travel itineraries, discover hidden gems, and handle the logistics for your next unforgettable adventure.
          </p>
          <div className="landing-hero-actions">
            <button className="landing-btn-primary large" onClick={onGetStarted}>
              Start Planning
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginLeft: '8px'}}>
                <line x1="5" y1="12" x2="19" y2="12"></line>
                <polyline points="12 5 19 12 12 19"></polyline>
              </svg>
            </button>
          </div>
        </div>

        {/* Hero Visual Mockup */}
        <div className="landing-hero-visual">
          <div className="mockup-window">
            <div className="mockup-header">
              <div className="mockup-dots"><span></span><span></span><span></span></div>
              <div className="mockup-title">travelo.ai</div>
            </div>
            <div className="mockup-body">
              <div className="mockup-chat user">Plan a 3-day trip to Tokyo focusing on tech and culture</div>
              <div className="mockup-chat ai">
                <div className="mockup-loading">
                  <div className="dot"></div><div className="dot"></div><div className="dot"></div>
                </div>
                <div className="mockup-itinerary">
                  <div className="m-day">Day 1: Historic Asakusa & Akihabara Tech</div>
                  <div className="m-slot"><span className="m-time">09:00</span> Senso-ji Temple <span className="m-crowd">🟢 Not Crowded</span></div>
                  <div className="m-slot"><span className="m-time">13:00</span> Sushi Dai</div>
                  <div className="m-slot"><span className="m-time">15:00</span> Akihabara Electric Town</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="landing-features">
        <h2 className="section-heading">Everything you need for the perfect trip</h2>
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
            <div className="feature-icon" style={{background: 'rgba(245, 158, 11, 0.1)', color: '#fbbf24'}}>🏨</div>
            <h3>Best Hotels & Food</h3>
            <p>Personalized recommendations powered by real, up-to-date reviews and ratings.</p>
          </div>
          <div className="feature-card">
            <div className="feature-icon" style={{background: 'rgba(139, 92, 246, 0.1)', color: '#a78bfa'}}>⚡</div>
            <h3>Geo-Optimized Routes</h3>
            <p>Efficient travel paths computed via nearest-neighbor routing to save you transit time.</p>
          </div>
        </div>
      </section>

      {/* Footer CTA */}
      <footer className="landing-footer">
        <div className="footer-cta-box">
          <h2>Ready to explore the world?</h2>
          <p>Join thousands of travelers planning better trips with Travelo AI.</p>
          <button className="landing-btn-primary" onClick={onGetStarted}>Create Free Account</button>
        </div>
        <div className="footer-bottom">
          <p>&copy; {new Date().getFullYear()} Travelo AI. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
