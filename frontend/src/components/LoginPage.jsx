import { useState, useMemo } from 'react'
import { useAuth } from '../contexts/AuthContext'

function getPasswordStrength(pw) {
  if (!pw) return { level: 0, label: '', color: '' }
  let score = 0
  if (pw.length >= 6) score++
  if (pw.length >= 10) score++
  if (/[A-Z]/.test(pw)) score++
  if (/[0-9]/.test(pw)) score++
  if (/[^A-Za-z0-9]/.test(pw)) score++

  if (score <= 1) return { level: 1, label: 'Weak', color: '#ef4444' }
  if (score <= 2) return { level: 2, label: 'Fair', color: '#f59e0b' }
  if (score <= 3) return { level: 3, label: 'Good', color: '#3b82f6' }
  return { level: 4, label: 'Strong', color: '#10b981' }
}

export default function LoginPage({ onBack }) {
  const [isSignUp, setIsSignUp] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const [verificationPending, setVerificationPending] = useState(false)
  const [verificationEmail, setVerificationEmail] = useState('')

  const { signInWithEmail, signUpWithEmail, signInWithGoogle } = useAuth()

  const passwordStrength = useMemo(() => getPasswordStrength(password), [password])
  const passwordsMatch = confirmPassword.length === 0 || password === confirmPassword

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')

    if (isSignUp) {
      if (password !== confirmPassword) {
        setError('Passwords do not match')
        return
      }
      if (password.length < 6) {
        setError('Password must be at least 6 characters')
        return
      }
    }

    setLoading(true)

    try {
      if (isSignUp) {
        const data = await signUpWithEmail(email, password)
        // Supabase returns user but no session when email confirmation is required
        if (data?.user && !data?.session) {
          setVerificationPending(true)
          setVerificationEmail(email)
        } else {
          setSuccess('Account created! Check your email to confirm, then sign in.')
          setIsSignUp(false)
          setPassword('')
          setConfirmPassword('')
        }
      } else {
        await signInWithEmail(email, password)
      }
    } catch (err) {
      setError(err.message || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleSignIn = async () => {
    setError('')
    try {
      await signInWithGoogle()
    } catch (err) {
      setError(err.message || 'Google sign-in failed')
    }
  }

  const handleResendVerification = async () => {
    setLoading(true)
    setError('')
    try {
      await signUpWithEmail(verificationEmail, password)
      setSuccess('Verification email resent! Check your inbox.')
    } catch (err) {
      setError(err.message || 'Failed to resend verification email')
    } finally {
      setLoading(false)
    }
  }

  // ── Email Verification Pending Screen ──
  if (verificationPending) {
    return (
      <div className="login-page">
        <div className="login-bg-orb login-bg-orb-1"></div>
        <div className="login-bg-orb login-bg-orb-2"></div>
        <div className="login-bg-orb login-bg-orb-3"></div>

        <div className="login-card">
          <div className="login-logo">
            <div className="verification-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="4" width="20" height="16" rx="2"/>
                <path d="M22 4l-10 8L2 4"/>
              </svg>
            </div>
            <h1 className="login-title" style={{ fontSize: '1.3rem' }}>Check Your Email</h1>
            <p className="login-subtitle" style={{ marginTop: '8px', lineHeight: '1.5' }}>
              We sent a verification link to<br/>
              <strong style={{ color: 'var(--primary)' }}>{verificationEmail}</strong>
            </p>
          </div>

          <div className="verification-steps">
            <div className="verification-step">
              <span className="step-num">1</span>
              <span>Open the email from Travelo AI</span>
            </div>
            <div className="verification-step">
              <span className="step-num">2</span>
              <span>Click the confirmation link</span>
            </div>
            <div className="verification-step">
              <span className="step-num">3</span>
              <span>Come back and sign in</span>
            </div>
          </div>

          {error && <div className="login-alert login-alert-error">{error}</div>}
          {success && <div className="login-alert login-alert-success">{success}</div>}

          <button
            className="login-btn login-btn-primary"
            onClick={() => { setVerificationPending(false); setIsSignUp(false); setPassword(''); setConfirmPassword(''); setError(''); setSuccess(''); }}
          >
            Go to Sign In
          </button>

          <button
            className="login-btn login-btn-resend"
            onClick={handleResendVerification}
            disabled={loading}
            style={{ marginTop: '10px' }}
          >
            {loading ? <span className="login-spinner"></span> : "Didn't get it? Resend"}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="login-page">
      {/* Animated background orbs */}
      <div className="login-bg-orb login-bg-orb-1"></div>
      <div className="login-bg-orb login-bg-orb-2"></div>
      <div className="login-bg-orb login-bg-orb-3"></div>

      <div className="login-card">
        {/* Back Button */}
        {onBack && (
          <button className="login-back-btn" onClick={onBack}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12"></line>
              <polyline points="12 19 5 12 12 5"></polyline>
            </svg>
            Back
          </button>
        )}

        {/* Logo */}
        <div className="login-logo">
          <div className="login-logo-icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <path d="M2 12h20"/>
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
            </svg>
          </div>
          <h1 className="login-title">TRAVELO AI</h1>
          <p className="login-subtitle">Your AI-powered travel companion</p>
        </div>

        {/* Error / Success */}
        {error && <div className="login-alert login-alert-error">{error}</div>}
        {success && <div className="login-alert login-alert-success">{success}</div>}

        {/* Form */}
        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-field">
            <label>Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoComplete="email"
            />
          </div>
          <div className="login-field">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder={isSignUp ? 'Create a password (6+ chars)' : 'Enter your password'}
              required
              minLength={6}
              autoComplete={isSignUp ? 'new-password' : 'current-password'}
            />
            {/* Password Strength Indicator — signup only */}
            {isSignUp && password.length > 0 && (
              <div className="password-strength">
                <div className="strength-bar-track">
                  {[1, 2, 3, 4].map(i => (
                    <div
                      key={i}
                      className="strength-bar-segment"
                      style={{
                        background: i <= passwordStrength.level ? passwordStrength.color : 'rgba(255,255,255,0.08)',
                      }}
                    />
                  ))}
                </div>
                <span className="strength-label" style={{ color: passwordStrength.color }}>
                  {passwordStrength.label}
                </span>
              </div>
            )}
          </div>

          {/* Confirm Password — signup only */}
          {isSignUp && (
            <div className="login-field">
              <label>Confirm Password</label>
              <input
                type="password"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                placeholder="Re-enter your password"
                required
                minLength={6}
                autoComplete="new-password"
                className={confirmPassword.length > 0 && !passwordsMatch ? 'input-error' : ''}
              />
              {confirmPassword.length > 0 && !passwordsMatch && (
                <span className="field-error">Passwords do not match</span>
              )}
              {confirmPassword.length > 0 && passwordsMatch && (
                <span className="field-success">✓ Passwords match</span>
              )}
            </div>
          )}

          <button
            type="submit"
            className="login-btn login-btn-primary"
            disabled={loading || (isSignUp && (!passwordsMatch || confirmPassword.length === 0))}
          >
            {loading ? (
              <span className="login-spinner"></span>
            ) : isSignUp ? (
              'Create Account'
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        {/* Divider */}
        <div className="login-divider">
          <span>OR</span>
        </div>

        {/* Google */}
        <button onClick={handleGoogleSignIn} className="login-btn login-btn-google" type="button">
          <svg width="38" height="18" viewBox="0 0 24 24">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
          </svg>
          Sign in with Google
        </button>

        {/* Toggle */}
        <p className="login-toggle">
          {isSignUp ? 'Already have an account?' : "Don't have an account?"}
          <button type="button" onClick={() => { setIsSignUp(!isSignUp); setError(''); setSuccess(''); setConfirmPassword(''); }}>
            {isSignUp ? 'Sign In' : 'Sign Up'}
          </button>
        </p>
      </div>
    </div>
  )
}
