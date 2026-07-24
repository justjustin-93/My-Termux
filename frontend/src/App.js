import { useEffect, useState } from "react";
import "@/App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";
const API_BASE = `${BACKEND_URL.replace(/\/$/, "")}/api`;

const starterMessages = [
  {
    id: 1,
    role: "assistant",
    content:
      "Welcome back. I can help you scan projects, plan your next steps, sync git work, inspect media, or repair the workspace.",
  },
];

const quickActions = [
  {
    id: "scan",
    label: "Scan project",
    prompt: "Scan the current project and suggest the next best action.",
  },
  {
    id: "sync",
    label: "Sync git",
    prompt: "Check the git state and prepare a safe sync plan.",
  },
  {
    id: "media",
    label: "Open media vault",
    prompt: "Show me the most useful media vault actions right now.",
  },
  {
    id: "repair",
    label: "Run repair",
    prompt: "Run a self-heal check and explain any issues I should fix first.",
  },
];

function App() {
  const [messages, setMessages] = useState(starterMessages);
  const [input, setInput] = useState("");
  const [overview, setOverview] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);

  useEffect(() => {
    const loadOverview = async () => {
      try {
        const response = await axios.get(`${API_BASE}/overview`);
        setOverview(response.data);
      } catch (error) {
        console.error("Failed to load overview", error);
        setOverview({
          status: "offline",
          agent: "MyTermux",
          mode: "offline demo",
          metrics: { projects: 3, sessions: 12, tasks: 4, health: "ready" },
          highlights: ["Local-first workflows", "Safe repair mode", "Fast project planning"],
        });
      } finally {
        setIsLoading(false);
      }
    };

    loadOverview();
  }, []);

  const submitMessage = async (text) => {
    const trimmed = text.trim();
    if (!trimmed) {
      return;
    }

    const userMessage = {
      id: Date.now(),
      role: "user",
      content: trimmed,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsSending(true);

    try {
      const response = await axios.post(`${API_BASE}/chat`, { message: trimmed });
      const assistantMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content: response.data.reply,
        meta: response.data,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 2,
          role: "assistant",
          content:
            "The assistant is offline right now, but your request is queued. I can still help you review the workspace status.",
        },
      ]);
    } finally {
      setIsSending(false);
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    submitMessage(input);
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-badge">MT</div>
          <div>
            <h1>MyTermux</h1>
            <p>Phone-first AI workspace</p>
          </div>
        </div>

        <section className="panel-card">
          <div className="panel-title">Live status</div>
          <div className="status-pill">{isLoading ? "Booting" : overview?.status || "Ready"}</div>
          <div className="metrics-grid">
            <div>
              <strong>{overview?.metrics?.projects ?? 3}</strong>
              <span>Projects</span>
            </div>
            <div>
              <strong>{overview?.metrics?.sessions ?? 12}</strong>
              <span>Sessions</span>
            </div>
            <div>
              <strong>{overview?.metrics?.tasks ?? 4}</strong>
              <span>Tasks</span>
            </div>
            <div>
              <strong>{overview?.metrics?.health ?? "ready"}</strong>
              <span>Health</span>
            </div>
          </div>
        </section>

        <section className="panel-card">
          <div className="panel-title">Quick actions</div>
          <div className="actions-list">
            {quickActions.map((action) => (
              <button key={action.id} type="button" onClick={() => submitMessage(action.prompt)}>
                {action.label}
              </button>
            ))}
          </div>
        </section>

        <section className="panel-card">
          <div className="panel-title">Capabilities</div>
          <ul className="bullet-list">
            <li>Project scanning and planning</li>
            <li>Git sync and smart follow-ups</li>
            <li>Media vault organization</li>
            <li>Self-heal diagnostics</li>
          </ul>
        </section>
      </aside>

      <main className="main-panel">
        <header className="hero-card">
          <div>
            <p className="eyebrow">Agent command center</p>
            <h2>{overview?.agent || "MyTermux"} is ready to help</h2>
            <p>
              This workspace now feels like a real operating layer: status, context, fast actions, and a conversational assistant in one view.
            </p>
          </div>
          <div className="hero-badge">{overview?.mode || "Planning mode"}</div>
        </header>

        <section className="chat-card">
          <div className="panel-title">Conversation</div>
          <div className="message-list">
            {messages.map((message) => (
              <div key={message.id} className={`message-row ${message.role}`}>
                <span className="message-label">{message.role === "user" ? "You" : "Agent"}</span>
                <p>{message.content}</p>
              </div>
            ))}
          </div>

          <form className="composer" onSubmit={handleSubmit}>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask for a scan, a repair, a git sync, or a plan..."
            />
            <button type="submit" disabled={isSending}>
              {isSending ? "Thinking..." : "Send"}
            </button>
          </form>
        </section>
      </main>
    </div>
  );
}

export default App;
