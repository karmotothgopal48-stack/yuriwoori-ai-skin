"use client";

import { useState } from "react";
import { sendCoachMessage } from "@/lib/api";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export default function CoachPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || loading) return;

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setLoading(true);

    try {
      const res = await sendCoachMessage(question, conversationId);
      setConversationId(res.conversation_id);
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply }]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Sorry, I couldn't reach the coach right now." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F0ECE3] flex flex-col">
      <div className="px-5 py-4 border-b border-border-soft">
        <span className="text-sm tracking-widest uppercase text-brand-muted">Yuri AI</span>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[78%] px-3.5 py-2.5 rounded-2xl text-[13.5px] leading-relaxed ${
              m.role === "user"
                ? "self-end bg-[#22201C] text-[#F7F4EE] rounded-br-[4px]"
                : "self-start bg-[#E6ECE4] text-[#33473A] rounded-bl-[4px]"
            }`}
          >
            {m.content}
          </div>
        ))}
        {loading && <div className="self-start text-xs text-brand-muted">Yuri is thinking…</div>}
      </div>

      <div className="p-4 border-t border-border-soft flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Ask Yuri anything about your routine…"
          className="flex-1 border border-border-soft rounded-full px-4 py-2.5 text-sm bg-white outline-none"
        />
        <button
          onClick={handleSend}
          className="bg-brand-primary text-white px-5 py-2.5 rounded-full text-sm hover:bg-brand-primary-light transition"
        >
          Send
        </button>
      </div>
    </div>
  );
}