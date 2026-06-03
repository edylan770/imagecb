import { Link } from "react-router-dom";
import { getAdminApiKey } from "../api/adminClient";

type Variant = "header" | "sidebar" | "sidebarCollapsed";

interface AdminNavLinkProps {
  variant: Variant;
}

function LockIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 20 20"
      fill="currentColor"
      aria-hidden
    >
      <path
        fillRule="evenodd"
        d="M10 1a4 4 0 00-4 4v2H5a2 2 0 00-2 2v7a2 2 0 002 2h10a2 2 0 002-2v-7a2 2 0 00-2-2h-1V5a4 4 0 00-4-4zm-2 4V5a2 2 0 114 0v2H8z"
        clipRule="evenodd"
      />
    </svg>
  );
}

export function AdminNavLink({ variant }: AdminNavLinkProps) {
  const hasKey = !!getAdminApiKey();
  const label = hasKey ? "Admin" : "Admin login";
  const title = hasKey
    ? "Open admin dashboard"
    : "Sign in with admin API key";

  if (variant === "sidebarCollapsed") {
    return (
      <Link
        to="/admin"
        title={title}
        className="mt-2 flex rounded-lg p-2 text-slate-500 ring-1 ring-transparent transition hover:bg-slate-200 hover:text-brand-600 hover:ring-slate-200"
        aria-label={label}
      >
        <LockIcon className="h-5 w-5" />
      </Link>
    );
  }

  if (variant === "sidebar") {
    return (
      <Link
        to="/admin"
        title={title}
        className="flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-600 ring-1 ring-slate-200 transition hover:bg-white hover:text-brand-600 hover:ring-brand-200"
      >
        <LockIcon className="h-4 w-4 shrink-0" />
        {label}
      </Link>
    );
  }

  return (
    <Link
      to="/admin"
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition ${
        hasKey
          ? "text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 hover:text-brand-600"
          : "text-slate-600 ring-1 ring-slate-200 hover:bg-brand-50 hover:text-brand-700 hover:ring-brand-200"
      }`}
    >
      <LockIcon className="h-4 w-4 shrink-0" />
      {label}
    </Link>
  );
}
