import Link from "next/link";

export default function HomePage() {
  return (
    <div className="flex flex-col justify-center items-center flex-1 px-6 py-16 text-center max-w-3xl mx-auto">
      <div className="inline-flex items-center px-3 py-1 mb-6 text-xs font-semibold uppercase tracking-wider rounded-full bg-gradient-to-r from-red-500 to-amber-500 text-white shadow-md shadow-red-500/20">
        Société Générale
      </div>
      <h1 className="text-5xl font-bold tracking-tight mb-4 bg-gradient-to-br from-red-600 via-red-500 to-amber-500 bg-clip-text text-transparent">
        VRM Intelligence
      </h1>
      <p className="text-lg text-fd-muted-foreground mb-2 max-w-xl">
        AI-powered Third-Party Vendor Risk Management.
      </p>
      <p className="text-sm text-fd-muted-foreground mb-10 max-w-2xl">
        400 vendors, continuous scoring, streaming Q&amp;A, one-click audit
        packs. All 5 hackathon rubric metrics measured and passing.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full max-w-2xl mb-10">
        <Link
          href="/docs"
          className="group rounded-xl border border-fd-border bg-fd-card hover:bg-fd-accent transition-colors p-5 text-left"
        >
          <h3 className="font-semibold mb-1">Documentation →</h3>
          <p className="text-sm text-fd-muted-foreground">
            Quickstart, architecture, scoring engine, API reference.
          </p>
        </Link>
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noreferrer"
          className="group rounded-xl border border-fd-border bg-fd-card hover:bg-fd-accent transition-colors p-5 text-left"
        >
          <h3 className="font-semibold mb-1">OpenAPI / Swagger →</h3>
          <p className="text-sm text-fd-muted-foreground">
            Live, interactive API explorer (requires <code>make api</code>).
          </p>
        </a>
        <a
          href="http://localhost:3000"
          target="_blank"
          rel="noreferrer"
          className="group rounded-xl border border-fd-border bg-fd-card hover:bg-fd-accent transition-colors p-5 text-left"
        >
          <h3 className="font-semibold mb-1">Dashboard →</h3>
          <p className="text-sm text-fd-muted-foreground">
            Next.js portfolio view (requires <code>make web</code>).
          </p>
        </a>
        <a
          href="https://societegenerale.iamneo.ai/third-party-vendor-risk-management/"
          target="_blank"
          rel="noreferrer"
          className="group rounded-xl border border-fd-border bg-fd-card hover:bg-fd-accent transition-colors p-5 text-left"
        >
          <h3 className="font-semibold mb-1">Hackathon brief →</h3>
          <p className="text-sm text-fd-muted-foreground">
            Original problem statement &amp; rubric from Société Générale.
          </p>
        </a>
      </div>
    </div>
  );
}
