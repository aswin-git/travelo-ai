import React, { useState } from 'react';

export default function ItineraryWizard({ onFinish, onCancel }) {
  const [step, setStep] = useState(0);
  const [data, setData] = useState({
    destination: '',
    start_location: '',
    check_in: '',
    num_days: '',
    traveler_type: 'couple',
    adults: 2,
    budget: '',
    pacing: 'relaxed',
    interests: '',
    activity_level: '',
    cuisine: '',
    kids_friendly: false,
    meal_preference: 'flexible',
    crowd_aware: false,
    crowd_precision: 'approximate',
    weather_aware: false,
  });

  const nextStep = () => {
    if (step === 0 && !data.destination.trim()) return;
    if (step === 1 && !data.start_location.trim()) return;
    if (step === 2 && (!data.check_in || !data.num_days)) return;
    
    if (step < 6) {
      setStep(step + 1);
    } else {
      onFinish(data);
    }
  };

  const prevStep = () => {
    if (step > 0) setStep(step - 1);
  };

  const handleChange = (field, value) => {
    setData(prev => ({ ...prev, [field]: value }));
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      nextStep();
    }
  };

  const steps = [
    {
      title: "Where are you dreaming of going?",
      content: (
        <input 
          autoFocus
          type="text" 
          value={data.destination} 
          onChange={e => handleChange('destination', e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="e.g. Kyoto, Japan"
          style={{ width: '100%', fontSize: '3rem', border: 'none', borderBottom: '2px solid var(--border-color)', background: 'transparent', color: 'var(--text-primary)', outline: 'none', padding: '10px 0', textAlign: 'center' }}
        />
      )
    },
    {
      title: "Where are you starting from?",
      content: (
        <input 
          autoFocus
          type="text" 
          value={data.start_location} 
          onChange={e => handleChange('start_location', e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="e.g. New York (JFK)"
          style={{ width: '100%', fontSize: '3rem', border: 'none', borderBottom: '2px solid var(--border-color)', background: 'transparent', color: 'var(--text-primary)', outline: 'none', padding: '10px 0', textAlign: 'center' }}
        />
      )
    },
    {
      title: "When are you traveling?",
      content: (
        <div style={{ display: 'flex', gap: '2rem', justifyContent: 'center' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <label style={{ color: 'var(--text-secondary)', fontSize: '1.2rem' }}>Start Date</label>
            <input 
              type="date" 
              value={data.check_in} 
              onChange={e => handleChange('check_in', e.target.value)}
              style={{ fontSize: '2rem', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <label style={{ color: 'var(--text-secondary)', fontSize: '1.2rem' }}>Number of Days</label>
            <input 
              type="number" 
              min="1"
              max="14"
              value={data.num_days} 
              onChange={e => handleChange('num_days', parseInt(e.target.value) || '')}
              onKeyDown={handleKeyDown}
              placeholder="e.g. 5"
              style={{ fontSize: '2rem', width: '150px', textAlign: 'center', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}
            />
          </div>
        </div>
      )
    },
    {
      title: "Who's coming along?",
      content: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', alignItems: 'center' }}>
          <select 
            value={data.traveler_type} 
            onChange={e => handleChange('traveler_type', e.target.value)}
            style={{ fontSize: '2rem', padding: '10px 20px', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}
          >
            <option value="solo">Solo Adventure</option>
            <option value="couple">Couple</option>
            <option value="family">Family (Kids friendly)</option>
            <option value="friends">Group of Friends</option>
          </select>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <label style={{ fontSize: '1.5rem', color: 'var(--text-secondary)' }}>Travelers:</label>
            <input 
              type="number" 
              min="1" 
              value={data.adults} 
              onChange={e => handleChange('adults', parseInt(e.target.value) || 1)}
              style={{ fontSize: '2rem', width: '100px', textAlign: 'center', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}
            />
          </div>
        </div>
      )
    },
    {
      title: "Any specific vibe or budget?",
      content: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', alignItems: 'center', width: '100%', maxWidth: '600px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', width: '100%' }}>
            <label style={{ fontSize: '1.5rem', color: 'var(--text-secondary)', width: '120px' }}>Budget (₹):</label>
            <input 
              type="number" 
              value={data.budget} 
              onChange={e => handleChange('budget', e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g. 50000"
              style={{ flex: 1, fontSize: '2rem', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', width: '100%' }}>
            <label style={{ fontSize: '1.5rem', color: 'var(--text-secondary)', width: '120px' }}>Pacing:</label>
            <select 
              value={data.pacing} 
              onChange={e => handleChange('pacing', e.target.value)}
              style={{ flex: 1, fontSize: '2rem', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}
            >
              <option value="relaxed">🍃 Relaxed (Fewer stops)</option>
              <option value="packed">🏃 Packed (See it all)</option>
            </select>
          </div>
        </div>
      )
    },
    {
      title: "What about activities and food?",
      content: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', alignItems: 'flex-start', width: '100%', maxWidth: '600px', fontSize: '1.2rem' }}>
          
          <div style={{ width: '100%' }}>
            <label style={{ display: 'block', color: 'var(--text-secondary)', marginBottom: '8px' }}>Specific Interests / Vibes</label>
            <input 
              type="text" 
              value={data.interests} 
              onChange={e => handleChange('interests', e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g. History, Art, Nightlife, Nature"
              style={{ width: '100%', fontSize: '1.2rem', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}
            />
          </div>

          <div style={{ width: '100%' }}>
            <label style={{ display: 'block', color: 'var(--text-secondary)', marginBottom: '8px' }}>Activity Level</label>
            <select 
              value={data.activity_level} 
              onChange={e => handleChange('activity_level', e.target.value)}
              style={{ width: '100%', fontSize: '1.2rem', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}
            >
              <option value="">Any</option>
              <option value="high">High (Hiking, walking)</option>
              <option value="low">Low (Museums, scenic drives)</option>
            </select>
          </div>

          <div style={{ width: '100%' }}>
            <label style={{ display: 'block', color: 'var(--text-secondary)', marginBottom: '8px' }}>Cuisine / Dietary Restrictions</label>
            <input 
              type="text" 
              value={data.cuisine} 
              onChange={e => handleChange('cuisine', e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g. Vegan, Seafood, Italian"
              style={{ width: '100%', fontSize: '1.2rem', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}
            />
          </div>

          <div style={{ width: '100%' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
              <input 
                type="checkbox" 
                checked={data.kids_friendly}
                onChange={e => handleChange('kids_friendly', e.target.checked)}
                style={{ width: '20px', height: '20px' }}
              />
              <span style={{ color: 'var(--text-primary)' }}>👨‍👩‍👧‍👦 Kids/Family Friendly</span>
            </label>
          </div>

        </div>
      )
    },
    {
      title: "Smart Planning Preferences",
      content: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', alignItems: 'flex-start', width: '100%', maxWidth: '600px', fontSize: '1.2rem' }}>
          
          <div style={{ width: '100%' }}>
            <label style={{ display: 'block', color: 'var(--text-secondary)', marginBottom: '8px' }}>Meal Scheduling</label>
            <select 
              value={data.meal_preference} 
              onChange={e => handleChange('meal_preference', e.target.value)}
              style={{ width: '100%', fontSize: '1.2rem', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}
            >
              <option value="flexible">📍 Flexible (restaurants placed on the route)</option>
              <option value="fixed">🕐 Fixed Times (Breakfast → Lunch → Dinner)</option>
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', width: '100%' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
              <input 
                type="checkbox" 
                checked={data.crowd_aware}
                onChange={e => {
                  handleChange('crowd_aware', e.target.checked);
                  if (!e.target.checked) handleChange('crowd_precision', 'approximate');
                }}
                style={{ width: '20px', height: '20px' }}
              />
              <span style={{ color: 'var(--text-primary)' }}>👥 Avoid Crowded Places</span>
            </label>

            {data.crowd_aware && (
              <div style={{ marginLeft: '30px', marginTop: '5px', width: '100%' }}>
                <label style={{ display: 'block', color: 'var(--text-secondary)', marginBottom: '8px', fontSize: '1rem' }}>Crowd Estimation Type</label>
                <select 
                  value={data.crowd_precision} 
                  onChange={e => handleChange('crowd_precision', e.target.value)}
                  style={{ width: '100%', fontSize: '1rem', padding: '8px', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}
                >
                  <option value="approximate">🤖 AI Estimate</option>
                  <option value="precise">📡 Real-time Data (Slower)</option>
                </select>
              </div>
            )}

            <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', marginTop: '10px' }}>
              <input 
                type="checkbox" 
                checked={data.weather_aware}
                onChange={e => handleChange('weather_aware', e.target.checked)}
                style={{ width: '20px', height: '20px' }}
              />
              <span style={{ color: 'var(--text-primary)' }}>⛅ Optimize for Weather</span>
            </label>
          </div>

        </div>
      )
    }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', padding: '2rem', background: 'var(--bg-color)', position: 'relative', flex: 1, width: '100%' }}>
      <button 
        onClick={onCancel}
        style={{ position: 'absolute', top: '2rem', left: '2rem', background: 'transparent', border: 'none', color: 'var(--text-secondary)', fontSize: '1.2rem', cursor: 'pointer' }}
      >
        ← Back
      </button>

      <div style={{ display: 'flex', justifyContent: 'center', marginTop: '2rem' }}>
        <div style={{ display: 'flex', gap: '10px' }}>
          {steps.map((_, i) => (
            <div 
              key={i} 
              style={{ 
                height: '6px', 
                width: '40px', 
                borderRadius: '3px', 
                background: i <= step ? 'var(--primary-color)' : 'var(--border-color)',
                transition: 'background 0.3s'
              }} 
            />
          ))}
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', maxWidth: '800px', margin: '0 auto', width: '100%' }}>
        <h2 style={{ fontSize: '2.5rem', marginBottom: '3rem', color: 'var(--text-primary)', textAlign: 'center' }}>
          {steps[step].title}
        </h2>
        
        <div style={{ width: '100%', display: 'flex', justifyContent: 'center' }}>
          {steps[step].content}
        </div>

        <div style={{ display: 'flex', gap: '1rem', marginTop: '4rem' }}>
          {step > 0 && (
            <button 
              onClick={prevStep}
              style={{ padding: '15px 30px', fontSize: '1.2rem', borderRadius: '30px', background: 'var(--surface-color)', border: '1px solid var(--border-color)', color: 'var(--text-primary)', cursor: 'pointer' }}
            >
              Previous
            </button>
          )}
          <button 
            onClick={nextStep}
            style={{ padding: '15px 40px', fontSize: '1.2rem', borderRadius: '30px', background: 'var(--primary-color)', border: 'none', color: 'white', cursor: 'pointer', fontWeight: 'bold' }}
          >
            {step === steps.length - 1 ? 'Build Itinerary ✨' : 'Next'}
          </button>
        </div>
      </div>
    </div>
  );
}
