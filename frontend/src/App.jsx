import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'

function App() {
  // ==========================================
  // BOOK CATALOG DATA STATES
  // ==========================================
  const [randomBooks, setRandomBooks] = useState([])
  const [searchMode, setSearchMode] = useState("name")
  const [query, setQuery] = useState("")
  const [searchResults, setSearchResults] = useState([])
  const [isSearching, setIsSearching] = useState(false)
  
  // ==========================================
  // AUTHENTICATION STATES
  // ==========================================
  const [token, setToken] = useState(localStorage.getItem('token') || null)
  const [currentUser, setCurrentUser] = useState(localStorage.getItem('username') || null)
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [authMode, setAuthMode] = useState('login') // 'login' or 'register'
  const [authData, setAuthData] = useState({ username: '', email: '', password: '' })
  const [authError, setAuthError] = useState('')

  // ==========================================
  // CHATBOT STATES
  // ==========================================
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [chatMessage, setChatMessage] = useState("")
  const [chatHistory, setChatHistory] = useState([
    { role: 'bot', text: 'I am AI-Goldfish! What would you like to ask about books?' }
  ])
  const chatEndRef = useRef(null)

  // Auto scroll to the latest message
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [chatHistory, isChatOpen])

  // Automatically clear auth form inputs on modal switch or close
  useEffect(() => {
    setAuthData({ username: '', email: '', password: '' })
    setAuthError('')
  }, [authMode, showAuthModal])

  // Fetch random book recommendations
  const fetchRandom = () => {
    fetch('http://127.0.0.1:8000/api/random')
      .then(res => res.json())
      .then(data => setRandomBooks(data.data))
      .catch(err => console.log("Backend server is offline", err))
  }

  useEffect(() => {
    fetchRandom()
    const interval = setInterval(fetchRandom, 10000)
    return () => clearInterval(interval)
  }, [])

  // Execute catalog search
  const handleSearch = async () => {
    if (!query.trim()) return
    setIsSearching(true)
    try {
      const response = await fetch('http://127.0.0.1:8000/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query, mode: searchMode, limit: 20 })
      })
      const data = await response.json()
      setSearchResults(data.data || [])
    } catch (error) {
      console.error("Search Error:", error)
    }
    setIsSearching(false)
  }

  // ==========================================
  // AUTHENTICATION ACTIONS
  // ==========================================
  const handleAuthSubmit = async (e) => {
    e.preventDefault()
    setAuthError('')
    
    const url = authMode === 'login' ? 'http://127.0.0.1:8000/api/auth/login' : 'http://127.0.0.1:8000/api/auth/register'
    const payload = authMode === 'login' 
      ? { username: authData.username, password: authData.password }
      : { username: authData.username, email: authData.email, password: authData.password }

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const data = await res.json()

      if (!res.ok) {
        setAuthError(data.detail || 'An error occurred!')
        return
      }

      if (authMode === 'login') {
        setToken(data.access_token)
        setCurrentUser(data.username)
        localStorage.setItem('token', data.access_token)
        localStorage.setItem('username', data.username)
        setShowAuthModal(false)
      } else {
        alert('Registration successful! Please login.')
        setAuthMode('login')
      }
    } catch (err) {
      setAuthError('Unable to connect to the server.')
    }
  }

  const handleLogout = () => {
    setToken(null)
    setCurrentUser(null)
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    setChatHistory([{ role: 'bot', text: 'I am AI-Goldfish! What would you like to ask about books?' }])
    setIsChatOpen(false)
  }

  // ==========================================
  // SECURE CHAT ACTION
  // ==========================================
  const handleSendMessage = async () => {
    if (!chatMessage.trim()) return;
    
    if (!token) {
      setShowAuthModal(true)
      return
    }

    const newHistory = [...chatHistory, { role: 'user', text: chatMessage }];
    setChatHistory(newHistory);
    const currentMsg = chatMessage;
    setChatMessage(""); 

    try {
      const response = await fetch('http://127.0.0.1:8000/api/chat', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}` 
        },
        body: JSON.stringify({ 
          message: currentMsg,
          session_id: "web_browser_tab"
        })
      });
      
      if (response.status === 401) {
        handleLogout();
        alert("Session expired. Please login again!");
        setShowAuthModal(true);
        return;
      }

      const data = await response.json();
      setChatHistory([...newHistory, { role: 'bot', text: data.reply }]);
    } catch (error) {
      setChatHistory([...newHistory, { role: 'bot', text: 'Network error!' }]);
    }
  }

  // Slice to exactly 4 books for a balanced 2x2 layout
  const displayedBooks = randomBooks.slice(0, 4);

  // ==========================================
  // RENDER INTERFACE
  // ==========================================
  return (
    <div style={styles.container}>
      
      {/* CSS KEYFRAMES */}
      <style>
        {`
          @keyframes heartbeat {
            0% { transform: scale(1); }
            14% { transform: scale(1.15); }
            28% { transform: scale(1); }
            42% { transform: scale(1.15); }
            70% { transform: scale(1); }
          }
          .bot-btn {
            position: fixed; bottom: 40px; right: 40px; width: 55px; height: 55px;
            border-radius: 50%; background-color: #1a1a1a; color: white; border: none;
            cursor: pointer; display: flex; align-items: center; justify-content: center;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2); animation: heartbeat 2s infinite;
            transition: all 0.3s ease; z-index: 1000;
          }
          .bot-btn:hover {
            background-color: #333; transform: scale(1.1); animation: none;
          }
          .auth-input {
            width: 100%; padding: 12px; margin-bottom: 15px; border: 1px solid #e0e0e0; 
            background-color: #fff; font-size: 14px; box-sizing: border-box; outline: none;
          }
        `}
      </style>

      {/* AUTHENTICATION POPUP MODAL */}
      {showAuthModal && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <div style={{display:'flex', justifyContent:'space-between', marginBottom:'20px'}}>
              <h3 style={{margin:0, letterSpacing: '2px'}}>{authMode === 'login' ? 'LOGIN' : 'REGISTER'}</h3>
              <button onClick={() => setShowAuthModal(false)} style={{background:'none', border:'none', fontSize: '14px', cursor:'pointer', fontWeight:'bold'}}>X</button>
            </div>
            
            {authError && <p style={{color:'red', fontSize:'12px', marginTop:0}}>{authError}</p>}
            
            <form onSubmit={handleAuthSubmit} autoComplete="off">
              <input 
                className="auth-input" type="text" placeholder="Username" required
                autoComplete="off"
                value={authData.username} onChange={e => setAuthData({...authData, username: e.target.value})}
              />
              {authMode === 'register' && (
                <input 
                  className="auth-input" type="email" placeholder="Email Address" required
                  autoComplete="off"
                  value={authData.email} onChange={e => setAuthData({...authData, email: e.target.value})}
                />
              )}
              <input 
                className="auth-input" type="password" placeholder="Password" required
                autoComplete="new-password"
                value={authData.password} onChange={e => setAuthData({...authData, password: e.target.value})}
              />
              <button type="submit" style={styles.authSubmitBtn}>
                {authMode === 'login' ? 'LOGIN' : 'CREATE ACCOUNT'}
              </button>
            </form>

            <div style={{marginTop:'20px', textAlign:'center', fontSize: '12px', letterSpacing: '1px'}}>
              {authMode === 'login' ? (
                <span>Don't have an account? <b style={{textDecoration:'underline', cursor:'pointer'}} onClick={() => setAuthMode('register')}>Register now</b></span>
              ) : (
                <span>Already have an account? <b style={{textDecoration:'underline', cursor:'pointer'}} onClick={() => setAuthMode('login')}>Login</b></span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* LEFT SIDEBAR CONTROLLER */}
      <aside style={styles.sidebar}>
        <div style={styles.logo}>SMART LIBRARY</div>

        {/* ACCOUNT PROFILE PANEL */}
        <div style={styles.userPanel}>
          {currentUser ? (
            <div style={{textAlign: 'center'}}>
              <div style={{fontSize: '10px', color: '#888', letterSpacing: '1px', marginBottom: '4px'}}>WELCOME BACK</div>
              <div style={{fontWeight: '700', fontSize: '14px', marginBottom: '12px', letterSpacing: '0.5px'}}>{currentUser.toUpperCase()}</div>
              <button onClick={handleLogout} style={styles.logoutBtn}>LOGOUT</button>
            </div>
          ) : (
            <button onClick={() => setShowAuthModal(true)} style={styles.loginBtn}>LOGIN TO CHAT</button>
          )}
        </div>
        
        <div style={styles.controlGroup}>
          <label style={styles.label}>SEARCH MODE</label>
          <button 
            onClick={() => setSearchMode('name')}
            style={{...styles.modeBtn, backgroundColor: searchMode === 'name' ? '#1a1a1a' : 'transparent', color: searchMode === 'name' ? '#fff' : '#1a1a1a'}}
          >
            By Title
          </button>
          <button 
            onClick={() => setSearchMode('idea')}
            style={{...styles.modeBtn, backgroundColor: searchMode === 'idea' ? '#1a1a1a' : 'transparent', color: searchMode === 'idea' ? '#fff' : '#1a1a1a'}}
          >
            By Idea
          </button>
        </div>

        <div style={styles.controlGroup}>
          <label style={styles.label}>INPUT</label>
          <textarea 
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={searchMode === 'name' ? "Enter book title..." : "Describe the plot or story idea..."}
            style={styles.textarea}
          />
        </div>

        <button onClick={handleSearch} style={styles.searchBtn}>
          {isSearching ? 'PROCESSING...' : 'SEARCH'}
        </button>
      </aside>

      {/* RIGHT MAIN LAYOUT BLOCK */}
      <main style={styles.mainContent}>
        {searchResults.length === 0 ? (
          <div style={styles.discoveryGrid}>
            <h2 style={styles.sectionTitle}>CURATED DISCOVERY</h2>
            
            {/* Fixed 2-column grid layout */}
            <div style={{...styles.grid, gridTemplateColumns: 'repeat(2, 1fr)'}}>
              {displayedBooks.map((book, idx) => (
                <div key={idx} style={styles.gridCard}>
                  <img src={book.thumbnail || 'https://via.placeholder.com/150'} alt="cover" style={styles.gridImg} />
                  <div style={styles.cardInfo}>
                    <div style={styles.bookTitleSmall}>{book.title}</div>
                    <div style={styles.bookAuthorSmall}>{book.authors}</div>
                  </div>
                </div>
              ))}
            </div>
            <p style={styles.refreshNote}>Refreshing collection in 10s...</p>
          </div>
        ) : (
          <div style={styles.resultsList}>
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
                <h2 style={styles.sectionTitle}>RESULTS</h2>
                <button onClick={() => setSearchResults([])} style={styles.closeBtn}>CLOSE RESULTS</button>
            </div>
            {searchResults.map((book, idx) => (
              <div key={idx} style={styles.listRow}>
                <img src={book.thumbnail || 'https://via.placeholder.com/150'} alt="cover" style={styles.listImg} />
                <div style={styles.listText}>
                  <h3 style={styles.bookTitleLarge}>{book.title}</h3>
                  <p style={styles.bookAuthorLarge}>{book.authors}</p>
                  <p style={styles.bookSummary}>{book.description || book.short_summary || "No summary available."}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* MINI CHATBOT ICON */}
      <button 
        onClick={() => {
          if (!token) setShowAuthModal(true);
          else setIsChatOpen(!isChatOpen);
        }} 
        className="bot-btn"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="11" width="18" height="10" rx="2"></rect>
          <circle cx="12" cy="5" r="2"></circle>
          <path d="M12 7v4"></path>
          <line x1="8" y1="16" x2="8.01" y2="16"></line>
          <line x1="16" y1="16" x2="16.01" y2="16"></line>
        </svg>
      </button>

      {/* CHAT INTERACTION CONSOLE */}
      {isChatOpen && (
        <div style={styles.chatBox}>
          <div style={styles.chatHeader}>
            <span>AI-GOLDFISH</span>
            <button onClick={() => setIsChatOpen(false)} style={{background:'none', border:'none', color:'white', cursor:'pointer', fontWeight:'bold'}}>X</button>
          </div>
          
          <div style={styles.chatBody}>
            {chatHistory.map((msg, idx) => (
              <div key={idx} style={{ textAlign: msg.role === 'user' ? 'right' : 'left', marginBottom: '15px' }}>
                <div style={{ 
                  display: 'inline-block', 
                  padding: '12px 16px', 
                  borderRadius: '2px', 
                  backgroundColor: msg.role === 'user' ? '#1a1a1a' : '#f4f3ec', 
                  color: msg.role === 'user' ? 'white' : 'black',
                  maxWidth: '90%', 
                  fontSize: '13px', 
                  lineHeight: '1.6',
                  textAlign: 'left'
                }}>
                  {msg.role === 'user' ? (
                    msg.text
                  ) : (
                    <ReactMarkdown 
                      components={{ 
                        img: () => null,
                        p: ({node, ...props}) => <p style={{margin: '0 0 8px 0', lineHeight: '1.5'}} {...props} />,
                        ul: ({node, ...props}) => <ul style={{margin: '0 0 10px 0', paddingLeft: '20px'}} {...props} />,
                        li: ({node, ...props}) => <li style={{marginBottom: '6px'}} {...props} />,
                        strong: ({node, ...props}) => <strong style={{color: '#10b981'}} {...props} />
                      }}
                    >
                      {msg.text || "Reconnecting to brain..."}
                    </ReactMarkdown>
                  )}
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          <div style={{ display: 'flex', borderTop: '1px solid #e0e0e0' }}>
            <input 
              style={styles.chatInput} 
              placeholder="Type a message..." 
              value={chatMessage}
              onChange={(e) => setChatMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
            />
            <button 
              onClick={handleSendMessage} 
              style={{ padding: '0 20px', background: 'white', border: 'none', fontWeight: 'bold', cursor: 'pointer', borderTop: '1px solid #e0e0e0', color: '#1a1a1a', letterSpacing: '1px', fontSize: '12px' }}
            >
              SEND
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

// ==========================================
// COMPACT, NARROW SIDEBAR & SPACE RECOVERY STYLES
// ==========================================
const styles = {
  container: { 
    display: 'flex', 
    height: '100vh', 
    backgroundColor: '#faf9f6', 
    color: '#1a1a1a', 
    overflow: 'hidden', 
    fontFamily: 'system-ui, sans-serif',
    width: '100%',
    maxWidth: '1440px', // Giới hạn chiều rộng tối đa để web trông sang trọng
    margin: '0 auto',   // Căn giữa container trên màn hình lớn
    borderLeft: '1px solid #e0e0e0', // Giữ đường kẻ viền trái
    borderRight: '1px solid #e0e0e0'  // Giữ đường kẻ viền phải
  },
  
  // NARROWED SIDEBAR (Reduced width to 260px and horizontally padded cleanly)
  sidebar: { width: '260px', padding: '25px 18px', borderRight: '1px solid #e0e0e0', display: 'flex', flexDirection: 'column', zIndex: 10, overflowY: 'auto' },
  logo: { fontSize: '18px', fontWeight: '800', letterSpacing: '4px', marginBottom: '20px', textAlign: 'center' },
  
  controlGroup: { marginBottom: '20px' },
  label: { fontSize: '10px', fontWeight: 'bold', color: '#888', letterSpacing: '2px', marginBottom: '8px', display: 'block', textAlign: 'center' },
  modeBtn: { width: '100%', padding: '10px', border: '1px solid #1a1a1a', marginBottom: '8px', cursor: 'pointer', fontSize: '12px', fontWeight: '600', transition: '0.3s' },
  textarea: { width: '100%', height: '80px', padding: '12px', border: '1px solid #e0e0e0', backgroundColor: '#fff', fontSize: '13px', boxSizing: 'border-box', outline: 'none', resize: 'none' },
  searchBtn: { padding: '12px', backgroundColor: '#1a1a1a', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 'bold', letterSpacing: '2px', marginTop: '0' },
  
  userPanel: { padding: '15px', border: '1px solid #1a1a1a', marginBottom: '20px', backgroundColor: '#fff' },
  loginBtn: { width: '100%', padding: '10px', backgroundColor: '#1a1a1a', color: 'white', border: 'none', cursor: 'pointer', fontWeight: 'bold', letterSpacing: '1px', fontSize: '12px' },
  logoutBtn: { width: '100%', padding: '8px', fontSize: '11px', backgroundColor: 'transparent', color: '#1a1a1a', border: '1px solid #1a1a1a', cursor: 'pointer', fontWeight: 'bold', letterSpacing: '1px' },
  
  mainContent: { flex: 1, padding: '40px 60px', overflowY: 'auto' },
  sectionTitle: { fontSize: '24px', fontWeight: '300', letterSpacing: '5px', marginBottom: '30px', textTransform: 'uppercase', textAlign: 'center' },
  
  // High spacing gaps inside grid layout
  grid: { display: 'grid', gap: '60px 100px' },
  gridCard: { textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' },
  
  // Fixed size matrix to prevent image scaling visual bugs
  gridImg: { width: '160px', height: '240px', objectFit: 'cover', borderRadius: '2px', boxShadow: '0 10px 25px rgba(0,0,0,0.06)', margin: '0 auto' },
  bookTitleSmall: { fontSize: '14px', fontWeight: '700', marginTop: '15px', maxWidth: '280px', lineHeight: '1.4' },
  bookAuthorSmall: { fontSize: '12px', color: '#666', marginTop: '5px' },
  refreshNote: { marginTop: '40px', fontSize: '11px', fontStyle: 'italic', color: '#aaa' },

  // Generous vertical list margins
  listRow: { display: 'flex', gap: '40px', marginBottom: '60px', paddingBottom: '40px', borderBottom: '1px solid #f0f0f0' },
  listImg: { width: '130px', height: '195px', objectFit: 'cover', borderRadius: '2px', boxShadow: '0 8px 20px rgba(0,0,0,0.05)', flexShrink: 0 },
  listText: { flex: 1 },
  bookTitleLarge: { fontSize: '20px', fontWeight: '700', margin: '0 0 5px 0' },
  bookAuthorLarge: { fontSize: '14px', color: '#888', marginBottom: '15px' },
  bookSummary: { fontSize: '14px', lineHeight: '1.6', color: '#444' },
  closeBtn: { background: 'none', border: '1px solid #ccc', padding: '5px 15px', cursor: 'pointer', fontSize: '11px', letterSpacing: '1px', fontWeight: 'bold' },

  chatBox: { position: 'fixed', bottom: '105px', right: '40px', width: '300px', backgroundColor: '#fff', border: '1px solid #e0e0e0', overflow: 'hidden', boxShadow: '0 20px 40px rgba(0,0,0,0.1)', zIndex: 1000 },
  chatHeader: { padding: '12px 16px', backgroundColor: '#1a1a1a', color: '#fff', fontSize: '12px', fontWeight: 'bold', letterSpacing: '2px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }, 
  chatBody: { padding: '16px', fontSize: '13px', height: '260px', overflowY: 'auto', backgroundColor: '#fff' },
  chatInput: { width: '100%', padding: '15px', border: 'none', outline: 'none', fontSize: '13px', backgroundColor: '#fff' },

  modalOverlay: { position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(255,255,255,0.85)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 9999, backdropFilter: 'blur(2px)' },
  modalContent: { backgroundColor: '#fff', padding: '40px', border: '1px solid #1a1a1a', width: '320px', boxShadow: '0 10px 30px rgba(0,0,0,0.05)' },
  authSubmitBtn: { width: '100%', padding: '15px', backgroundColor: '#1a1a1a', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 'bold', marginTop: '10px', letterSpacing: '2px', fontSize: '12px' }
}

export default App