import React, { useState, useEffect, useCallback } from 'react';
import { useRecorder } from './hooks/useRecorder';
import { API_BASE } from './config';
import { clearAccessToken, getAccessToken, setAccessToken } from './authStorage';
import './App.css';

function apiUrl(path) {
  return `${API_BASE}${path}`;
}

/** API reachability (GET /api/health). */
function ApiStatusBar() {
  const [status, setStatus] = useState('checking');

  useEffect(() => {
    let cancelled = false;
    fetch(apiUrl('/api/health'))
      .then((r) => {
        if (!cancelled) setStatus(r.ok ? 'ok' : 'error');
      })
      .catch(() => {
        if (!cancelled) setStatus('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const label =
    status === 'checking'
      ? 'API: checking connection…'
      : status === 'ok'
        ? 'API: connected'
        : 'API: unreachable — start the backend (port 8000) or check REACT_APP_API_URL';

  return (
    <div className={`appwrite-bar appwrite-bar--${status}`} role="status" aria-live="polite">
      {label}
    </div>
  );
}

function LoginScreen({ onLoggedIn }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [mode, setMode] = useState('login');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      const path = mode === 'register' ? '/api/auth/register' : '/api/auth/login';
      const body =
        mode === 'register'
          ? { email, password, name: name || email.split('@')[0] }
          : { email, password };
      const res = await fetch(apiUrl(path), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg =
          typeof data.detail === 'string'
            ? data.detail
            : Array.isArray(data.detail)
              ? data.detail.map((d) => d.msg || d).join(', ')
              : 'Authentication failed';
        throw new Error(msg);
      }
      setAccessToken(data.access_token);
      onLoggedIn(data.user);
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="setup-screen">
      <div className="setup-card" style={{ maxWidth: 420 }}>
        <div className="setup-header">
          <div className="logo-mark">VCX</div>
          <h1>Sign in</h1>
          <p className="setup-subtitle">Voicera collector account (Postgres + JWT backend)</p>
        </div>
        <form className="setup-body" onSubmit={submit}>
          {mode === 'register' && (
            <div className="field-group">
              <label>Display name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Optional" />
            </div>
          )}
          <div className="field-group">
            <label>Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
          </div>
          <div className="field-group">
            <label>Password</label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
            />
          </div>
          {error && <div className="error-msg">{error}</div>}
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? 'Please wait…' : mode === 'register' ? 'Create account' : 'Log in'}
          </button>
          <button
            type="button"
            className="btn-ghost"
            onClick={() => setMode(mode === 'login' ? 'register' : 'login')}
          >
            {mode === 'login' ? 'Need an account? Register' : 'Have an account? Log in'}
          </button>
        </form>
      </div>
    </div>
  );
}

function UserBar({ user, onLogout }) {
  return (
    <div className="user-bar">
      <span className="user-email">{user.email}</span>
      <button type="button" className="btn-ghost small" onClick={onLogout}>
        Log out
      </button>
    </div>
  );
}

const INDIAN_LANGUAGES = [
  'Hindi', 'Marathi', 'Bengali', 'Telugu', 'Tamil', 'Gujarati',
  'Kannada', 'Malayalam', 'Punjabi', 'Odia', 'Assamese', 'Urdu',
  'English (native)', 'Other',
];

const REGIONS = [
  'Maharashtra', 'Delhi / NCR', 'Karnataka', 'Tamil Nadu', 'Telangana',
  'Gujarat', 'West Bengal', 'Kerala', 'Punjab', 'Rajasthan',
  'Uttar Pradesh', 'Madhya Pradesh', 'Andhra Pradesh', 'Other',
];

const NOISE_LEVELS = [
  { value: 'quiet', label: 'Quiet (office/home)' },
  { value: 'moderate', label: 'Moderate (background noise)' },
  { value: 'noisy', label: 'Noisy (crowd/traffic)' },
];

const DEVICE_TYPES = [
  { value: 'laptop_builtin', label: 'Laptop built-in mic' },
  { value: 'headset', label: 'Headset / earphones' },
  { value: 'phone', label: 'Mobile phone' },
  { value: 'external_mic', label: 'External microphone' },
];

const AGE_RANGES = [
  { value: '18-24', label: '18–24' },
  { value: '25-34', label: '25–34' },
  { value: '35-44', label: '35–44' },
  { value: '45-54', label: '45–54' },
  { value: '55+', label: '55 and above' },
];

const GENDER_OPTIONS = [
  { value: 'Male', label: 'Male' },
  { value: 'Female', label: 'Female' },
  { value: 'Non-binary', label: 'Non-binary' },
  { value: 'Prefer not to say', label: 'Prefer not to say' },
];

const CATEGORY_LABELS = {
  domain_vocabulary: 'Domain Vocabulary',
  customer_query: 'Customer Query',
  hinglish: 'Hinglish',
  alphanumeric: 'Alphanumeric',
  phonetic_indian: 'Indian English Phonetic',
  disfluent: 'Disfluent',
  dates_addresses: 'Dates & Addresses',
  numbers_currency: 'Numbers & Currency',
  identity: 'Speaker Identity',
  // Legacy key for existing recordings
  phonetic: 'Phonetic (legacy)',
};

const CATEGORY_COLORS = {
  domain_vocabulary: '#ff5c1a',
  customer_query: '#3ddc84',
  hinglish: '#f5c842',
  alphanumeric: '#5c9fff',
  phonetic_indian: '#c084fc',
  disfluent: '#fb7185',
  dates_addresses: '#34d399',
  numbers_currency: '#fbbf24',
  identity: '#94a3b8',
  // Legacy key for existing recordings
  phonetic: '#c084fc',
};

// ── Speaker Setup ─────────────────────────────────────────────────────────────

const SPEAKER_PROFILE_KEY = 'vcx_speaker_profile';

function loadSavedProfile(userId) {
  try {
    const raw = localStorage.getItem(`${SPEAKER_PROFILE_KEY}_${userId}`);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function saveProfile(userId, profile) {
  try {
    localStorage.setItem(`${SPEAKER_PROFILE_KEY}_${userId}`, JSON.stringify(profile));
  } catch {}
}

// First-time setup: collect language, region, demographics
function SpeakerSetup({ onComplete, user }) {
  const [form, setForm] = useState({
    native_language: '', region: '', age_range: '', gender: '',
    noise_level: 'quiet', device_type: 'laptop_builtin',
  });

  const valid = form.native_language && form.region;
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleStart = () => {
    if (!valid) return;
    const profile = {
      ...form,
      name: user?.name || '',
      email: user?.email || '',
    };
    saveProfile(user?.id, profile);
    onComplete(profile);
  };

  return (
    <div className="setup-screen">
      <div className="setup-card">
        <div className="setup-header">
          <div className="logo-mark">VCX</div>
          <h1>Speech Data Collector</h1>
          <p className="setup-subtitle">Tell us a bit about yourself — only asked once</p>
        </div>

        <div className="setup-body">
          <div className="field-group">
            <label>Recording as</label>
            <input value={`${user?.name || ''} · ${user?.email || ''}`} disabled style={{ opacity: 0.6 }} />
          </div>

          <div className="field-row">
            <div className="field-group">
              <label>Native Language</label>
              <select value={form.native_language} onChange={e => set('native_language', e.target.value)}>
                <option value="">Select language</option>
                {INDIAN_LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <div className="field-group">
              <label>Home Region</label>
              <select value={form.region} onChange={e => set('region', e.target.value)}>
                <option value="">Select region</option>
                {REGIONS.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
          </div>

          <div className="field-row">
            <div className="field-group">
              <label>Age Range <span style={{ color: 'var(--text-secondary)', fontWeight: 400 }}>(optional)</span></label>
              <select value={form.age_range} onChange={e => set('age_range', e.target.value)}>
                <option value="">Prefer not to say</option>
                {AGE_RANGES.map(a => <option key={a.value} value={a.value}>{a.label}</option>)}
              </select>
            </div>
            <div className="field-group">
              <label>Gender <span style={{ color: 'var(--text-secondary)', fontWeight: 400 }}>(optional)</span></label>
              <select value={form.gender} onChange={e => set('gender', e.target.value)}>
                <option value="">Prefer not to say</option>
                {GENDER_OPTIONS.map(g => <option key={g.value} value={g.value}>{g.label}</option>)}
              </select>
            </div>
          </div>

          <div className="field-row">
            <div className="field-group">
              <label>Current Environment</label>
              <select value={form.noise_level} onChange={e => set('noise_level', e.target.value)}>
                {NOISE_LEVELS.map(n => <option key={n.value} value={n.value}>{n.label}</option>)}
              </select>
            </div>
            <div className="field-group">
              <label>Recording Device</label>
              <select value={form.device_type} onChange={e => set('device_type', e.target.value)}>
                {DEVICE_TYPES.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
              </select>
            </div>
          </div>

          <div className="setup-note">
            <span className="note-icon">ℹ</span>
            Speak naturally in your own accent — your accent is what makes this data valuable.
          </div>

          <button className={`btn-primary ${!valid ? 'disabled' : ''}`} onClick={handleStart} disabled={!valid}>
            Start Recording Session →
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Waveform Visualizer ───────────────────────────────────────────────────────

// Returning-speaker quick-start: only ask noise + device (can change each session)
function SessionEnvSetup({ profile, onComplete, onReset }) {
  const [noise_level, setNoise] = useState(profile.noise_level || 'quiet');
  const [device_type, setDevice] = useState(profile.device_type || 'laptop_builtin');

  return (
    <div className="setup-screen">
      <div className="setup-card">
        <div className="setup-header">
          <div className="logo-mark">VCX</div>
          <h1>Ready to record?</h1>
          <p className="setup-subtitle">{profile.name} · {profile.native_language} · {profile.region}</p>
        </div>
        <div className="setup-body">
          <div className="field-row">
            <div className="field-group">
              <label>Current Environment</label>
              <select value={noise_level} onChange={e => setNoise(e.target.value)}>
                {NOISE_LEVELS.map(n => <option key={n.value} value={n.value}>{n.label}</option>)}
              </select>
            </div>
            <div className="field-group">
              <label>Recording Device</label>
              <select value={device_type} onChange={e => setDevice(e.target.value)}>
                {DEVICE_TYPES.map(d => <option key={d.value} value={d.value}>{d.label}</option>)}
              </select>
            </div>
          </div>
          <button className="btn-primary" onClick={() => onComplete({ ...profile, noise_level, device_type })}>
            Start Recording Session →
          </button>
          <button className="btn-ghost" style={{ marginTop: 10, width: '100%' }} onClick={onReset}>
            Not you? Update profile
          </button>
        </div>
      </div>
    </div>
  );
}

function VolumeBar({ volume, isRecording }) {
  const bars = 24;
  return (
    <div className="volume-bars">
      {Array.from({ length: bars }).map((_, i) => {
        const threshold = (i / bars) * 100;
        const active = isRecording && volume > threshold;
        return (
          <div
            key={i}
            className={`vol-bar ${active ? 'active' : ''}`}
            style={{ height: `${8 + (i % 3) * 4 + Math.sin(i * 0.8) * 6}px` }}
          />
        );
      })}
    </div>
  );
}

// ── Recording Session ─────────────────────────────────────────────────────────

const IDENTITY_PROMPTS = [
  { id: 'id_001', category: 'identity', text: 'Please say your full name clearly.' },
  { id: 'id_002', category: 'identity', text: 'Please spell out your email address.' },
];

const MIN_DURATION = 1;
const MAX_DURATION = 30;

function RecordingSession({ speaker, prompts, onDone, getAuthHeaders, sessionId: sessionUuid }) {
  const [promptIndex, setPromptIndex] = useState(0);
  const [sessionComplete, setSessionComplete] = useState(false);
  const [state, setState] = useState('idle'); // idle | recording | reviewing | uploading | done | error
  const [autoTranscript, setAutoTranscript] = useState('');
  const [uploadError, setUploadError] = useState('');
  const [completedCount, setCompletedCount] = useState(0);
  const [durationWarning, setDurationWarning] = useState('');
  const [confidenceWarning, setConfidenceWarning] = useState('');

  const { isRecording, audioBlob, audioUrl, duration, volume, error, start, stop, reset } = useRecorder();

  // Prepend identity prompts to the session
  const allPrompts = React.useMemo(() => [...IDENTITY_PROMPTS, ...prompts], [prompts]);
  const currentPrompt = allPrompts[promptIndex];
  const progress = (completedCount / allPrompts.length) * 100;

  const handleRecord = useCallback(async () => {
    if (state === 'idle') {
      setDurationWarning('');
      setConfidenceWarning('');
      await start();
      setState('recording');
    } else if (state === 'recording') {
      if (duration < MIN_DURATION) {
        setDurationWarning('Recording too short (under 1 second). Please try again.');
        stop();
        reset();
        setState('idle');
        return;
      }
      stop();
      setState('reviewing');
      setAutoTranscript('');
    }
  }, [state, start, stop, reset, duration]);

  // Auto-stop recording at MAX_DURATION
  useEffect(() => {
    if (state === 'recording' && duration >= MAX_DURATION) {
      stop();
      setState('reviewing');
      setAutoTranscript('');
      setDurationWarning('Recording auto-stopped at 30 seconds.');
    }
  }, [state, duration, stop]);

  // Auto-upload as soon as the blob is ready after stopping
  useEffect(() => {
    if (state === 'reviewing' && audioBlob) {
      autoUpload(audioBlob);
    }
  }, [state, audioBlob]); // autoUpload is intentionally excluded — it changes every render due to currentPrompt

  const autoUpload = useCallback(async (blob) => {
    setState('uploading');
    setUploadError('');
    setConfidenceWarning('');
    setAutoTranscript('Transcribing…');

    const speakerId = speaker.name.toLowerCase().replace(/\s+/g, '_');
    const form = new FormData();
    form.append('audio', blob, 'recording.webm');
    form.append('speaker_id', speakerId);
    form.append('speaker_name', speaker.name);
    form.append('native_language', speaker.native_language);
    form.append('region', speaker.region);
    form.append('prompt_id', currentPrompt.id);
    form.append('prompt_text', currentPrompt.text);
    form.append('prompt_category', currentPrompt.category);
    form.append('noise_level', speaker.noise_level);
    form.append('device_type', speaker.device_type);
    if (speaker.email) form.append('speaker_email', speaker.email);
    if (sessionUuid) form.append('session_id', sessionUuid);
    form.append('prompt_bank_version', '2.0');
    if (speaker.age_range) form.append('age_range', speaker.age_range);
    if (speaker.gender)    form.append('gender', speaker.gender);

    try {
      const authHeaders = getAuthHeaders ? await getAuthHeaders() : {};
      const res = await fetch(apiUrl('/api/upload'), {
        method: 'POST',
        headers: authHeaders,
        body: form,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Upload failed');

      setAutoTranscript(data.auto_transcript || '(no transcript)');
      if (data.confidence_warning) {
        setConfidenceWarning(data.confidence_warning);
      }
      setState('done');
      setCompletedCount(c => c + 1);

      setTimeout(() => {
        if (promptIndex + 1 < allPrompts.length) {
          setPromptIndex(i => i + 1);
          setState('idle');
          reset();
          setAutoTranscript('');
          setDurationWarning('');
          setConfidenceWarning('');
        } else {
          setSessionComplete(true);
        }
      }, 2200);
    } catch (err) {
      setUploadError(err.message);
      setState('idle');
      reset();
    }
  }, [speaker, currentPrompt, promptIndex, allPrompts.length, reset, getAuthHeaders, sessionUuid]);

  const handleSkip = useCallback(() => {
    if (promptIndex + 1 < allPrompts.length) {
      setPromptIndex(i => i + 1);
      setState('idle');
      reset();
      setAutoTranscript('');
      setDurationWarning('');
      setConfidenceWarning('');
    } else {
      setSessionComplete(true);
    }
  }, [promptIndex, allPrompts.length, reset]);

  if (sessionComplete) {
    return (
      <div className="session-complete">
        <div className="complete-card">
          <div className="complete-icon">✓</div>
          <h2>Session Complete</h2>
          <p>{completedCount} recordings saved · thank you, {speaker.name.split(' ')[0]}</p>
          <div className="complete-actions">
            <button className="btn-secondary" onClick={onDone}>View Stats</button>
            <button className="btn-primary" onClick={() => {
              setSessionComplete(false);
              setPromptIndex(0);
              setCompletedCount(0);
              setState('idle');
              reset();
            }}>Record Again</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="session-screen">
      {/* Header */}
      <div className="session-header">
        <div className="session-meta">
          <span className="speaker-badge">{speaker.name}</span>
          <span className="lang-badge">{speaker.native_language} · {speaker.region}</span>
        </div>
        <div className="session-progress">
          <span className="progress-text">{completedCount} / {allPrompts.length}</span>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>
        <button
          className="btn-ghost end-session-btn"
          onClick={() => setSessionComplete(true)}
          title="End session early"
        >End Session</button>
      </div>

      {/* Category chip + prompt */}
      <div className="prompt-area">
        <div
          className="category-chip"
          style={{ '--chip-color': CATEGORY_COLORS[currentPrompt.category] }}
        >
          {CATEGORY_LABELS[currentPrompt.category]}
        </div>

        <div className="prompt-text">{currentPrompt.text}</div>

        <div className="prompt-hint">
          Read this naturally — in your own accent, at your normal speaking pace.
          If you naturally mix Hindi and English, do it.
        </div>
      </div>

      {/* Recorder */}
      <div className="recorder-area">
        <VolumeBar volume={volume} isRecording={isRecording} />

        {audioUrl && state !== 'idle' && (
          <audio className="audio-preview" src={audioUrl} controls />
        )}

        <div className="recorder-controls">
          {state === 'idle' && (
            <button className="btn-record" onClick={handleRecord}>
              <span className="rec-dot" />
              Start Recording
            </button>
          )}

          {state === 'recording' && (
            <button className="btn-record recording" onClick={handleRecord}>
              <span className="rec-square" />
              Stop — {duration}s
            </button>
          )}

          {state === 'uploading' && (
            <div className="uploading-state">
              <div className="spinner" />
              <span>{autoTranscript || 'Saving…'}</span>
            </div>
          )}

          {state === 'done' && (
            <div className="saved-flash">
              <span className="saved-icon">✓</span> Saved
              {autoTranscript && autoTranscript !== '(no transcript)' && (
                <div className="transcript-preview">"{autoTranscript}"</div>
              )}
            </div>
          )}
        </div>

        {durationWarning && <div className="error-msg" style={{ color: '#f59e0b' }}>{durationWarning}</div>}
        {confidenceWarning && <div className="error-msg" style={{ color: '#f59e0b' }}>{confidenceWarning}</div>}
        {uploadError && <div className="error-msg">{uploadError}</div>}
        {error && <div className="error-msg">{error}</div>}
      </div>

      {/* Prompt navigation */}
      <div className="prompt-nav">
        <button className="btn-ghost small" onClick={handleSkip}>
          Skip this prompt →
        </button>
        <span className="prompt-counter">
          {promptIndex + 1} of {allPrompts.length}
        </span>
      </div>
    </div>
  );
}

// ── Stats Dashboard ───────────────────────────────────────────────────────────

function StatsDashboard({ onRecord, onAdmin, getAuthHeaders }) {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const headers = getAuthHeaders ? await getAuthHeaders() : {};
        const r = await fetch(apiUrl('/api/stats'), { headers });
        const data = await r.json();
        if (!cancelled) {
          if (!r.ok) {
            const d = data.detail;
            const msg = typeof d === 'string' ? d : d ? JSON.stringify(d) : r.statusText;
            setStats({ error: true, message: msg });
          } else setStats(data);
        }
      } catch {
        if (!cancelled) setStats({ error: true });
      }
    })();
    return () => { cancelled = true; };
  }, [getAuthHeaders]);

  const hours = stats ? Math.floor(stats.total_duration_seconds / 3600) : 0;
  const minutes = stats ? Math.floor((stats.total_duration_seconds % 3600) / 60) : 0;

  return (
    <div className="stats-screen">
      <div className="stats-header">
        <div className="logo-mark small">VCX</div>
        <h2>Collection Progress</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn-secondary" onClick={onAdmin}>Admin</button>
          <button className="btn-primary" onClick={onRecord}>+ New Recording Session</button>
        </div>
      </div>

      {!stats && <div className="loading-text">Loading stats...</div>}

      {stats && stats.error && (
        <div className="error-msg" style={{ margin: '16px 0' }}>
          {stats.message || 'Could not load stats. If the API requires login, ensure you are signed in.'}
        </div>
      )}

      {stats && !stats.error && (
        <>
          <div className="stat-grid">
            <div className="stat-card accent">
              <div className="stat-value">{stats.total_recordings}</div>
              <div className="stat-label">Total Recordings</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{hours}h {minutes}m</div>
              <div className="stat-label">Audio Collected</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats.unique_speakers}</div>
              <div className="stat-label">Unique Speakers</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">
                {stats.total_recordings > 0
                  ? Math.round(stats.total_duration_seconds / stats.total_recordings)
                  : 0}s
              </div>
              <div className="stat-label">Avg Duration</div>
            </div>
          </div>

          <div className="stats-row">
            <div className="stats-panel">
              <h3>By Category</h3>
              {Object.entries(stats.categories || {}).map(([cat, count]) => (
                <div className="bar-row" key={cat}>
                  <span className="bar-label" style={{ color: CATEGORY_COLORS[cat] || '#888' }}>
                    {CATEGORY_LABELS[cat] || cat}
                  </span>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{
                        width: `${(count / Math.max(1, ...Object.values(stats.categories))) * 100}%`,
                        background: CATEGORY_COLORS[cat] || 'var(--accent)',
                      }}
                    />
                  </div>
                  <span className="bar-count">{count}</span>
                </div>
              ))}
              {Object.keys(stats.categories || {}).length === 0 && (
                <div className="empty-state">No recordings yet</div>
              )}
            </div>

            <div className="stats-panel">
              <h3>By Speaker</h3>
              {Object.entries(stats.speakers || {}).map(([spk, count]) => (
                <div className="bar-row" key={spk}>
                  <span className="bar-label">{spk.replace(/_/g, ' ')}</span>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{
                        width: `${(count / Math.max(1, ...Object.values(stats.speakers))) * 100}%`,
                      }}
                    />
                  </div>
                  <span className="bar-count">{count}</span>
                </div>
              ))}
              {Object.keys(stats.speakers || {}).length === 0 && (
                <div className="empty-state">No speakers yet</div>
              )}
            </div>
          </div>

          <div className="target-banner">
            <div className="target-info">
              <span className="target-label">Target: 600 recordings · ~5 hours</span>
              <span className="target-sub">~22 prompts per session (2 identity + 20 sampled)</span>
            </div>
            <div className="target-progress-wrap">
              <div className="target-bar">
                <div
                  className="target-fill"
                  style={{ width: `${Math.min(100, (stats.total_recordings / 600) * 100)}%` }}
                />
              </div>
              <span className="target-pct">
                {Math.round((stats.total_recordings / 600) * 100)}%
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ── Admin Panel ───────────────────────────────────────────────────────────────

function AdminPanel({ onBack }) {
  const [secret, setSecret] = useState(() => localStorage.getItem('vcx_admin_secret') || '');
  const [secretInput, setSecretInput] = useState(secret);
  const [overview, setOverview] = useState(null);
  const [publicStats, setPublicStats] = useState(null);
  const [flagged, setFlagged] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editText, setEditText] = useState('');
  const [actionMsg, setActionMsg] = useState('');
  const [exportLoading, setExportLoading] = useState(false);

  const adminHeaders = { 'X-Stats-Admin-Secret': secret, 'Content-Type': 'application/json' };

  const load = useCallback(async (s) => {
    if (!s) return;
    setLoading(true);
    setError('');
    try {
      const [ovRes, flRes, pubRes] = await Promise.all([
        fetch(apiUrl('/api/admin/stats'), { headers: { 'X-Stats-Admin-Secret': s } }),
        fetch(apiUrl('/api/admin/flagged?limit=50'), { headers: { 'X-Stats-Admin-Secret': s } }),
        fetch(apiUrl('/api/stats')),
      ]);
      if (!ovRes.ok) { setError('Invalid admin secret or server error.'); setLoading(false); return; }
      setOverview(await ovRes.json());
      setFlagged(await flRes.json());
      if (pubRes.ok) setPublicStats(await pubRes.json());
    } catch { setError('Could not reach API.'); }
    setLoading(false);
  }, []);

  const handleExport = async () => {
    setExportLoading(true);
    setActionMsg('');
    try {
      const res = await fetch(apiUrl('/api/export/training?url_ttl=3600'), {
        headers: { 'X-Stats-Admin-Secret': secret },
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setActionMsg(`Export error: ${d.detail || res.statusText}`);
        setExportLoading(false);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `voicera_training_${new Date().toISOString().slice(0,10)}.jsonl`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setActionMsg('Export downloaded ✓');
    } catch (e) {
      setActionMsg(`Export failed: ${e.message}`);
    }
    setExportLoading(false);
  };

  const handleSecretSubmit = (e) => {
    e.preventDefault();
    localStorage.setItem('vcx_admin_secret', secretInput);
    setSecret(secretInput);
    load(secretInput);
  };

  useEffect(() => { if (secret) load(secret); }, [secret, load]);

  const doAction = async (id, action, finalTranscript) => {
    setActionMsg('');
    const body = action === 'approve'
      ? { action, final_transcript: finalTranscript }
      : { action };
    const res = await fetch(apiUrl(`/api/admin/recordings/${id}`), {
      method: 'PATCH', headers: adminHeaders, body: JSON.stringify(body),
    });
    if (res.ok) {
      setActionMsg(`${action === 'approve' ? 'Approved ✓' : 'Rejected ✗'} — ${id}`);
      setEditingId(null);
      load(secret);
    } else {
      const d = await res.json();
      setActionMsg(`Error: ${d.detail || res.statusText}`);
    }
  };

  const totalFlagged = overview
    ? Object.values(overview.breakdown).reduce((s, v) => s + (v.flagged || 0), 0)
    : 0;
  const breakdown = overview?.breakdown || {};

  return (
    <div className="stats-screen">
      <div className="stats-header">
        <div className="logo-mark small">VCX</div>
        <h2>Admin — Review Queue</h2>
        <div style={{ display: 'flex', gap: 8 }}>
          {secret && (
            <button
              className="btn-primary"
              style={{ fontSize: 12 }}
              onClick={handleExport}
              disabled={exportLoading}
            >
              {exportLoading ? 'Exporting…' : '↓ Export Training Data'}
            </button>
          )}
          <button className="btn-secondary" onClick={onBack}>← Back</button>
        </div>
      </div>

      {/* Secret input */}
      {!secret && (
        <form onSubmit={handleSecretSubmit} style={{ margin: '24px 0', display: 'flex', gap: 8 }}>
          <input
            type="password"
            className="form-input"
            placeholder="Admin secret (STATS_ADMIN_SECRET)"
            value={secretInput}
            onChange={e => setSecretInput(e.target.value)}
            style={{ flex: 1 }}
          />
          <button type="submit" className="btn-primary">Unlock</button>
        </form>
      )}
      {secret && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '8px 0 16px' }}>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>Authenticated as admin</span>
          <button className="btn-ghost" style={{ fontSize: 11, padding: '2px 8px' }}
            onClick={() => { setSecret(''); setSecretInput(''); localStorage.removeItem('vcx_admin_secret'); setOverview(null); setFlagged(null); }}>
            Sign out
          </button>
        </div>
      )}

      {error && <div className="error-msg" style={{ marginBottom: 16 }}>{error}</div>}
      {actionMsg && (
        <div className={`error-msg`} style={{ marginBottom: 16, background: actionMsg.startsWith('Error') ? undefined : '#1a2e1a', color: actionMsg.startsWith('Error') ? undefined : '#6fcf6f', border: actionMsg.startsWith('Error') ? undefined : '1px solid #2e4d2e' }}>
          {actionMsg}
        </div>
      )}
      {loading && <div className="loading-text">Loading…</div>}

      {/* Stats overview */}
      {(overview || publicStats) && (
        <>
          {publicStats && (
            <div className="stat-grid" style={{ marginBottom: 16 }}>
              <div className="stat-card accent">
                <div className="stat-value">{publicStats.total_recordings}</div>
                <div className="stat-label">Total Recordings</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{publicStats.unique_speakers}</div>
                <div className="stat-label">Speakers</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {Math.floor(publicStats.total_duration_seconds / 3600)}h{' '}
                  {Math.floor((publicStats.total_duration_seconds % 3600) / 60)}m
                </div>
                <div className="stat-label">Total Audio</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {publicStats.total_recordings > 0
                    ? Math.round(publicStats.total_duration_seconds / publicStats.total_recordings)
                    : 0}s
                </div>
                <div className="stat-label">Avg Duration</div>
              </div>
            </div>
          )}
          {overview && (
            <div className="stat-grid" style={{ marginBottom: 24 }}>
              {Object.entries(breakdown).map(([status, v]) => (
                <div key={status} className={`stat-card ${status === 'completed' ? 'accent' : ''}`}>
                  <div className="stat-value">{v.total}</div>
                  <div className="stat-label">{status}{v.flagged ? ` (${v.flagged} ⚑)` : ''}</div>
                </div>
              ))}
              <div className="stat-card" style={{ borderColor: totalFlagged > 0 ? 'var(--error, #e05)' : undefined }}>
                <div className="stat-value" style={{ color: totalFlagged > 0 ? 'var(--error, #e05)' : undefined }}>{totalFlagged}</div>
                <div className="stat-label">Awaiting Review</div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Flagged queue */}
      {flagged && flagged.total === 0 && (
        <div className="empty-state" style={{ padding: 32 }}>No flagged recordings — queue is clear ✓</div>
      )}

      {flagged && flagged.recordings.map(r => (
        <div key={r.id} style={{
          background: 'var(--surface, #111)', border: '1px solid var(--border, #222)',
          borderRadius: 8, padding: 16, marginBottom: 12,
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8, marginBottom: 10 }}>
            <div>
              <span style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--muted)' }}>{r.id}</span>
              <span style={{ marginLeft: 8, fontSize: 11, color: 'var(--muted)' }}>
                {r.transcription_engine} · WER {r.wer_score != null ? (r.wer_score * 100).toFixed(0) + '%' : 'n/a'} · {r.native_language} · {r.duration_seconds?.toFixed(1)}s
              </span>
            </div>
            <span style={{ fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap' }}>
              {new Date(r.timestamp).toLocaleString()}
            </span>
          </div>

          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 2 }}>PROMPT</div>
            <div style={{ fontSize: 14, color: '#ccc', fontStyle: 'italic' }}>{r.prompt_text}</div>
          </div>
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 2 }}>TRANSCRIPT</div>
            <div style={{ fontSize: 14, color: '#f88', fontFamily: 'monospace' }}>{r.auto_transcript || '(empty)'}</div>
          </div>

          {editingId === r.id ? (
            <div>
              <textarea
                className="form-input"
                style={{ width: '100%', minHeight: 60, marginBottom: 8, fontFamily: 'monospace', fontSize: 13, boxSizing: 'border-box' }}
                value={editText}
                onChange={e => setEditText(e.target.value)}
              />
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn-primary" style={{ fontSize: 12 }}
                  onClick={() => doAction(r.id, 'approve', editText)}>
                  Confirm Approve
                </button>
                <button className="btn-ghost" style={{ fontSize: 12 }}
                  onClick={() => setEditingId(null)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn-primary" style={{ fontSize: 12 }}
                onClick={() => { setEditingId(r.id); setEditText(r.auto_transcript || ''); }}>
                ✓ Approve / Edit
              </button>
              <button className="btn-secondary" style={{ fontSize: 12, borderColor: '#e05', color: '#e05' }}
                onClick={() => doAction(r.id, 'reject')}>
                ✗ Reject
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── App Root ──────────────────────────────────────────────────────────────────

const VIEWS = { STATS: 'stats', SETUP: 'setup', RECORDING: 'recording', ADMIN: 'admin' };

function generateSessionId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `sess_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 12)}`;
}

export default function App() {
  /** null = still resolving; 'local' = DATABASE_URL unset on server; 'postgres' = auth required */
  const [authMode, setAuthMode] = useState(null);
  const [sessionUser, setSessionUser] = useState(undefined);
  const [view, setView] = useState(VIEWS.STATS);
  const [speaker, setSpeaker] = useState(null);
  const [prompts, setPrompts] = useState([]);
  const [promptsLoading, setPromptsLoading] = useState(false);
  const [promptsError, setPromptsError] = useState('');
  const [sessionId, setSessionId] = useState('');

  const refreshUser = useCallback(async () => {
    const token = getAccessToken();
    if (!token) {
      setSessionUser(null);
      return;
    }
    try {
      const res = await fetch(apiUrl('/api/auth/me'), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        clearAccessToken();
        setSessionUser(null);
        return;
      }
      const u = await res.json();
      setSessionUser({ id: u.id, email: u.email, name: u.name });
    } catch {
      clearAccessToken();
      setSessionUser(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const hr = await fetch(apiUrl('/api/health'));
        const health = hr.ok ? await hr.json() : {};
        if (cancelled) return;
        if (!health.postgres) {
          setAuthMode('local');
          setSessionUser({ id: '', email: '', name: '' });
          return;
        }
        setAuthMode('postgres');
        const token = getAccessToken();
        if (!token) {
          setSessionUser(null);
          return;
        }
        await refreshUser();
      } catch {
        if (!cancelled) {
          setAuthMode('postgres');
          setSessionUser(null);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshUser]);

  const getAuthHeaders = useCallback(async () => {
    const t = getAccessToken();
    if (!t) return {};
    return { Authorization: `Bearer ${t}` };
  }, []);

  // Fetch stratified sample of 20 prompts when entering recording session
  const fetchSessionPrompts = useCallback(() => {
    setPromptsLoading(true);
    setPromptsError('');
    setPrompts([]);
    fetch(apiUrl('/api/prompts?count=20'))
      .then((r) => {
        if (!r.ok) throw new Error('Failed to load prompts');
        return r.json();
      })
      .then((data) => setPrompts(data.prompts || []))
      .catch(() => setPromptsError('Could not load prompts. Check API URL and try again.'))
      .finally(() => setPromptsLoading(false));
  }, []);

  const [savedProfile, setSavedProfile] = useState(() =>
    sessionUser?.id ? loadSavedProfile(sessionUser.id) : null
  );

  const handleSetupComplete = useCallback((speakerData) => {
    setSpeaker(speakerData);
    setSavedProfile(speakerData);
    setSessionId(generateSessionId());
    setView(VIEWS.RECORDING);
    fetchSessionPrompts();
  }, [fetchSessionPrompts]);

  const handleLogout = useCallback(async () => {
    clearAccessToken();
    setSessionUser(null);
    setView(VIEWS.STATS);
    setSpeaker(null);
  }, []);

  if (authMode === null || sessionUser === undefined) {
    return (
      <div className="app">
        <div className="loading-text" style={{ padding: 48, textAlign: 'center' }}>Loading…</div>
      </div>
    );
  }

  if (authMode === 'postgres' && !sessionUser) {
    return (
      <div className="app">
        <ApiStatusBar />
        <LoginScreen onLoggedIn={(user) => setSessionUser(user)} />
      </div>
    );
  }

  return (
    <div className="app">
      <ApiStatusBar />
      {authMode === 'postgres' && sessionUser?.email ? (
        <UserBar user={sessionUser} onLogout={handleLogout} />
      ) : (
        <div className="user-bar">
          <span className="user-email">Local mode (no DATABASE_URL) — JSONL + disk only</span>
        </div>
      )}
      {view === VIEWS.STATS && (
        <StatsDashboard
          onRecord={() => setView(VIEWS.SETUP)}
          onAdmin={() => setView(VIEWS.ADMIN)}
          getAuthHeaders={getAuthHeaders}
        />
      )}
      {view === VIEWS.ADMIN && (
        <AdminPanel onBack={() => setView(VIEWS.STATS)} />
      )}
      {view === VIEWS.SETUP && !savedProfile && (
        <SpeakerSetup onComplete={handleSetupComplete} user={sessionUser} />
      )}
      {view === VIEWS.SETUP && savedProfile && (
        <SessionEnvSetup
          profile={savedProfile}
          onComplete={handleSetupComplete}
          onReset={() => {
            if (sessionUser?.id) localStorage.removeItem(`${SPEAKER_PROFILE_KEY}_${sessionUser.id}`);
            setSavedProfile(null);
          }}
        />
      )}
      {view === VIEWS.RECORDING && speaker && promptsLoading && (
        <div className="setup-screen">
          <div className="setup-card">
            <p className="loading-text" style={{ textAlign: 'center', padding: 24 }}>
              Loading session prompts…
            </p>
          </div>
        </div>
      )}
      {view === VIEWS.RECORDING && speaker && !promptsLoading && promptsError && (
        <div className="setup-screen">
          <div className="setup-card">
            <div className="error-msg" style={{ marginBottom: 16 }}>{promptsError}</div>
            <button type="button" className="btn-primary" onClick={fetchSessionPrompts}>
              Retry
            </button>
            <button type="button" className="btn-ghost" style={{ marginLeft: 8 }} onClick={() => setView(VIEWS.SETUP)}>
              Back
            </button>
          </div>
        </div>
      )}
      {view === VIEWS.RECORDING && speaker && !promptsLoading && !promptsError && prompts.length > 0 && (
        <RecordingSession
          speaker={speaker}
          prompts={prompts}
          onDone={() => setView(VIEWS.STATS)}
          getAuthHeaders={getAuthHeaders}
          sessionId={sessionId}
        />
      )}
    </div>
  );
}
