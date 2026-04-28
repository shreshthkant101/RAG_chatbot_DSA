import { useEffect, useRef, useState } from "react"
import ReactMarkdown from "react-markdown"
import CopyButton from "./CopyButton"



export default function ChatPanel({ messages, loading }) {
  const bottomRef = useRef(null)
  const panelRef = useRef(null)

  const [introText, setIntroText] = useState("")
  const [scrollBtn, setscrollBtn] = useState("0")


 
  useEffect(() => {
  const panel = panelRef.current
  if (!panel) return

  panel.addEventListener("scroll", () => {
    const isScrolledUp = panel.scrollHeight - panel.scrollTop - panel.clientHeight > 300
    if(isScrolledUp) {
      setscrollBtn("1")
    }
    else {
      setscrollBtn("0")
    }
  })
  }, [])  
  
  

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  useEffect(() => {
    const text = "Hi, I'm Jarvis. Ask me anything about DSA, and I'll try my best to answer."
let index = 0

function type() {
  setIntroText(text.slice(0, index + 1))

  index++

  if (index < text.length) {
    const currentText = text.slice(0, index)

    // pause after "Hi, I'm Jarvis."
    if (currentText === "Hi, I'm Jarvis.") {
      setTimeout(type, 600) // 2 sec pause
    } else {
      setTimeout(type, 75)
    }
  }
}
 
      type()

  }, [])

  return (
    <div className="chat-panel"  ref={panelRef}>
      {messages.length === 0 && !loading && (
        <div className="empty-state">
          <span id="typewriter-intro">{introText}</span>
        </div>
      )}

      {messages.map((msg, i) => (
        <div key={i} className={`bubble-row ${msg.role}`}>

          {msg.role === "ai" && msg.sources?.length > 0 && (
            <div className="sources-row">
              {msg.sources.map((s, j) => (
                <span key={j} className="source-pill">
                  Page {s.page} · {Math.round(s.score * 100)}%
                </span>
              ))}
            </div>
          )}

          <div className="line"></div>
          <div className={`bubble ${msg.role}`}>
            {msg.role === "ai"
              ? msg.text
                ? <><ReactMarkdown>{msg.text}</ReactMarkdown></>
                : loading && i === messages.length - 1
                  ? <span className="typing">thinking...</span>
                  : null
              : <>{msg.text}</>
            }
            
          </div>
            <CopyButton msgs={msg}></CopyButton>
          <div className="down-arrow" style={{opacity:scrollBtn}} onClick={() => {bottomRef.current?.scrollIntoView({ behavior: "smooth" })}}>
            &#8595;
          </div>
        </div>
      ))}

      <div ref={bottomRef} />
    </div>
  )
}