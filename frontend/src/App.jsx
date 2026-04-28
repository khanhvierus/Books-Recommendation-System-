import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'

function App() {
  // ==========================================
  // STATES QUẢN LÝ DỮ LIỆU
  // ==========================================
  const [randomBooks, setRandomBooks] = useState([])
  const [searchMode, setSearchMode] = useState("name")
  const [query, setQuery] = useState("")
  const [searchResults, setSearchResults] = useState([])
  const [isSearching, setIsSearching] = useState(false)
  
  // STATE CHO CHATBOT
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [chatMessage, setChatMessage] = useState("")
  const [chatHistory, setChatHistory] = useState([
    { role: 'bot', text: 'Tớ là AI-Cá Vàng đây! Cậu muốn hỏi gì nào?' }
  ])
  const chatEndRef = useRef(null)

  // Hàm tự động cuộn xuống tin nhắn cuối
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [chatHistory, isChatOpen])

  // 1. Tự động cập nhật 9 cuốn sách ngẫu nhiên mỗi 10 giây
  const fetchRandom = () => {
    fetch('http://127.0.0.1:8000/api/random')
      .then(res => res.json())
      .then(data => setRandomBooks(data.data))
  }

  useEffect(() => {
    fetchRandom()
    const interval = setInterval(fetchRandom, 10000)
    return () => clearInterval(interval)
  }, [])

  // 2. Xử lý tìm kiếm
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

  // 3. Xử lý Chatbot
  const handleSendMessage = async () => {
    if (!chatMessage.trim()) return;
    
    const newHistory = [...chatHistory, { role: 'user', text: chatMessage }];
    setChatHistory(newHistory);
    const currentMsg = chatMessage;
    setChatMessage(""); 

    try {
      const response = await fetch('http://127.0.0.1:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: currentMsg })
      });
      const data = await response.json();
      setChatHistory([...newHistory, { role: 'bot', text: data.reply }]);
    } catch (error) {
      setChatHistory([...newHistory, { role: 'bot', text: 'Lỗi mạng rồi cậu ơi!' }]);
    }
  }

  // ==========================================
  // RENDER GIAO DIỆN
  // ==========================================
  return (
    <div style={styles.container}>
      
      {/* NHÚNG CSS TRỰC TIẾP CHO ANIMATION & HOVER */}
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
            position: fixed;
            bottom: 40px;
            right: 40px;
            width: 55px;
            height: 55px;
            border-radius: 50%;
            background-color: #3b82f6;
            color: white;
            border: none;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
            animation: heartbeat 2s infinite;
            transition: all 0.3s ease;
            z-index: 1000;
          }
          .bot-btn:hover {
            background-color: #1d4ed8;
            transform: scale(1.1);
            box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
            animation: none;
          }
        `}
      </style>

      {/* SIDEBAR BÊN TRÁI: ĐIỀU KHIỂN */}
      <aside style={styles.sidebar}>
        <div style={styles.logo}>Smart Library</div>
        
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
            placeholder={searchMode === 'name' ? "Enter book title..." : "Describe the mood or story..."}
            style={styles.textarea}
          />
        </div>

        <button onClick={handleSearch} style={styles.searchBtn}>
          {isSearching ? 'PROCESSING...' : 'SEARCH'}
        </button>
      </aside>

      {/* MAIN CONTENT BÊN PHẢI: HIỂN THỊ SÁCH */}
      <main style={styles.mainContent}>
        {searchResults.length === 0 ? (
          /* MẶC ĐỊNH: 3 HÀNG x 3 CỘT */
          <div style={styles.discoveryGrid}>
            <h2 style={styles.sectionTitle}>CURATED DISCOVERY</h2>
            <div style={styles.grid}>
              {randomBooks.map((book, idx) => (
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
          /* KHI TÌM KIẾM: LIST DỌC 20 CUỐN */
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

      {/* MINI CHATBOT ICON (Robot có CSS Class) */}
      <button onClick={() => setIsChatOpen(!isChatOpen)} className="bot-btn">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="11" width="18" height="10" rx="2"></rect>
          <circle cx="12" cy="5" r="2"></circle>
          <path d="M12 7v4"></path>
          <line x1="8" y1="16" x2="8.01" y2="16"></line>
          <line x1="16" y1="16" x2="16.01" y2="16"></line>
        </svg>
      </button>

      {/* KHUNG CHATBOT */}
      {isChatOpen && (
        <div style={styles.chatBox}>
          <div style={styles.chatHeader}>🐟 AI-CÁ VÀNG</div>
          
          <div style={styles.chatBody}>
            {chatHistory.map((msg, idx) => (
              <div key={idx} style={{ textAlign: msg.role === 'user' ? 'right' : 'left', marginBottom: '15px' }}>
                <div style={{ 
                  display: 'inline-block', 
                  padding: '12px 16px', 
                  borderRadius: '16px', 
                  backgroundColor: msg.role === 'user' ? '#003366' : '#f1f1f1', 
                  color: msg.role === 'user' ? 'white' : 'black',
                  maxWidth: '90%', 
                  fontSize: '13px', 
                  lineHeight: '1.6',
                  boxShadow: '0 2px 5px rgba(0,0,0,0.05)',
                  textAlign: 'left'
                }}>
                  
                  {/* Text Nội dung */}
                  {msg.role === 'user' ? (
                    msg.text || ""
                  ) : (
                    <ReactMarkdown 
                      components={{
                        // ÉP REACT TỪ CHỐI VẼ ẢNH ĐỂ CHỐNG LỖI HIỂN THỊ
                        img: () => null,
                        
                        p: ({node, ...props}) => <p style={{margin: '0 0 8px 0', lineHeight: '1.5'}} {...props} />,
                        ul: ({node, ...props}) => <ul style={{margin: '0 0 10px 0', paddingLeft: '20px'}} {...props} />,
                        li: ({node, ...props}) => <li style={{marginBottom: '6px'}} {...props} />,
                        strong: ({node, ...props}) => <strong style={{color: '#10b981'}} {...props} /> 
                      }}
                    >
                      {/* Áo giáp chống sập web khi API trả lỗi */}
                      {msg.text || "Đang kết nối lại với não bộ cá vàng... 🐟"}
                    </ReactMarkdown>
                  )}

                </div>
              </div>
            ))}
            <div ref={chatEndRef} />
          </div>

          {/* Thanh nhập liệu */}
          <div style={{ display: 'flex', borderTop: '1px solid #eee' }}>
            <input 
              style={styles.chatInput} 
              placeholder="Nhắn với Cá Vàng..." 
              value={chatMessage}
              onChange={(e) => setChatMessage(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
            />
            <button 
              onClick={handleSendMessage} 
              style={{ padding: '0 15px', background: 'white', border: 'none', fontWeight: 'bold', cursor: 'pointer', borderTop: '1px solid #eee', color: '#10b981' }}
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
// STYLES OBJECT (Professional Minimalism)
// ==========================================
const styles = {
  container: { display: 'flex', height: '100vh', backgroundColor: '#faf9f6', color: '#1a1a1a', overflow: 'hidden' },
  sidebar: { width: '350px', padding: '50px 40px', borderRight: '1px solid #e0e0e0', display: 'flex', flexDirection: 'column', zIndex: 10 },
  logo: { fontSize: '18px', fontWeight: '800', letterSpacing: '4px', marginBottom: '60px' },
  controlGroup: { marginBottom: '35px' },
  label: { fontSize: '10px', fontWeight: 'bold', color: '#888', letterSpacing: '2px', marginBottom: '15px', display: 'block' },
  modeBtn: { width: '100%', padding: '12px', border: '1px solid #1a1a1a', marginBottom: '10px', cursor: 'pointer', fontSize: '12px', fontWeight: '600', transition: '0.3s' },
  textarea: { width: '100%', height: '120px', padding: '15px', border: '1px solid #e0e0e0', backgroundColor: '#fff', fontSize: '14px', boxSizing: 'border-box', outline: 'none' },
  searchBtn: { padding: '15px', backgroundColor: '#1a1a1a', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 'bold', letterSpacing: '2px' },
  
  mainContent: { flex: 1, padding: '60px 80px', overflowY: 'auto' },
  sectionTitle: { fontSize: '24px', fontWeight: '300', letterSpacing: '5px', marginBottom: '40px', textTransform: 'uppercase' },
  
  // Discovery Grid (3x3)
  grid: { display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '40px' },
  gridCard: { textAlign: 'center' },
  gridImg: { width: '100%', height: '220px', objectFit: 'cover', borderRadius: '2px', boxShadow: '0 10px 20px rgba(0,0,0,0.05)' },
  bookTitleSmall: { fontSize: '14px', fontWeight: '700', marginTop: '15px' },
  bookAuthorSmall: { fontSize: '12px', color: '#666', marginTop: '5px' },
  refreshNote: { marginTop: '40px', fontSize: '11px', fontStyle: 'italic', color: '#aaa' },

  // Search Results List
  listRow: { display: 'flex', gap: '30px', marginBottom: '50px', paddingBottom: '30px', borderBottom: '1px solid #f0f0f0' },
  listImg: { width: '120px', height: '180px', objectFit: 'cover' },
  bookTitleLarge: { fontSize: '20px', fontWeight: '700', margin: '0 0 5px 0' },
  bookAuthorLarge: { fontSize: '14px', color: '#888', marginBottom: '15px' },
  bookSummary: { fontSize: '14px', lineHeight: '1.6', color: '#444' },
  closeBtn: { background: 'none', border: '1px solid #ccc', padding: '5px 15px', cursor: 'pointer', fontSize: '11px' },

  // Chat Widget
  chatBox: { position: 'fixed', bottom: '110px', right: '40px', width: '320px', backgroundColor: '#fff', border: '1px solid #e0e0e0', borderRadius: '8px', overflow: 'hidden', boxShadow: '0 20px 40px rgba(0,0,0,0.15)', zIndex: 1000 },
  chatHeader: { padding: '15px', backgroundColor: '#003366', color: '#fff', fontSize: '12px', fontWeight: 'bold', letterSpacing: '1px' }, 
  chatBody: { padding: '15px', fontSize: '13px', height: '350px', overflowY: 'auto', backgroundColor: '#fff' },
  chatInput: { width: '100%', padding: '12px', border: 'none', outline: 'none' }
}

export default App