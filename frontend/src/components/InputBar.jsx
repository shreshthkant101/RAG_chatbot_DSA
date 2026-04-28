import { useState, useRef, useEffect } from "react"

export default function InputBar({ onSend, loading }) {
  const [input, setInput] = useState("")
  const textareaRef = useRef(null)

  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  useEffect(() => {
    const handleKeyPress = (e) => {
      if (e.key === "Enter" || e.metaKey || e.ctrlKey || e.altKey) return
      textareaRef.current?.focus()
    }
    window.addEventListener("keydown", handleKeyPress)
    return () => window.removeEventListener("keydown", handleKeyPress)
  }, [])

  const handleSend = () => {
    if (!input.trim() || loading) return
    onSend(input.trim())
    setInput("")
    textareaRef.current?.focus()
  }

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="input-bar">
      <textarea
        ref={textareaRef}
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask me anything..."
        disabled={loading}
        rows={1}
      />
      <button onClick={handleSend} disabled={!input.trim() || loading}>
        {loading ? "..." : "Send"}
      </button>
    </div>
  )
}