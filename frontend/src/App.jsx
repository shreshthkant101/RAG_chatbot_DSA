import { useState } from "react"
import ChatPanel from "./components/ChatPanel"
import InputBar from "./components/InputBar"


import "./styling/globalstyles.css"

export default function App() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading]   = useState(false)

  const sendMessage = async (question) => {
    if (!question.trim() || loading) return

    const userMessage = { role: "user", text: question }
    const aiMessage   = { role: "ai", text: "", sources: [], complete: false }

    const historySnapshot = [...messages].slice(-10).filter(m =>
      m.role === "user" || (m.role === "ai" && m.complete === true)
    )

    setMessages(prev => [...prev, userMessage, aiMessage])
    setLoading(true)

    try {
      const response = await fetch("http://localhost:8000/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: question,
          history:  historySnapshot
        })
      })

      const reader  = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const text  = decoder.decode(value)
        const lines = text.split("\n").filter(l => l.startsWith("data: "))

        for (const line of lines) {
          const data = JSON.parse(line.slice(6))

          if (data.type === "sources") {
            setMessages(prev => {
              const updated = [...prev]
              updated[updated.length - 1].sources = data.chunks
              return updated
            })
          }

          if (data.type === "token") {
            setMessages(prev => {
              const updated = [...prev]
              updated[updated.length - 1].text += data.content
              return updated
            })
          }

          if (data.type === "done") {
            setMessages(prev => {
              const updated = [...prev]
              updated[updated.length - 1].complete = true
              return updated
            })
            setLoading(false)
          }

          if (data.type === "error") {
            setMessages(prev => {
              const updated = [...prev]
              updated[updated.length - 1].text = "Error: " + data.content
              return updated
            })
            setLoading(false)
          }
        }
      }
    } catch (err) {
      setLoading(false)
      console.error(err)
    }
  }

  return (
    <div className="app">
      <div className="header">
        <span className="logo">Jarvis</span>
        <span className="model-tag"> Trained on DSA · Shreshth Kant </span>
      </div>
      <ChatPanel messages={messages} loading={loading} />
      <InputBar onSend={sendMessage} loading={loading} />
    </div>
  )
}