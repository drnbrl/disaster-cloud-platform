import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getRequest } from "../api";
import { PriorityBadge } from "../components/PriorityBadge";

export function StatusPage() {
  const { requestId = "" } = useParams();
  const query = useQuery({
    queryKey: ["request", requestId],
    queryFn: () => getRequest(requestId),
    refetchInterval: state => state.state.data?.analysisStatus === "COMPLETED" ? false : 2500
  });
  return (
    <main className="page narrow">
      <Link to="/">← Yeni talep</Link>
      <header className="hero compact"><h1>Talep durumu</h1><code className="request-code">{requestId}</code></header>
      {query.isLoading && <section className="panel">Talep yükleniyor…</section>}
      {query.error && <section className="panel error-box">{query.error.message}</section>}
      {query.data && (
        <section className="panel details">
          <div><span>Analiz</span><strong>{query.data.analysisStatus}</strong></div>
          <div><span>Operasyon durumu</span><strong>{query.data.requestStatus}</strong></div>
          <div><span>Öncelik</span><PriorityBadge level={query.data.priorityLevel} /></div>
          <div><span>Puan</span><strong>{query.data.priorityScore ?? "Bekleniyor"}</strong></div>
          {query.data.summary && <article className="full-width"><h2>AI özeti</h2><p>{query.data.summary}</p></article>}
          {query.data.priorityReasons && <article className="full-width"><h2>Gerekçeler</h2><ul>{query.data.priorityReasons.map(reason => <li key={reason}>{reason}</li>)}</ul></article>}
        </section>
      )}
    </main>
  );
}
