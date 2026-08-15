import React, { useState, useRef, useCallback, useEffect } from "react";
import { api, ChatResponse } from "../api";

interface Msg {
  role: string;
  content: string;
  rewritten?: string | null;
  metrics?: Record<string, any>;
}

type DisplayMode = "both" | "rewritten_only" | "original_only";

export function ClaudeView({ configured }: { configured: boolean }) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [autoRewrite, setAutoRewrite] = useState(false);
  const [displayMode, setDisplayMode] = useState<DisplayMode>("both");
  const [rewriteStrength, setRewriteStrength] = useState("natural");
  const [rewriteStyle, setRewriteStyle] = useState("natural");
  const endRef = useRef<HTMLDivElement>(null);
  const busyRef = useRef(false);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = useCallback(async () => {
    if (busyRef.current || !input.trim()) return;
    busyRef.current = true;
    setSending(true);

    const userMsg: Msg = { role: "user", content: input };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");

    try {
      const apiMessages = newMessages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const res = await api.chat({
        messages: apiMessages,
        auto_rewrite: autoRewrite,
        rewrite_strength: rewriteStrength,
        rewrite_style: rewriteStyle,
        display_mode: displayMode,
      });

      const assistantMsg: Msg = {
        role: "assistant",
        content: res.content,
        rewritten: res.rewritten_content,
        metrics: res.metrics,
      };
      setMessages([...newMessages, assistantMsg]);
    } catch (e: any) {
      const errMsg: Msg = {
        role: "assistant",
        content: `Error: ${e.message}`,
      };
      setMessages([...newMessages, errMsg]);
    } finally {
      busyRef.current = false;
      setSending(false);
    }
  }, [input, messages, autoRewrite, displayMode, rewriteStrength, rewriteStyle]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const displayText = (m: Msg) => {
    if (m.role !== "assistant") return m.content;
    if (displayMode === "rewritten_only" && m.rewritten) return m.rewritten;
    if (displayMode === "original_only") return m.content;
    return m.content; // "both" handled with tabs
  };

  return (
    <div className="view claude-view">
      <div className="view-header">
        <h1>Claude</h1>
        <div className="controls-row compact">
          <label className="preserve-toggle">
            <input
              type="checkbox"
              checked={autoRewrite}
              onChange={() => setAutoRewrite(!autoRewrite)}
            />
            <span>Auto-rewrite responses</span>
          </label>
          {autoRewrite && (
            <>
              <select
                className="select-sm"
                value={rewriteStrength}
                onChange={(e) => setRewriteStrength(e.target.value)}
              >
                <option value="light">Light</option>
                <option value="natural">Natural</option>
                <option value="strong">Strong</option>
              </select>
              <select
                className="select-sm"
                value={rewriteStyle}
                onChange={(e) => setRewriteStyle(e.target.value)}
              >
                <option value="natural">Natural</option>
                <option value="academic">Academic</option>
                <option value="professional">Professional</option>
                <option value="concise">Concise</option>
                <option value="creative">Creative</option>
              </select>
            </>
          )}
          <select
            className="select-sm"
            value={displayMode}
            onChange={(e) => setDisplayMode(e.target.value as DisplayMode)}
          >
            <option value="both">Show Both</option>
            <option value="rewritten_only">Rewritten Only</option>
            <option value="original_only">Original Only</option>
          </select>
        </div>
      </div>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="empty-state">
            {configured
              ? "Start a conversation with Claude"
              : "Configure your API key in Settings first"}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role}`}>
            <div className="chat-role">{m.role === "user" ? "You" : "Claude"}</div>
            <div className="chat-content">
              {m.role === "assistant" && displayMode === "both" && m.rewritten ? (
                <MessageWithBoth original={m.content} rewritten={m.rewritten} metrics={m.metrics} />
              ) : (
                <div className="chat-text">{displayText(m)}</div>
              )}
            </div>
          </div>
        ))}
        {sending && (
          <div className="chat-msg assistant">
            <div className="chat-role">Claude</div>
            <div className="chat-content">
              <div className="loading-state">
                <div className="spinner" />
                <span>Thinking…</span>
              </div>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="chat-input-bar">
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message… (Enter to send)"
          disabled={!configured || sending}
        />
        <button
          className="btn-primary"
          onClick={send}
          disabled={!configured || sending || !input.trim()}
        >
          Send
        </button>
      </div>
    </div>
  );
}

function MessageWithBoth({
  original,
  rewritten,
  metrics,
}: {
  original: string;
  rewritten: string;
  metrics?: Record<string, any>;
}) {
  const [tab, setTab] = useState<"rewritten" | "original">("rewritten");

  return (
    <div>
      <div className="msg-tabs">
        <button
          className={`msg-tab ${tab === "rewritten" ? "active" : ""}`}
          onClick={() => setTab("rewritten")}
        >
          Rewritten
        </button>
        <button
          className={`msg-tab ${tab === "original" ? "active" : ""}`}
          onClick={() => setTab("original")}
        >
          Original
        </button>
      </div>
      <div className="chat-text">
        {tab === "rewritten" ? rewritten : original}
      </div>
      {metrics && tab === "rewritten" && (
        <div className="metrics-row compact">
          {Object.entries(metrics)
            .filter(([k]) => ["semantic_similarity", "character_edit_ratio"].includes(k))
            .map(([k, v]) => (
              <span key={k} className="metric-inline">
                {k.replace(/_/g, " ")}:{" "}
                {typeof v === "number" ? v.toFixed(3) : String(v)}
              </span>
            ))}
        </div>
      )}
    </div>
  );
}
