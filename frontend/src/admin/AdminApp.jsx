/* Protected admin reporting (/admin). All data comes from the backend's admin API, which
   requires an admin session token; nothing about users is shown before login. */
import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Download, LogOut, RefreshCcw } from "lucide-react";
import { Button, Eyebrow } from "../components/Button";
import { OfficialLogo } from "../components/Logo";
import { api } from "../services/api";
import { getAdminToken, setAdminToken } from "../services/session";

function Login({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const { token } = await api("/admin/login", { method: "POST", body: { email, password }, auth: false });
      setAdminToken(token); onLogin();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  const field = "w-full rounded-xl border border-sage-light bg-white px-4 py-3 text-[15px] outline-none focus:border-jade focus:ring-2 focus:ring-jade/15";
  return (
    <div className="flex-1 w-full max-w-sm mx-auto px-4 py-16">
      <Eyebrow className="mb-3 text-center">Admin</Eyebrow>
      <h1 className="font-display text-3xl text-jade-deep mb-8 text-center">Skin analysis reports</h1>
      <form onSubmit={submit} className="flex flex-col gap-4 bg-white rounded-card border border-hairline shadow-soft p-6">
        <label className="flex flex-col gap-1.5"><span className="text-sm font-medium">Admin email</span>
          <input className={field} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required /></label>
        <label className="flex flex-col gap-1.5"><span className="text-sm font-medium">Password</span>
          <input className={field} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required /></label>
        {error && <p className="flex gap-2 rounded-xl bg-danger-soft border border-danger-line p-3 text-sm text-danger" role="alert"><AlertCircle size={16} className="shrink-0 mt-0.5" />{error}</p>}
        <Button type="submit" full loading={busy} disabled={!email || !password}>Log in</Button>
      </form>
    </div>
  );
}

const fmt = (v) => (v == null ? "—" : v);

function Metric({ label, value, note }) {
  return (
    <div className="rounded-card bg-white border border-hairline shadow-soft p-5">
      <p className="text-[11px] font-semibold uppercase tracking-widest text-ink-soft mb-2">{label}</p>
      <p className="font-display text-3xl text-jade-deep">{fmt(value)}</p>
      {note && <p className="mt-1 text-[11px] text-ink-soft/80">{note}</p>}
    </div>
  );
}

/* Google Sheets follow-up sync (admin only): on/off, setting problems, counts and the latest states by customer ID.
   Contact details aren't shown here; they are in the sheet itself. */
function SheetSync({ sheet }) {
  if (!sheet) return null;
  const counts = sheet.by_status || {};
  const state = !sheet.enabled ? "Off (rows are queued, not written)" : sheet.problems.length ? "On, but not configured" : "On";
  return (
    <section className="rounded-card bg-white border border-hairline shadow-soft p-6 mb-8">
      <h2 className="font-display text-2xl text-ink mb-1">Google Sheets sync</h2>
      <p className="text-xs text-ink-soft mb-4">Worksheet {sheet.worksheet} · {sheet.eligibility}</p>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
        <Metric label="Sync" value={state} />
        {["pending", "syncing", "synced", "failed"].map((k) => <Metric key={k} label={k} value={counts[k] || 0} />)}
      </div>
      {sheet.problems.length > 0 && (
        <ul className="mb-4 list-disc pl-5 text-[13px] text-danger">{sheet.problems.map((p) => <li key={p}>{p}</li>)}</ul>)}
      {Object.keys(sheet.failed_by_error || {}).length > 0 && (
        <p className="mb-4 text-[13px] text-ink">Failures by reason: {Object.entries(sheet.failed_by_error).map(([e, n]) => `${e} (${n})`).join(", ")}</p>)}
      {sheet.items.length === 0 ? <p className="text-sm text-ink-soft">No customers queued yet.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-[13px]">
            <thead><tr className="text-left text-[11px] uppercase tracking-widest text-ink-soft">
              {["Customer ID", "Status", "Written / wanted", "Attempts", "Last error", "Last written", "Next try"].map((h) => <th key={h} className="pb-2 pr-4 whitespace-nowrap">{h}</th>)}
            </tr></thead>
            <tbody>{sheet.items.map((r) => (
              <tr key={r.customer_id} className="border-t border-sage-light/60">
                <td className="py-2 pr-4 font-mono text-[11px]">{r.customer_id.slice(0, 8)}…</td><td className="py-2 pr-4">{r.status}</td>
                <td className="py-2 pr-4 tabular-nums">{r.version}</td><td className="py-2 pr-4 tabular-nums">{r.attempts}</td>
                <td className="py-2 pr-4">{fmt(r.last_error)}</td><td className="py-2 pr-4">{fmt(r.last_synced_at)}</td><td className="py-2 pr-4">{fmt(r.next_attempt_at)}</td>
              </tr>))}</tbody>
          </table>
        </div>)}
    </section>
  );
}

function Dashboard({ onLogout }) {
  const [data, setData] = useState(null);
  const [rows, setRows] = useState([]);
  const [sheet, setSheet] = useState(null);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const [s, a] = await Promise.all([api("/admin/summary", { auth: "admin" }), api("/admin/analyses?limit=1000", { auth: "admin" })]);
      setData(s); setRows(a.items);
      setSheet(await api("/admin/customer-sheet", { auth: "admin" }).catch(() => null)); // optional panel
    } catch (err) {
      if (err.status === 401 || err.status === 403) onLogout(); else setError(err.message);
    }
  }, [onLogout]);
  useEffect(() => { load(); }, [load]);

  const exportExcel = async () => {
    setExporting(true); setError("");
    try {
      const res = await api("/admin/report.xlsx", { auth: "admin", raw: true });
      const url = URL.createObjectURL(await res.blob());
      const a = Object.assign(document.createElement("a"), { href: url, download: `yuriwoori-skin-analysis-report-${new Date().toISOString().slice(0, 10)}.xlsx` });
      document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
    } catch (err) {
      if (err.status === 401 || err.status === 403) onLogout(); else setError(err.message);
    } finally { setExporting(false); }
  };

  const s = data?.summary;
  return (
    <div className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-8 py-8">
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
        <div>
          <Eyebrow className="mb-2">Admin dashboard</Eyebrow>
          <h1 className="font-display text-3xl sm:text-4xl text-jade-deep">Skin analysis reports</h1>
          {s && <p className="text-xs text-ink-soft mt-1">Generated {s.generated_at} · {s.timezone}</p>}
        </div>
        <div className="flex gap-3">
          <Button variant="secondary" iconLeft={RefreshCcw} icon={null} onClick={load}>Refresh</Button>
          <Button iconLeft={Download} icon={null} onClick={exportExcel} loading={exporting} disabled={!data}>Export Excel</Button>
        </div>
      </div>

      {error && <p className="mb-6 flex gap-2 rounded-xl bg-danger-soft border border-danger-line p-3 text-sm text-danger" role="alert"><AlertCircle size={16} className="shrink-0 mt-0.5" />{error}</p>}
      {!data && !error && <p className="text-sm text-ink-soft">Loading…</p>}

      {s && (
        <>
          <section className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <Metric label="Registered users" value={s.registered_users} />
            <Metric label="Completed analyses" value={s.completed_analyses} note={`${s.scans_started} scans started`} />
            <Metric label="Unique users analyzed" value={s.unique_users_analyzed} />
            <Metric label="Products recommended" value={s.products_recommended} note={`${s.analyses_with_recommendations} analyses with products`} />
            <Metric label="Recommendations viewed" value={s.analyses_recommendations_viewed} note="analyses" />
            <Metric label="Product clicks" value={s.product_clicks} note={`${s.unique_products_clicked} different products`} />
            <Metric label="Analyses with a click" value={s.analyses_with_product_click} />
            <Metric label="Confirmed purchases" value="Not available" note="No Shopify order integration" />
          </section>

          <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <div className="rounded-card bg-white border border-hairline shadow-soft p-6">
              <h2 className="font-display text-2xl text-ink mb-4">Conversion funnel</h2>
              <ol className="flex flex-col gap-3">
                {s.funnel.map((f) => (
                  <li key={f.stage} className="flex items-center justify-between gap-4 text-sm border-b border-sage-light/60 pb-2 last:border-0">
                    <span className="text-ink">{f.stage}</span>
                    <span className="font-semibold text-jade-deep tabular-nums">
                      {f.count == null ? "Not available" : f.count}
                      {f.pct_of_previous != null && <span className="ml-2 text-xs font-normal text-ink-soft">({f.pct_of_previous}%)</span>}
                    </span>
                  </li>
                ))}
              </ol>
              <p className="mt-4 text-[12px] leading-relaxed text-ink-soft">{s.purchase_tracking} A product click is not counted as a purchase.</p>
            </div>
            <div className="rounded-card bg-white border border-hairline shadow-soft p-6 overflow-x-auto">
              <h2 className="font-display text-2xl text-ink mb-4">Product engagement</h2>
              {data.product_engagement.length === 0 ? <p className="text-sm text-ink-soft">No recommendations yet.</p> : (
                <table className="w-full text-sm">
                  <thead><tr className="text-left text-[11px] uppercase tracking-widest text-ink-soft"><th className="pb-2 pr-3">Product</th><th className="pb-2 pr-3">Recommended</th><th className="pb-2">Clicks</th></tr></thead>
                  <tbody>{data.product_engagement.map((p) => (
                    <tr key={p.product} className="border-t border-sage-light/60">
                      <td className="py-2 pr-3">{p.product_url ? <a href={p.product_url} target="_blank" rel="noreferrer" className="text-jade hover:underline">{p.product}</a> : p.product}</td>
                      <td className="py-2 pr-3 tabular-nums">{p.times_recommended}</td><td className="py-2 tabular-nums">{p.clicks}</td>
                    </tr>))}</tbody>
                </table>)}
            </div>
          </section>

          <SheetSync sheet={sheet} />

          <section className="rounded-card bg-white border border-hairline shadow-soft p-6">
            <h2 className="font-display text-2xl text-ink mb-4">Analyses <span className="text-sm font-sans text-ink-soft">({rows.length})</span></h2>
            {rows.length === 0 ? <p className="text-sm text-ink-soft">No completed analyses by signed-up users yet.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1100px] text-[13px]">
                  <thead><tr className="text-left text-[11px] uppercase tracking-widest text-ink-soft">
                    {["Name", "Email", "Analysis ID", "Date", "Time", "IP address", "Skin type", "Detected concerns", "Recommended products", "Clicked", "Purchase status"].map((h) => <th key={h} className="pb-2 pr-4 whitespace-nowrap">{h}</th>)}
                  </tr></thead>
                  <tbody>{rows.map((r) => (
                    <tr key={r.analysis_id} className="border-t border-sage-light/60 align-top">
                      <td className="py-2 pr-4">{r.user_name}</td><td className="py-2 pr-4">{r.email}</td>
                      <td className="py-2 pr-4 font-mono text-[11px]">{r.analysis_id.slice(0, 8)}…</td>
                      <td className="py-2 pr-4 whitespace-nowrap">{r.date}</td><td className="py-2 pr-4">{r.time}</td><td className="py-2 pr-4">{fmt(r.ip_address)}</td>
                      <td className="py-2 pr-4 capitalize">{r.skin_type}</td>
                      <td className="py-2 pr-4">{r.detected_concerns.join(", ") || "None detected"}</td>
                      <td className="py-2 pr-4">{r.recommended_products.length ? `${r.recommended_products.length} products` : "None"}</td>
                      <td className="py-2 pr-4">{r.product_clicked ? r.clicked_products.join(", ") : "No"}</td>
                      <td className="py-2 pr-4 text-ink-soft">{r.purchase_status}</td>
                    </tr>))}</tbody>
                </table>
              </div>)}
          </section>
        </>
      )}
    </div>
  );
}

export default function AdminApp() {
  const [authed, setAuthed] = useState(!!getAdminToken());
  const logout = useCallback(() => { setAdminToken(null); setAuthed(false); }, []);
  return (
    <div className="min-h-dvh flex flex-col bg-cream">
      <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-md border-b border-sage-light">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
          <a href="/" aria-label="YuriWoori skin analysis"><OfficialLogo height={40} /></a>
          <span className="text-[11px] uppercase tracking-wider font-semibold text-ink-soft">Admin</span>
          {authed ? <button onClick={logout} className="flex items-center gap-1.5 text-xs font-semibold text-jade"><LogOut size={14} /> Log out</button> : <span className="w-16" />}
        </div>
      </header>
      {authed ? <Dashboard onLogout={logout} /> : <Login onLogin={() => setAuthed(true)} />}
    </div>
  );
}
