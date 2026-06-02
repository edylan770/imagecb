import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchStatus,
  fetchSuggestions,
  ingestFiles,
  sendChatStream,
} from "./api/client";
import {
  createConversation,
  lastTurn,
  loadStoredState,
  newTurnId,
  recentChatTitles,
  saveStoredState,
  titleFromMessage,
  turnsToMessages,
} from "./chat/storage";
import { ChatMessageList } from "./components/ChatMessageList";
import { ChatSidebar } from "./components/ChatSidebar";
import { Composer } from "./components/Composer";
import { CorpusDrawer } from "./components/CorpusDrawer";
import { EmptyState } from "./components/EmptyState";
import { Header } from "./components/Header";
import { ResultsGrid } from "./components/ResultsGrid";
import type {
  Conversation,
  ConversationTurn,
  ResultCard,
} from "./types";

function applyTurnToPanel(
  turn: ConversationTurn | null,
  setResults: (r: ResultCard[]) => void,
) {
  setResults(turn?.results ?? []);
}

export default function App() {
  const [indexedCount, setIndexedCount] = useState(0);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(
    null,
  );
  const [selectedTurnId, setSelectedTurnId] = useState<string | null>(null);
  const [results, setResults] = useState<ResultCard[]>([]);
  const [input, setInput] = useState("");
  const [topK, setTopK] = useState(10);
  const [minMatchPercent, setMinMatchPercent] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const [corpusOpen, setCorpusOpen] = useState(false);
  const [skipCaption, setSkipCaption] = useState(false);
  const [skipOcr, setSkipOcr] = useState(false);
  const [force, setForce] = useState(false);
  const [ingesting, setIngesting] = useState(false);
  const [ingestMessage, setIngestMessage] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);

  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const activeConversation = useMemo(
    () => conversations.find((c) => c.id === activeConversationId) ?? null,
    [conversations, activeConversationId],
  );

  const messages = useMemo(
    () => (activeConversation ? turnsToMessages(activeConversation.turns) : []),
    [activeConversation],
  );

  const persistSoon = useCallback(
    (nextConversations: Conversation[], nextActiveId: string | null) => {
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(() => {
        saveStoredState({
          conversations: nextConversations,
          activeConversationId: nextActiveId,
        });
      }, 300);
    },
    [],
  );

  const updateConversations = useCallback(
    (
      updater: (prev: Conversation[]) => Conversation[],
      activeId: string | null = activeConversationId,
    ) => {
      setConversations((prev) => {
        const next = updater(prev);
        persistSoon(next, activeId);
        return next;
      });
    },
    [activeConversationId, persistSoon],
  );

  useEffect(() => {
    const stored = loadStoredState();
    let list = stored.conversations;
    let activeId = stored.activeConversationId;

    if (list.length === 0) {
      const c = createConversation();
      list = [c];
      activeId = c.id;
    } else if (!activeId || !list.some((c) => c.id === activeId)) {
      activeId = list.sort((a, b) => b.updatedAt - a.updatedAt)[0]!.id;
    }

    setConversations(list);
    setActiveConversationId(activeId);
    const active = list.find((c) => c.id === activeId);
    const turn = active ? lastTurn(active.turns) : null;
    applyTurnToPanel(turn, setResults);
    if (turn) setSelectedTurnId(turn.id);
  }, []);

  const refreshStatus = useCallback(async () => {
    try {
      const s = await fetchStatus();
      setIndexedCount(s.indexed_count);
    } catch {
      /* backend may be down during dev */
    }
  }, []);

  useEffect(() => {
    refreshStatus();
  }, [refreshStatus]);

  useEffect(() => {
    if (messages.length > 0) {
      setSuggestions([]);
      setSuggestionsLoading(false);
      return;
    }

    const controller = new AbortController();
    const titles = recentChatTitles(conversations);

    setSuggestionsLoading(true);
    fetchSuggestions(titles)
      .then((res) => {
        if (controller.signal.aborted) return;
        setSuggestions(res.suggestions);
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setSuggestions([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setSuggestionsLoading(false);
        }
      });

    return () => controller.abort();
  }, [messages.length, indexedCount, conversations]);

  const selectConversation = useCallback(
    (id: string) => {
      setActiveConversationId(id);
      persistSoon(conversations, id);
      const c = conversations.find((x) => x.id === id);
      const turn = c ? lastTurn(c.turns) : null;
      setSelectedTurnId(turn?.id ?? null);
      applyTurnToPanel(turn, setResults);
      setError(null);
    },
    [conversations, persistSoon],
  );

  const handleNewChat = useCallback(() => {
    const c = createConversation();
    setConversations((prev) => {
      const next = [c, ...prev];
      persistSoon(next, c.id);
      return next;
    });
    setActiveConversationId(c.id);
    setSelectedTurnId(null);
    setResults([]);
    setError(null);
    setInput("");
  }, [persistSoon]);

  const handleDeleteChat = useCallback(
    (id: string) => {
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== id);
        let newActive = activeConversationId;
        if (activeConversationId === id) {
          if (next.length === 0) {
            const c = createConversation();
            next.push(c);
            newActive = c.id;
            setActiveConversationId(c.id);
            setSelectedTurnId(null);
            setResults([]);
          } else {
            newActive = next.sort((a, b) => b.updatedAt - a.updatedAt)[0]!.id;
            setActiveConversationId(newActive);
            const active = next.find((c) => c.id === newActive)!;
            const turn = lastTurn(active.turns);
            setSelectedTurnId(turn?.id ?? null);
            applyTurnToPanel(turn, setResults);
          }
        }
        persistSoon(next, newActive);
        return next;
      });
    },
    [activeConversationId, persistSoon],
  );

  const handleSelectTurn = useCallback(
    (turnId: string) => {
      if (!activeConversation) return;
      const turn = activeConversation.turns.find((t) => t.id === turnId);
      if (!turn) return;
      setSelectedTurnId(turnId);
      applyTurnToPanel(turn, setResults);
    },
    [activeConversation],
  );

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;

    let convId = activeConversationId;
    let conv = activeConversation;
    if (!conv || !convId) {
      const c = createConversation();
      conv = c;
      convId = c.id;
      setConversations((prev) => {
        const next = [c, ...prev];
        persistSoon(next, c.id);
        return next;
      });
      setActiveConversationId(c.id);
    }

    setError(null);
    setLoading(true);
    setInput("");

    const turnId = newTurnId();
    const sessionId = conv.sessionId;

    const pendingTurn: ConversationTurn = {
      id: turnId,
      userContent: text,
      assistantContent: "",
      results: [],
      parsedQuery: null,
    };
    updateConversations((prev) =>
      prev.map((c) => {
        if (c.id !== convId) return c;
        const title = c.turns.length === 0 ? titleFromMessage(text) : c.title;
        return {
          ...c,
          title,
          updatedAt: Date.now(),
          turns: [...c.turns, pendingTurn],
        };
      }),
    );
    setSelectedTurnId(turnId);

    let streamedContent = "";

    try {
      await sendChatStream(text, sessionId, topK, minMatchPercent, {
        onMetadata: (meta) => {
          updateConversations((prev) =>
            prev.map((c) => {
              if (c.id !== convId) return c;
              return {
                ...c,
                sessionId: meta.session_id,
                updatedAt: Date.now(),
                turns: c.turns.map((t) =>
                  t.id === turnId
                    ? {
                        ...t,
                        results: meta.results,
                        parsedQuery: meta.parsed_query ?? null,
                      }
                    : t,
                ),
              };
            }),
          );
          setResults(meta.results);
        },
        onToken: (chunk) => {
          streamedContent += chunk;
          const content = streamedContent;
          updateConversations((prev) =>
            prev.map((c) => {
              if (c.id !== convId) return c;
              return {
                ...c,
                updatedAt: Date.now(),
                turns: c.turns.map((t) =>
                  t.id === turnId ? { ...t, assistantContent: content } : t,
                ),
              };
            }),
          );
        },
        onDone: (assistantMessage) => {
          updateConversations((prev) =>
            prev.map((c) => {
              if (c.id !== convId) return c;
              return {
                ...c,
                updatedAt: Date.now(),
                turns: c.turns.map((t) =>
                  t.id === turnId
                    ? { ...t, assistantContent: assistantMessage }
                    : t,
                ),
              };
            }),
          );
          setSelectedTurnId(turnId);
        },
        onError: (detail) => {
          throw new Error(detail);
        },
      });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      const errTurn: ConversationTurn = {
        id: turnId,
        userContent: text,
        assistantContent: `**Error:** ${msg}`,
        results: [],
        parsedQuery: null,
      };
      updateConversations((prev) =>
        prev.map((c) => {
          if (c.id !== convId) return c;
          return {
            ...c,
            updatedAt: Date.now(),
            turns: c.turns.map((t) => (t.id === turnId ? errTurn : t)),
          };
        }),
      );
      setSelectedTurnId(turnId);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleIngest = async (files: FileList | null) => {
    if (!files?.length) return;
    setIngesting(true);
    setIngestMessage(null);
    try {
      const res = await ingestFiles(Array.from(files), {
        skipCaption,
        skipOcr,
        force,
      });
      setIngestMessage(res.message);
      setIndexedCount(res.indexed_count);
    } catch (e) {
      setIngestMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setIngesting(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        indexedCount={indexedCount}
        onOpenCorpus={() => setCorpusOpen(true)}
      />

      {error && (
        <div className="mx-6 mt-2 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700 ring-1 ring-red-100">
          {error}
        </div>
      )}

      <main className="flex flex-1 flex-col lg:flex-row lg:items-stretch">
        <ChatSidebar
          conversations={conversations}
          activeId={activeConversationId}
          collapsed={sidebarCollapsed}
          onToggleCollapsed={() => setSidebarCollapsed((v) => !v)}
          onSelect={selectConversation}
          onNewChat={handleNewChat}
          onDelete={handleDeleteChat}
        />

        <section className="flex min-h-0 flex-1 flex-col border-b border-slate-200 lg:border-b-0 lg:border-r">
          <div className="flex shrink-0 items-center gap-2 border-b border-slate-100 bg-slate-50/80 px-4 py-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Conversation
            </span>
            {sidebarCollapsed && (
              <button
                type="button"
                onClick={() => setSidebarCollapsed(false)}
                className="text-xs text-brand-600 hover:underline"
              >
                Show chats
              </button>
            )}
          </div>
          <div className="max-h-[min(50vh,calc(100dvh-14rem))] flex-1 overflow-y-auto lg:max-h-none">
            {messages.length === 0 ? (
              <EmptyState
                suggestions={suggestions}
                loading={suggestionsLoading}
                onPickExample={setInput}
              />
            ) : (
              <ChatMessageList
                messages={messages}
                selectedTurnId={selectedTurnId}
                onSelectTurn={handleSelectTurn}
              />
            )}
          </div>
          <Composer
            value={input}
            topK={topK}
            minMatchPercent={minMatchPercent}
            loading={loading}
            onChange={setInput}
            onTopKChange={setTopK}
            onMinMatchPercentChange={setMinMatchPercent}
            onSend={handleSend}
          />
        </section>

        <section className="flex min-h-[50vh] flex-1 flex-col lg:sticky lg:top-0 lg:min-h-0 lg:h-[calc(100dvh-7rem)]">
          <div className="flex shrink-0 items-center gap-2 border-b border-slate-100 bg-slate-50/80 px-4 py-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Results
            </span>
            {results.length > 0 && (
              <span className="text-xs text-slate-400">
                {results.length} image{results.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
          <ResultsGrid results={results} />
        </section>
      </main>

      <footer className="border-t border-slate-200 bg-white px-6 py-2 text-xs text-slate-500">
        Indexed images: {indexedCount}. CLI:{" "}
        <code className="rounded bg-slate-100 px-1">
          python -m imagecb.cli ingest &lt;path&gt;
        </code>
      </footer>

      <CorpusDrawer
        open={corpusOpen}
        onClose={() => setCorpusOpen(false)}
        skipCaption={skipCaption}
        skipOcr={skipOcr}
        force={force}
        onSkipCaptionChange={setSkipCaption}
        onSkipOcrChange={setSkipOcr}
        onForceChange={setForce}
        onIngest={handleIngest}
        ingestMessage={ingestMessage}
        ingesting={ingesting}
      />
    </div>
  );
}
