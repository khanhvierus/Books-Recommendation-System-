import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'

function App() {
  // ==========================================
  // BOOK CATALOG & SEARCH STATES
  // ==========================================
  const [randomBooks, setRandomBooks] = useState([])
  const [searchMode, setSearchMode] = useState("name")
  const [query, setQuery] = useState("")
  const [searchResults, setSearchResults] = useState([])
  const [isSearching, setIsSearching] = useState(false)
  
  // ==========================================
  // FILTER & PAGINATION STATES
  // ==========================================
  const [availableFilters, setAvailableFilters] = useState({ authors: [], categories: [] })
  const [selectedAuthors, setSelectedAuthors] = useState([])
  const [selectedCategories, setSelectedCategories] = useState([])
  const [currentPage, setCurrentPage] = useState(0)
  
  const [catSearchTerm, setCatSearchTerm] = useState("")
  const [authSearchTerm, setAuthSearchTerm] = useState("")
  
  // ==========================================
  // DETAIL PAGE & CAROUSEL STATES
  // ==========================================
  const [selectedBook, setSelectedBook] = useState(null) 
  const [relatedBooks, setRelatedBooks] = useState([]) 
  const [carouselIndex, setCarouselIndex] = useState(0) 
  const [isCatExpanded, setIsCatExpanded] = useState(false) 
  const [isAuthExpanded, setIsAuthExpanded] = useState(false) 
  
  // ==========================================
  // AUTHENTICATION STATES
  // ==========================================
  const [token, setToken] = useState(localStorage.getItem('token') || null)
  const [currentUser, setCurrentUser] = useState(localStorage.getItem('username') || null)
  const [showAuthModal, setShowAuthModal] = useState(false)
  const [authMode, setAuthMode] = useState('login')
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

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [chatHistory, isChatOpen])

  useEffect(() => {
    setAuthData({ username: '', email: '', password: '' })
    setAuthError('')
  }, [authMode, showAuthModal])

  // ==========================================
  // DATA FETCHING
  // ==========================================
  useEffect(() => {
    const fetchRandom = () => {
      fetch('http://127.0.0.1:8000/api/random')
        .then(res => res.json())
        .then(data => setRandomBooks(data.data))
        .catch(err => console.log("Backend offline", err))
    }
    fetchRandom()
    const interval = setInterval(fetchRandom, 10000)

    fetch('http://127.0.0.1:8000/api/filters')
      .then(res => res.json())
      .then(data => setAvailableFilters(data))
      .catch(err => console.log("Filter API error", err))

    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (!selectedBook) {
      setRelatedBooks([])
      return
    }
    
    setRelatedBooks([])
    setCarouselIndex(0) 

    fetch('http://127.0.0.1:8000/api/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        query: selectedBook.title, 
        mode: "name", 
        limit: 15 
      })
    })
    .then(res => res.json())
    .then(data => {
      const filtered = (data.data || []).filter(b => b.title.toLowerCase().trim() !== selectedBook.title.toLowerCase().trim())
      setRelatedBooks(filtered)
    })
    .catch(err => console.error("Error fetching related books:", err))
  }, [selectedBook])

  const handleSearch = async () => {
    if (!query.trim() && selectedAuthors.length === 0 && selectedCategories.length === 0) return
    setIsSearching(true)
    setSelectedBook(null) 
    try {
      const response = await fetch('http://127.0.0.1:8000/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query: query, 
          mode: searchMode, 
          limit: 20, 
          authors: selectedAuthors,
          categories: selectedCategories
        })
      })
      const data = await response.json()
      setSearchResults(data.data || [])
      setCurrentPage(0) 
    } catch (error) {
      console.error("Search Error:", error)
    }
    setIsSearching(false)
  }

  const handleClearFilters = () => {
    setSelectedAuthors([])
    setSelectedCategories([])
    setCatSearchTerm("")
    setAuthSearchTerm("")
  }

  const toggleAuthor = (author) => {
    setSelectedAuthors(prev => prev.includes(author) ? prev.filter(a => a !== author) : [...prev, author])
  }
  const toggleCategory = (category) => {
    setSelectedCategories(prev => prev.includes(category) ? prev.filter(c => c !== category) : [...prev, category])
  }

  // ==========================================
  // AUTH & CHAT ACTIONS
  // ==========================================
  const handleAuthSubmit = async (e) => {
    e.preventDefault()
    setAuthError('')
    const url = authMode === 'login' ? 'http://127.0.0.1:8000/api/auth/login' : 'http://127.0.0.1:8000/api/auth/register'
    const payload = authMode === 'login' 
      ? { username: authData.username, password: authData.password }
      : { username: authData.username, email: authData.email, password: authData.password }

    try {
      const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      const data = await res.json()
      if (!res.ok) return setAuthError(data.detail || 'An error occurred!')
      if (authMode === 'login') {
        setToken(data.access_token); setCurrentUser(data.username)
        localStorage.setItem('token', data.access_token); localStorage.setItem('username', data.username)
        setShowAuthModal(false)
      } else {
        alert('Registration successful! Please login.'); setAuthMode('login')
      }
    } catch (err) { setAuthError('Unable to connect to the server.') }
  }

  const handleLogout = () => {
    setToken(null); setCurrentUser(null); localStorage.removeItem('token'); localStorage.removeItem('username')
    setChatHistory([{ role: 'bot', text: 'I am AI-Goldfish! What would you like to ask about books?' }]); setIsChatOpen(false)
    
    setSelectedAuthors([]);
    setSelectedCategories([]);
    setQuery("");
    setSearchResults([]);
    setSelectedBook(null);
    setRelatedBooks([]);
    setCurrentPage(0);
  }

  const handleSendMessage = async () => {
    if (!chatMessage.trim()) return;
    if (!token) return setShowAuthModal(true);

    const newHistory = [...chatHistory, { role: 'user', text: chatMessage }];
    setChatHistory(newHistory); const currentMsg = chatMessage; setChatMessage(""); 

    try {
      const response = await fetch('http://127.0.0.1:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ message: currentMsg, session_id: "web_browser_tab" })
      });
      if (response.status === 401) { handleLogout(); alert("Session expired."); return setShowAuthModal(true); }
      const data = await response.json();
      setChatHistory([...newHistory, { role: 'bot', text: data.reply }]);
    } catch (error) { setChatHistory([...newHistory, { role: 'bot', text: 'Network error!' }]); }
  }

  const handleBookLinkClick = async (e, href) => {
    if (href && href.startsWith('#book:')) {
      e.preventDefault(); 
      e.stopPropagation(); 
      
      const rawTitle = href.replace('#book:', '');
      const bookTitle = decodeURIComponent(rawTitle).replace(/_/g, ' ').trim();
      
      setIsChatOpen(false); 
      
      try {
        const response = await fetch('http://127.0.0.1:8000/api/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: bookTitle, mode: "name", limit: 1 })
        });
        const data = await response.json();
        
        if (data.data && data.data.length > 0) {
          setSelectedBook(data.data[0]);
        }
      } catch (err) {
        console.error("Error loading book from chat:", err);
      }
    }
  };

  const booksPerPage = 4;
  const totalPages = Math.ceil(searchResults.length / booksPerPage);
  const paginatedResults = searchResults.slice(currentPage * booksPerPage, (currentPage + 1) * booksPerPage);
  const displayedBooks = randomBooks.slice(0, 4);

  const displayedRelated = relatedBooks.slice(carouselIndex, carouselIndex + 4);
  const currentCarouselPage = Math.floor(carouselIndex / 4) + 1;
  const totalCarouselPages = Math.ceil(relatedBooks.length / 4) || 1;

  return (
    <div style={styles.container}>
      <style>
        {`
          @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
          
          @keyframes heartbeat { 0% { transform: scale(1); } 14% { transform: scale(1.15); } 28% { transform: scale(1); } 42% { transform: scale(1.15); } 70% { transform: scale(1); } }
          
          ::-webkit-scrollbar { width: 6px; height: 6px; }
          ::-webkit-scrollbar-track { background: #f4f9fd; }
          ::-webkit-scrollbar-thumb { background: #cce0f5; border-radius: 10px; }
          ::-webkit-scrollbar-thumb:hover { background: #99c2ff; }
          
          .interactive-btn { transition: all 0.3s ease; cursor: pointer; }
          .interactive-btn:not(:disabled):hover { background-color: #0d5dd6 !important; transform: translateY(-2px); box-shadow: 0 6px 15px rgba(29, 112, 245, 0.25); }
          .interactive-btn:not(:disabled):active { transform: translateY(0); }
          
          .text-btn { transition: all 0.2s ease; cursor: pointer; color: #1d70f5 !important; }
          .text-btn:hover { color: #0d5dd6 !important; letter-spacing: 2px !important; }
          
          .logo-hover { transition: all 0.3s ease; cursor: pointer; }
          .logo-hover:hover { opacity: 0.8; letter-spacing: 5px !important; text-shadow: 0 0 10px rgba(29, 112, 245, 0.3); }

          .hover-check-label { display: flex; alignItems: center; font-size: 13px; margin-bottom: 10px; cursor: pointer; gap: 10px; transition: color 0.2s; color: #4a698a; }
          .hover-check-label:hover { color: #0c2b4b; font-weight: 600; }

          .book-card { transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1); cursor: pointer; background: #fff; padding: 20px; border-radius: 12px; border: 1px solid #eaf2fa; }
          .book-card:hover { transform: translateY(-8px); box-shadow: 0 15px 35px rgba(29, 112, 245, 0.1); border-color: #cce0f5; }
          
          .carousel-card { width: 22%; text-align: center; cursor: pointer; transition: all 0.3s ease; }
          .carousel-card:hover { transform: translateY(-8px) scale(1.02); }
          
          .accordion-btn { 
            width: 100%; text-align: left; background: #fff; border: 1px solid #cce0f5; 
            padding: 12px 15px; font-size: 12px; font-weight: 800; color: #0c2b4b; 
            letter-spacing: 1px; cursor: pointer; display: flex; justify-content: space-between; 
            align-items: center; border-radius: 8px; margin-bottom: 5px; transition: all 0.2s; 
            box-shadow: 0 2px 5px rgba(29, 112, 245, 0.05);
          }
          .accordion-btn:hover { border-color: #1d70f5; color: #1d70f5; }

          .bot-btn { position: fixed; bottom: 40px; right: 40px; width: 60px; height: 60px; border-radius: 50%; background: linear-gradient(135deg, #1d70f5, #0044cc); color: white; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; box-shadow: 0 8px 25px rgba(29, 112, 245, 0.4); animation: heartbeat 2s infinite; transition: all 0.3s ease; z-index: 1000; }
          .bot-btn:hover { transform: scale(1.1); animation: none; box-shadow: 0 12px 30px rgba(29, 112, 245, 0.6); }

          /* 🌟 ĐÃ SỬA: Hiệu ứng hover dành riêng cho các nút Tắt (X) */
          .icon-close-btn { transition: all 0.2s ease; cursor: pointer; }
          .icon-close-btn:hover { transform: scale(1.25); color: #ff4757 !important; text-shadow: 0 0 8px rgba(255, 71, 87, 0.4); }

          .circle-tl { position: absolute; top: -50px; left: -50px; width: 200px; height: 200px; background: radial-gradient(circle, rgba(29,112,245,0.05) 0%, rgba(255,255,255,0) 70%); border-radius: 50%; pointer-events: none; z-index: 0; }
          .circle-br { position: absolute; bottom: -50px; right: -50px; width: 300px; height: 300px; background: radial-gradient(circle, rgba(29,112,245,0.08) 0%, rgba(255,255,255,0) 70%); border-radius: 50%; pointer-events: none; z-index: 0; }
        `}
      </style>

      {showAuthModal && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalContent}>
            <div style={{display:'flex', justifyContent:'space-between', marginBottom:'25px', alignItems: 'center'}}>
              <h3 style={{margin:0, letterSpacing: '1px', color: '#0c2b4b', fontSize: '20px', fontWeight: '800'}}>{authMode === 'login' ? 'WELCOME BACK' : 'JOIN US'}</h3>
              {/* 🌟 ĐÃ SỬA: Thêm className icon-close-btn vào nút tắt modal */}
              <button onClick={() => setShowAuthModal(false)} className="icon-close-btn" style={{background:'none', border:'none', fontSize: '18px', fontWeight:'bold', color: '#888'}}>✕</button>
            </div>
            {authError && <p style={{color:'#e74c3c', fontSize:'13px', marginTop:0, fontWeight: '600'}}>{authError}</p>}
            <form onSubmit={handleAuthSubmit}>
              <input style={styles.authInput} type="text" placeholder="Username" value={authData.username} onChange={e => setAuthData({...authData, username: e.target.value})} required />
              {authMode === 'register' && <input style={styles.authInput} type="email" placeholder="Email" value={authData.email} onChange={e => setAuthData({...authData, email: e.target.value})} required />}
              <input style={styles.authInput} type="password" placeholder="Password" value={authData.password} onChange={e => setAuthData({...authData, password: e.target.value})} required />
              
              <button type="submit" className="interactive-btn" style={styles.authSubmitBtn}>
                {authMode === 'login' ? 'LOGIN TO ACCOUNT' : 'CREATE ACCOUNT'}
              </button>
              
              <div style={{marginTop: '20px', textAlign: 'center', fontSize: '13px', color: '#666'}}>
                {authMode === 'login' ? (
                  <span>New to library? <span onClick={() => setAuthMode('register')} style={{fontWeight: '700', color: '#1d70f5', cursor: 'pointer'}}>Sign up here</span></span>
                ) : (
                  <span>Already have an account? <span onClick={() => setAuthMode('login')} style={{fontWeight: '700', color: '#1d70f5', cursor: 'pointer'}}>Log in</span></span>
                )}
              </div>
            </form>
          </div>
        </div>
      )}

      {/* LEFT SIDEBAR */}
      <aside style={styles.sidebar}>
        <div className="logo-hover" style={styles.logo} onClick={() => { setSelectedBook(null); setSearchResults([]); }}>SMART<br/>LIBRARY</div>

        <div style={styles.userPanel}>
          {currentUser ? (
            <div style={{textAlign: 'center'}}>
              <div style={{fontSize: '11px', color: '#4a698a', fontWeight: '600', letterSpacing: '1px', marginBottom: '6px'}}>LOGGED IN AS</div>
              <div style={{fontWeight: '800', fontSize: '16px', color: '#1d70f5', marginBottom: '15px'}}>{currentUser.toUpperCase()}</div>
              <button onClick={handleLogout} className="interactive-btn" style={styles.logoutBtn}>LOGOUT</button>
            </div>
          ) : (
            <button onClick={() => setShowAuthModal(true)} className="interactive-btn" style={styles.loginBtn}>LOGIN TO ACCESS CHAT</button>
          )}
        </div>
        
        <div style={styles.controlGroup}>
          {/* 🌟 ĐÃ SỬA: Căn giữa, phóng to, đổi màu xanh cho chữ SMART SEARCH ENGINE */}
          <label style={{...styles.label, textAlign: 'center', fontSize: '15px', color: '#1d70f5', letterSpacing: '2px', marginBottom: '15px'}}>SMART SEARCH ENGINE</label>
          <textarea 
            value={query} 
            onChange={(e) => setQuery(e.target.value)} 
            placeholder="Search books, authors, or abstract ideas..." 
            style={styles.textarea} 
          />
        </div>

        {availableFilters.categories && availableFilters.categories.length > 0 && (
          <div style={styles.controlGroup}>
            <button className="accordion-btn" onClick={() => setIsCatExpanded(!isCatExpanded)}>
              <span>CATEGORIES ({selectedCategories.length})</span>
              <span style={{fontSize: '10px'}}>{isCatExpanded ? '▲' : '▼'}</span>
            </button>
            {isCatExpanded && (
              <div style={styles.filterWrapper}>
                <input 
                  type="text" 
                  placeholder="Find category..." 
                  value={catSearchTerm}
                  onChange={(e) => setCatSearchTerm(e.target.value)}
                  style={styles.filterSearchInput}
                />
                <div style={styles.filterBox} className="filter-scroll">
                  {availableFilters.categories
                    .filter(cat => cat.toLowerCase().includes(catSearchTerm.toLowerCase()))
                    .map(cat => (
                    <label key={cat} className="hover-check-label">
                      <input type="checkbox" style={{accentColor: '#1d70f5'}} checked={selectedCategories.includes(cat)} onChange={() => toggleCategory(cat)} /> {cat}
                    </label>
                  ))}
                  {availableFilters.categories.filter(cat => cat.toLowerCase().includes(catSearchTerm.toLowerCase())).length === 0 && (
                    <div style={{fontSize: '12px', color: '#888', textAlign: 'center', marginTop: '10px'}}>No categories found</div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {availableFilters.authors && availableFilters.authors.length > 0 && (
          <div style={styles.controlGroup}>
            <button className="accordion-btn" onClick={() => setIsAuthExpanded(!isAuthExpanded)}>
              <span>AUTHORS ({selectedAuthors.length})</span>
              <span style={{fontSize: '10px'}}>{isAuthExpanded ? '▲' : '▼'}</span>
            </button>
            {isAuthExpanded && (
              <div style={styles.filterWrapper}>
                <input 
                  type="text" 
                  placeholder="Find author..." 
                  value={authSearchTerm}
                  onChange={(e) => setAuthSearchTerm(e.target.value)}
                  style={styles.filterSearchInput}
                />
                <div style={styles.filterBox} className="filter-scroll">
                  {availableFilters.authors
                    .filter(author => author.toLowerCase().includes(authSearchTerm.toLowerCase()))
                    .map(author => (
                    <label key={author} className="hover-check-label">
                      <input type="checkbox" style={{accentColor: '#1d70f5'}} checked={selectedAuthors.includes(author)} onChange={() => toggleAuthor(author)} /> {author}
                    </label>
                  ))}
                  {availableFilters.authors.filter(author => author.toLowerCase().includes(authSearchTerm.toLowerCase())).length === 0 && (
                    <div style={{fontSize: '12px', color: '#888', textAlign: 'center', marginTop: '10px'}}>No authors found</div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {(selectedAuthors.length > 0 || selectedCategories.length > 0) && (
          <div style={{ textAlign: 'center', marginBottom: '15px' }}>
            <button onClick={handleClearFilters} className="text-btn" style={styles.clearFilterText}>
              CLEAR ALL FILTERS
            </button>
          </div>
        )}

        <button onClick={handleSearch} className="interactive-btn" style={styles.searchBtn}>
          {isSearching ? 'SEARCHING...' : 'DISCOVER NOW'}
        </button>
      </aside>

      <main style={styles.mainContent}>
        
        {selectedBook ? (
          <div style={styles.bookDetailPage}>
            <div style={{marginBottom: '25px'}}>
              <button onClick={() => setSelectedBook(null)} className="text-btn" style={styles.backButton}>← BACK TO BROWSE</button>
            </div>
            
            <div style={{display: 'flex', gap: '50px', flexWrap: 'wrap', borderBottom: '2px solid #eaf2fa', paddingBottom: '40px'}}>
              <img src={selectedBook.thumbnail || 'https://via.placeholder.com/200x300'} alt="cover" style={styles.detailImgFull} />
              <div style={{flex: 1, minWidth: '300px'}}>
                <h1 style={{marginTop: 0, fontSize: '38px', fontWeight: '800', color: '#0c2b4b', letterSpacing: '-0.5px', marginBottom: '15px', lineHeight: '1.2'}}>{selectedBook.title}</h1>
                <p style={{fontSize: '20px', color: '#1d70f5', fontWeight: '600', marginBottom: '25px'}}>{selectedBook.authors}</p>
                <div style={{display: 'flex', gap: '12px', marginBottom: '35px'}}>
                  <span style={styles.badge}>⭐ {selectedBook.average_rating || "N/A"}</span>
                  <span style={styles.badge}>🏷️ {selectedBook.categories || "General"}</span>
                </div>
                <h3 style={{fontSize: '15px', fontWeight: '700', letterSpacing: '1px', color: '#0c2b4b', textTransform: 'uppercase', marginBottom: '15px'}}>Synopsis</h3>
                <p style={{fontSize: '16px', lineHeight: '1.8', color: '#4a698a', textAlign: 'justify'}}>
                  {selectedBook.description || selectedBook.short_summary || "No full summary or description is currently available for this title."}
                </p>
              </div>
            </div>

            <div style={{marginTop: '40px'}}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '25px'}}>
                <h3 style={{fontSize: '16px', fontWeight: '800', color: '#0c2b4b', textTransform: 'uppercase', margin: 0}}>Readers Also Explored</h3>
                
                {relatedBooks.length > 4 && (
                  <div style={{display: 'flex', gap: '15px', alignItems: 'center'}}>
                    <button disabled={carouselIndex === 0} onClick={() => setCarouselIndex(p => Math.max(0, p - 4))} className="interactive-btn" style={{...styles.carouselArrow, opacity: carouselIndex === 0 ? 0.3 : 1}}>←</button>
                    <span style={{fontSize: '12px', fontWeight: '700', color: '#4a698a'}}>PAGE {currentCarouselPage} OF {totalCarouselPages}</span>
                    <button disabled={carouselIndex + 4 >= relatedBooks.length} onClick={() => setCarouselIndex(p => p + 4)} className="interactive-btn" style={{...styles.carouselArrow, opacity: carouselIndex + 4 >= relatedBooks.length ? 0.3 : 1}}>→</button>
                  </div>
                )}
              </div>

              {relatedBooks.length === 0 ? (
                <p style={{fontSize: '14px', color: '#888', fontStyle: 'italic', padding: '20px 0'}}>Analyzing intelligence database for connections...</p>
              ) : (
                <div style={styles.carouselTrack}>
                  {displayedRelated.map((book, idx) => (
                    <div key={idx} className="carousel-card" onClick={() => setSelectedBook(book)}>
                      <img src={book.thumbnail || 'https://via.placeholder.com/150'} alt="cover" style={styles.carouselImg} />
                      <div style={styles.carouselTitle} title={book.title}>{book.title}</div>
                      <div style={styles.carouselAuthor}>{book.authors?.split(';')[0]}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : searchResults.length === 0 ? (
          
          <div style={styles.discoverySection}>
            <div className="circle-tl"></div>
            <div className="circle-br"></div>
            
            <div style={{ position: 'relative', zIndex: 1 }}>
              <h2 style={styles.sectionTitle}>Curated For You</h2>
              <div style={{...styles.grid, gridTemplateColumns: 'repeat(2, 1fr)'}}>
                {displayedBooks.map((book, idx) => (
                  <div key={idx} style={styles.gridCard} className="book-card" onClick={() => setSelectedBook(book)}>
                    <img src={book.thumbnail || 'https://via.placeholder.com/150'} alt="cover" style={styles.gridImg} />
                    <div style={styles.cardInfo}>
                      <div style={styles.bookTitleSmall}>{book.title}</div>
                      <div style={styles.bookAuthorSmall}>{book.authors}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div style={styles.resultsList}>
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', borderBottom: '2px solid #eaf2fa', paddingBottom: '20px', marginBottom: '40px'}}>
                <h2 style={{...styles.sectionTitle, marginBottom: 0}}>Results ({searchResults.length})</h2>
                <button onClick={() => setSearchResults([])} className="interactive-btn" style={styles.closeBtn}>CLEAR SEARCH</button>
            </div>
            
            <div style={{...styles.grid, gridTemplateColumns: 'repeat(2, 1fr)'}}>
              {paginatedResults.map((book, idx) => (
                <div key={idx} style={styles.gridCard} className="book-card" onClick={() => setSelectedBook(book)}>
                  <img src={book.thumbnail || 'https://via.placeholder.com/150'} alt="cover" style={styles.gridImg} />
                  <div style={styles.cardInfo}>
                    <div style={styles.bookTitleSmall}>{book.title}</div>
                    <div style={styles.bookAuthorSmall}>{book.authors}</div>
                  </div>
                </div>
              ))}
            </div>

            {totalPages > 1 && (
              <div style={styles.paginationBox}>
                <button disabled={currentPage === 0} onClick={() => setCurrentPage(p => p - 1)} className="interactive-btn" style={{...styles.pageBtn, opacity: currentPage === 0 ? 0.3 : 1}}>
                  ← PREV
                </button>
                <span style={styles.pageText}>PAGE {currentPage + 1} OF {totalPages}</span>
                <button disabled={currentPage >= totalPages - 1} onClick={() => setCurrentPage(p => p + 1)} className="interactive-btn" style={{...styles.pageBtn, opacity: currentPage >= totalPages - 1 ? 0.3 : 1}}>
                  NEXT →
                </button>
              </div>
            )}
          </div>
        )}
      </main>

      {/* CHATBOT ICON & CONSOLE */}
      <button onClick={() => token ? setIsChatOpen(!isChatOpen) : setShowAuthModal(true)} className="bot-btn">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"></path></svg>
      </button>

      {isChatOpen && (
        <div style={styles.chatBox}>
          <div style={styles.chatHeader}>
            <div style={{display: 'flex', alignItems: 'center', gap: '8px'}}>
              <span style={{width: '8px', height: '8px', backgroundColor: '#4ade80', borderRadius: '50%', display: 'inline-block'}}></span>
              AI-GOLDFISH
            </div>
            {/* 🌟 ĐÃ SỬA: Thêm className icon-close-btn vào nút tắt chat */}
            <button onClick={() => setIsChatOpen(false)} className="icon-close-btn" style={{background:'none', border:'none', color:'white', fontSize: '18px', fontWeight: 'bold'}}>×</button>
          </div>
          
          <div style={styles.chatBody}>
            {chatHistory.map((msg, idx) => (
              <div key={idx} style={{ textAlign: msg.role === 'user' ? 'right' : 'left', marginBottom: '18px' }}>
                <div style={{ 
                    display: 'inline-block', 
                    padding: '14px 18px', 
                    borderRadius: msg.role === 'user' ? '18px 18px 0px 18px' : '18px 18px 18px 0px', 
                    backgroundColor: msg.role === 'user' ? '#1d70f5' : '#eaf2fa', 
                    color: msg.role === 'user' ? 'white' : '#0c2b4b', 
                    maxWidth: '85%', 
                    fontSize: '14px', 
                    textAlign: 'left',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.04)',
                    lineHeight: '1.6'
                  }}>
                  {msg.role === 'user' ? msg.text : (
                    <ReactMarkdown 
                      components={{ 
                        p: ({node, ...props}) => <p style={{margin: '0 0 10px 0'}} {...props} />,
                        img: ({node, ...props}) => (
                          <img 
                            {...props} 
                            style={{ maxWidth: '100px', borderRadius: '6px', boxShadow: '0 6px 12px rgba(0,0,0,0.1)', display: 'block', margin: '12px 0', cursor: 'pointer' }} 
                            alt="book-cover"
                          />
                        ),
                        a: ({node, href, children, ...props}) => (
                          <a 
                            href={href} 
                            {...props} 
                            onClick={(e) => handleBookLinkClick(e, href)}
                            style={{
                              color: href?.startsWith('#book:') ? '#0c2b4b' : '#1d70f5', 
                              fontWeight: href?.startsWith('#book:') ? '800' : '600',
                              textDecoration: href?.startsWith('#book:') ? 'underline' : 'none',
                              cursor: 'pointer'
                            }}
                          >
                            {children}
                          </a>
                        )
                      }}
                    >
                      {msg.text}
                    </ReactMarkdown>
                  )}
                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>
          <div style={{ display: 'flex', borderTop: '1px solid #eaf2fa', backgroundColor: '#fff', padding: '10px' }}>
            <input style={styles.chatInput} placeholder="Ask anything about books..." value={chatMessage} onChange={e => setChatMessage(e.target.value)} onKeyDown={e => e.key === 'Enter' && handleSendMessage()} />
            <button onClick={handleSendMessage} className="interactive-btn" style={{ padding: '0 20px', background: '#1d70f5', color: 'white', border: 'none', fontWeight: 'bold', cursor: 'pointer', fontSize: '13px', borderRadius: '8px', letterSpacing: '1px' }}>SEND</button>
          </div>
        </div>
      )}
    </div>
  )
}

// ==========================================
// CSS STYLES 
// ==========================================
const styles = {
  container: { display: 'flex', height: '100vh', backgroundColor: '#f4f9fd', color: '#0c2b4b', overflow: 'hidden', fontFamily: '"Plus Jakarta Sans", system-ui, sans-serif', width: '100%', maxWidth: '1600px', margin: '0 auto', boxShadow: '0 0 40px rgba(0,0,0,0.05)' },
  
  sidebar: { width: '300px', padding: '30px 24px', backgroundColor: '#eaf2fa', borderRight: '1px solid #cce0f5', display: 'flex', flexDirection: 'column', zIndex: 10, overflowY: 'auto' },
  logo: { fontSize: '26px', fontWeight: '800', color: '#1d70f5', letterSpacing: '3px', marginBottom: '30px', textAlign: 'center', lineHeight: '1.2' },
  
  controlGroup: { marginBottom: '24px' },
  label: { fontSize: '11px', fontWeight: '700', color: '#4a698a', letterSpacing: '2px', marginBottom: '10px', display: 'block' },
  modeBtn: { flex: 1, padding: '10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px', fontWeight: '700' },
  textarea: { width: '100%', height: '70px', padding: '12px', border: '1px solid #cce0f5', borderRadius: '8px', backgroundColor: '#fff', fontSize: '14px', boxSizing: 'border-box', outline: 'none', resize: 'none', color: '#0c2b4b', fontFamily: 'inherit' },
  searchBtn: { padding: '15px', backgroundColor: '#1d70f5', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: '800', letterSpacing: '2px', borderRadius: '8px', marginTop: 'auto', marginBottom: '10px', width: '100%', fontSize: '13px' },
  clearFilterText: { background: 'none', border: 'none', fontSize: '11px', fontWeight: '700', color: '#4a698a', letterSpacing: '1px', padding: '5px 0', width: '100%', textAlign: 'center', marginTop: '10px' },
  
  filterWrapper: { border: '1px solid #cce0f5', backgroundColor: '#fff', marginTop: '8px', borderRadius: '8px', overflow: 'hidden', display: 'flex', flexDirection: 'column' },
  filterSearchInput: { width: '100%', padding: '10px 14px', border: 'none', borderBottom: '1px solid #eaf2fa', outline: 'none', fontSize: '12px', color: '#0c2b4b', backgroundColor: '#f9fbfc', fontFamily: 'inherit' },
  filterBox: { maxHeight: '160px', overflowY: 'auto', padding: '12px' },
  
  userPanel: { padding: '20px', border: '2px solid #cce0f5', borderRadius: '12px', marginBottom: '30px', backgroundColor: '#fff', boxShadow: '0 4px 15px rgba(29, 112, 245, 0.05)' },
  loginBtn: { width: '100%', padding: '12px', backgroundColor: '#1d70f5', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: '700', letterSpacing: '1px', fontSize: '12px' },
  logoutBtn: { width: '100%', padding: '10px', fontSize: '12px', backgroundColor: '#fff', color: '#e74c3c', border: '2px solid #ffe6e6', borderRadius: '6px', cursor: 'pointer', fontWeight: '700', letterSpacing: '1px', transition: 'all 0.2s' },
  
  // 🌟 ĐÃ SỬA: Giảm padding trên xuống 20px để đẩy toàn bộ nội dung lên cao
  mainContent: { flex: 1, padding: '20px 70px', overflowY: 'auto', display: 'flex', flexDirection: 'column' },
  // 🌟 ĐÃ SỬA: Bỏ padding 20px ở box discovery để sát lên trên
  discoverySection: { position: 'relative', padding: '0px 20px', flex: 1 },
  // 🌟 ĐÃ SỬA: Giảm margin-bottom của tiêu đề để sách hiện cao hơn
  sectionTitle: { fontSize: '28px', fontWeight: '800', color: '#0c2b4b', letterSpacing: '2px', marginBottom: '25px' },
  
  grid: { display: 'grid', gap: '50px 80px', flex: 1 },
  gridCard: { textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' },
  gridImg: { width: '190px', height: '285px', objectFit: 'cover', borderRadius: '8px', boxShadow: '0 12px 30px rgba(0,0,0,0.1)', margin: '0 auto' },
  bookTitleSmall: { fontSize: '16px', fontWeight: '800', color: '#0c2b4b', marginTop: '18px', maxWidth: '280px', lineHeight: '1.4' },
  bookAuthorSmall: { fontSize: '14px', color: '#4a698a', fontWeight: '600', marginTop: '6px' },
  
  paginationBox: { display: 'flex', justifyContent: 'center', alignItems: 'center', marginTop: '60px', gap: '25px', paddingTop: '30px', borderTop: '2px solid #eaf2fa' },
  pageBtn: { padding: '10px 20px', backgroundColor: '#fff', color: '#1d70f5', border: '2px solid #1d70f5', cursor: 'pointer', fontWeight: '800', fontSize: '13px', letterSpacing: '1px', borderRadius: '8px' },
  pageText: { fontSize: '13px', fontWeight: '800', letterSpacing: '2px', color: '#4a698a' },
  closeBtn: { background: '#fff', border: '2px solid #eaf2fa', color: '#4a698a', borderRadius: '6px', padding: '8px 18px', cursor: 'pointer', fontSize: '12px', letterSpacing: '1px', fontWeight: '800' },
  
  chatBox: { position: 'fixed', bottom: '110px', right: '40px', width: '380px', height: '70vh', maxHeight: '600px', display: 'flex', flexDirection: 'column', backgroundColor: '#fff', borderRadius: '16px', border: '1px solid #cce0f5', overflow: 'hidden', boxShadow: '0 25px 50px rgba(29, 112, 245, 0.15)', zIndex: 1000 },
  chatHeader: { padding: '16px 20px', background: 'linear-gradient(135deg, #1d70f5, #0056b3)', color: '#fff', fontSize: '14px', fontWeight: '800', letterSpacing: '1px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexShrink: 0 }, 
  chatBody: { padding: '20px', fontSize: '14px', flex: 1, overflowY: 'auto', backgroundColor: '#fff' },
  chatInput: { width: '100%', padding: '12px 15px', border: 'none', outline: 'none', fontSize: '14px', color: '#0c2b4b', fontFamily: 'inherit' },
  
  modalOverlay: { position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', backgroundColor: 'rgba(244, 249, 253, 0.85)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 9999, backdropFilter: 'blur(8px)' },
  modalContent: { backgroundColor: '#fff', padding: '45px', borderRadius: '16px', border: 'none', width: '340px', boxShadow: '0 20px 60px rgba(29, 112, 245, 0.15)' },
  authInput: { width: '100%', padding: '14px', marginBottom: '18px', border: '2px solid #eaf2fa', borderRadius: '8px', backgroundColor: '#f9fbfc', fontSize: '14px', boxSizing: 'border-box', outline: 'none', color: '#0c2b4b', fontFamily: 'inherit' },
  authSubmitBtn: { width: '100%', padding: '16px', backgroundColor: '#1d70f5', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: '800', marginTop: '10px', letterSpacing: '1px', fontSize: '14px' },
  
  bookDetailPage: { animation: 'fadeIn 0.4s ease', display: 'flex', flexDirection: 'column' },
  backButton: { background: 'none', border: 'none', cursor: 'pointer', fontSize: '13px', fontWeight: '800', letterSpacing: '1px', color: '#4a698a', padding: '10px 0' },
  detailImgFull: { width: '260px', height: '390px', objectFit: 'cover', borderRadius: '10px', boxShadow: '0 20px 40px rgba(29, 112, 245, 0.2)' },
  badge: { display: 'inline-block', padding: '6px 16px', backgroundColor: '#eaf2fa', color: '#1d70f5', borderRadius: '20px', fontSize: '13px', fontWeight: '800' },
  carouselTrack: { display: 'flex', justifyContent: 'space-between', padding: '20px 0', width: '100%' }, 
  carouselImg: { width: '100%', aspectRatio: '2/3', objectFit: 'cover', borderRadius: '8px', boxShadow: '0 8px 20px rgba(0,0,0,0.08)' }, 
  carouselTitle: { fontSize: '14px', fontWeight: '800', color: '#0c2b4b', marginTop: '12px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', width: '100%' },
  carouselAuthor: { fontSize: '12px', color: '#4a698a', fontWeight: '600', marginTop: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', width: '100%' },
  carouselArrow: { width: '36px', height: '36px', backgroundColor: '#fff', color: '#1d70f5', border: '2px solid #eaf2fa', cursor: 'pointer', fontWeight: 'bold', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '8px' }
}

export default App