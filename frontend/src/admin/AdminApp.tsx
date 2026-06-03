import { useCallback, useEffect, useState } from "react";
import { Link, Route, Routes } from "react-router-dom";
import {
  fetchAnalyticsSummary,
  fetchAudit,
  fetchCorpusImages,
  fetchDeleted,
  fetchDuplicateClusters,
  fetchOrphans,
  fetchSearchQuality,
  getAdminApiKey,
  restoreImage,
  setAdminApiKey,
  softDeleteImage,
  type AnalyticsSummary,
  type CorpusImage,
  type SearchQualityItem,
  type SearchQualityLists,
} from "../api/adminClient";

function queryTooltip(row: SearchQualityItem): string {
  const user = row.user_message ?? row.query_text ?? "";
  const semantic = row.parsed_semantic_query ?? "";
  const parts: string[] = [];
  if (user) parts.push(`User: ${user}`);
  if (semantic && semantic !== user) parts.push(`Interpreted: ${semantic}`);
  return parts.join("\n") || row.display_query;
}
function AdminKeyGate({ children }: { children: React.ReactNode }) {
  const [key, setKey] = useState(getAdminApiKey() ?? "");
  const [unlocked, setUnlocked] = useState(!!getAdminApiKey());

  if (unlocked) return <>{children}</>;

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 p-8">
      <h1 className="text-xl font-semibold text-slate-800">Admin access</h1>
      <p className="text-sm text-slate-600">
        Enter the server <code className="rounded bg-slate-100 px-1">ADMIN_API_KEY</code>.
      </p>
      <input
        type="password"
        value={key}
        onChange={(e) => setKey(e.target.value)}
        className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
        placeholder="Admin API key"
      />
      <button
        type="button"
        className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        onClick={() => {
          if (!key.trim()) return;
          setAdminApiKey(key.trim());
          setUnlocked(true);
        }}
      >
        Continue
      </button>
      <Link to="/" className="text-center text-sm text-brand-600 hover:underline">
        Back to chat
      </Link>
    </div>
  );
}

function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <AdminKeyGate>
      <div className="min-h-screen bg-slate-50">
        <header className="border-b border-slate-200 bg-white px-6 py-4">
          <div className="mx-auto flex max-w-6xl items-center justify-between">
            <h1 className="text-lg font-semibold text-slate-900">Imagecb Admin</h1>
            <nav className="flex gap-4 text-sm">
              <Link to="/admin" className="text-brand-600 hover:underline">
                Dashboard
              </Link>
              <Link to="/admin/quality" className="text-brand-600 hover:underline">
                Search quality
              </Link>
              <Link to="/admin/corpus" className="text-brand-600 hover:underline">
                Corpus
              </Link>
              <Link to="/admin/audit" className="text-brand-600 hover:underline">
                Audit log
              </Link>
              <Link to="/" className="text-slate-500 hover:underline">
                Chat
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl p-6">{children}</main>
      </div>
    </AdminKeyGate>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <p className="text-xs font-medium uppercase text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function DashboardPage() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalyticsSummary()
      .then(setSummary)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!summary) return <p className="text-slate-500">Loading…</p>;

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Dashboard (last 7 days)</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total searches" value={summary.total_searches} />
        <StatCard
          label="Zero-result rate"
          value={`${(summary.zero_result_rate * 100).toFixed(1)}%`}
        />
        <StatCard
          label="Weak-result rate"
          value={`${(summary.weak_result_rate * 100).toFixed(1)}%`}
        />
        <StatCard
          label="No-interaction rate"
          value={`${(summary.no_interaction_rate * 100).toFixed(1)}%`}
        />
        <StatCard label="Interactions" value={summary.interaction_count} />
        <StatCard
          label="Interaction rate"
          value={`${(summary.interaction_rate * 100).toFixed(1)}%`}
        />
      </div>
      <p className="text-xs text-slate-500">
        Weak threshold (raw score): {summary.weak_score_threshold}
      </p>
    </div>
  );
}

function QualityTable({ title, items }: { title: string; items: SearchQualityItem[] }) {
  return (
    <section className="space-y-2">
      <h3 className="font-medium text-slate-800">
        {title} ({items.length})
      </h3>
      <div className="overflow-x-auto rounded-lg bg-white ring-1 ring-slate-200">
        <table className="min-w-full text-left text-xs">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-3 py-2">Time</th>
              <th className="px-3 py-2">Query</th>
              <th className="px-3 py-2">Results</th>
              <th className="px-3 py-2">Top score</th>
            </tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <tr key={row.search_event_id} className="border-t border-slate-100">
                <td className="px-3 py-2 whitespace-nowrap">{row.created_at}</td>
                <td
                  className="max-w-md truncate px-3 py-2"
                  title={queryTooltip(row)}
                >
                  {row.display_query}
                </td>
                <td className="px-3 py-2">{row.result_count}</td>
                <td className="px-3 py-2">
                  {row.top_score != null
                    ? `${row.top_score.toFixed(3)} (${row.top_score_kind})`
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function QualityPage() {
  const [data, setData] = useState<SearchQualityLists | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSearchQuality()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return <p className="text-slate-500">Loading…</p>;

  return (
    <div className="space-y-8">
      <h2 className="text-lg font-semibold">Search quality</h2>
      <QualityTable title="Zero results" items={data.zero_result} />
      <QualityTable title="Weak results" items={data.weak_result} />
      <QualityTable title="No interaction" items={data.no_interaction} />
    </div>
  );
}

function CorpusPage() {
  const [images, setImages] = useState<CorpusImage[]>([]);
  const [corpusError, setCorpusError] = useState<string | null>(null);
  const [corpusLoading, setCorpusLoading] = useState(true);
  const [orphans, setOrphans] = useState<unknown[]>([]);
  const [orphansError, setOrphansError] = useState<string | null>(null);
  const [deleted, setDeleted] = useState<unknown[]>([]);
  const [deletedError, setDeletedError] = useState<string | null>(null);
  const [clusters, setClusters] = useState<unknown[]>([]);
  const [clustersError, setClustersError] = useState<string | null>(null);

  const loadCorpus = useCallback(() => {
    setCorpusLoading(true);
    setCorpusError(null);
    fetchCorpusImages()
      .then((r) => setImages(r.images))
      .catch((e) => setCorpusError(e instanceof Error ? e.message : String(e)))
      .finally(() => setCorpusLoading(false));
  }, []);

  const loadSecondary = useCallback(() => {
    fetchOrphans()
      .then((r) => {
        setOrphans(r.orphans);
        setOrphansError(null);
      })
      .catch((e) =>
        setOrphansError(e instanceof Error ? e.message : String(e)),
      );
    fetchDeleted()
      .then((r) => {
        setDeleted(r.deleted);
        setDeletedError(null);
      })
      .catch((e) =>
        setDeletedError(e instanceof Error ? e.message : String(e)),
      );
    fetchDuplicateClusters()
      .then((r) => {
        setClusters(r.clusters);
        setClustersError(r.error ?? null);
      })
      .catch((e) =>
        setClustersError(e instanceof Error ? e.message : String(e)),
      );
  }, []);

  const reloadAll = useCallback(() => {
    loadCorpus();
    loadSecondary();
  }, [loadCorpus, loadSecondary]);

  useEffect(() => {
    loadCorpus();
    loadSecondary();
  }, [loadCorpus, loadSecondary]);

  const handleSoftDelete = async (imageId: string) => {
    await softDeleteImage(imageId);
    reloadAll();
  };

  const handleRestore = async (imageId: string) => {
    await restoreImage(imageId);
    reloadAll();
  };

  return (
    <div className="space-y-8">
      <h2 className="text-lg font-semibold">Corpus curation</h2>

      <section>
        <h3 className="mb-2 font-medium">
          Indexed corpus ({corpusLoading ? "…" : images.length})
        </h3>
        {corpusError && (
          <p className="mb-2 text-sm text-red-600">{corpusError}</p>
        )}
        {corpusLoading ? (
          <p className="text-sm text-slate-500">Loading corpus…</p>
        ) : images.length === 0 ? (
          <p className="text-sm text-slate-500">No indexed images.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {images.map((img) => (
              <article
                key={img.image_id}
                className="flex flex-col overflow-hidden rounded-lg bg-white ring-1 ring-slate-200"
              >
                <div className="aspect-video bg-slate-100">
                  <img
                    src={img.image_url}
                    alt={img.caption_short || img.image_id}
                    className="h-full w-full object-contain"
                    loading="lazy"
                  />
                </div>
                <div className="flex flex-1 flex-col gap-1 p-2 text-xs">
                  <p className="line-clamp-2 text-slate-700">
                    {img.caption_short || "(no caption)"}
                  </p>
                  <p className="truncate text-slate-400" title={img.source_file}>
                    {img.source_file}
                  </p>
                  <button
                    type="button"
                    className="mt-auto self-start text-red-600 hover:underline"
                    onClick={() => void handleSoftDelete(img.image_id)}
                  >
                    Soft delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section>
        <h3 className="mb-2 font-medium">Orphan images (never served)</h3>
        {orphansError && (
          <p className="mb-2 text-sm text-amber-700">{orphansError}</p>
        )}
        <ul className="space-y-1 text-sm">
          {(orphans as { image_id: string; caption_short?: string }[]).map((o) => (
            <li key={o.image_id} className="flex items-center gap-2 rounded bg-white px-3 py-2 ring-1 ring-slate-200">
              <span className="font-mono text-xs">{o.image_id.slice(0, 8)}…</span>
              <span className="flex-1 truncate">{o.caption_short || "(no caption)"}</span>
              <button
                type="button"
                className="text-xs text-red-600 hover:underline"
                onClick={() => void handleSoftDelete(o.image_id)}
              >
                Soft delete
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3 className="mb-2 font-medium">Soft-deleted (recoverable)</h3>
        {deletedError && (
          <p className="mb-2 text-sm text-amber-700">{deletedError}</p>
        )}
        <ul className="space-y-1 text-sm">
          {(deleted as { image_id: string; deleted_at?: string }[]).map((d) => (
            <li key={d.image_id} className="flex items-center gap-2 rounded bg-white px-3 py-2 ring-1 ring-slate-200">
              <span className="font-mono text-xs">{d.image_id.slice(0, 8)}…</span>
              <span className="text-slate-500">{d.deleted_at}</span>
              <button
                type="button"
                className="text-xs text-brand-600 hover:underline"
                onClick={() => void handleRestore(d.image_id)}
              >
                Restore
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h3 className="mb-2 font-medium">Near-duplicate clusters</h3>
        {clustersError && (
          <p className="mb-2 text-sm text-amber-700">{clustersError}</p>
        )}
        {(clusters as { cluster_id: string; size: number; max_similarity: number; images: { image_id: string; caption_short?: string }[] }[]).map(
          (cl) => (
            <details key={cl.cluster_id} className="mb-2 rounded bg-white p-3 ring-1 ring-slate-200">
              <summary className="cursor-pointer text-sm font-medium">
                Cluster ({cl.size} images, max sim {cl.max_similarity})
              </summary>
              <ul className="mt-2 space-y-1 text-xs text-slate-600">
                {cl.images.map((img) => (
                  <li key={img.image_id}>
                    {img.image_id.slice(0, 8)}… — {img.caption_short || "—"}
                  </li>
                ))}
              </ul>
            </details>
          ),
        )}
      </section>
    </div>
  );
}

function AuditPage() {
  const [entries, setEntries] = useState<unknown[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAudit()
      .then((r) => setEntries(r.entries))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold">Audit log</h2>
      <ul className="space-y-2 text-sm">
        {(entries as { created_at: string; actor: string; action: string; target_id: string }[]).map(
          (e) => (
            <li key={`${e.created_at}-${e.target_id}-${e.action}`} className="rounded bg-white px-3 py-2 ring-1 ring-slate-200">
              <span className="text-slate-500">{e.created_at}</span> — {e.actor} —{" "}
              <strong>{e.action}</strong> on {e.target_id}
            </li>
          ),
        )}
      </ul>
    </div>
  );
}

export default function AdminApp() {
  return (
    <AdminLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/quality" element={<QualityPage />} />
        <Route path="/corpus" element={<CorpusPage />} />
        <Route path="/audit" element={<AuditPage />} />
      </Routes>
    </AdminLayout>
  );
}
