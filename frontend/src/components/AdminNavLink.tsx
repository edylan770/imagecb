import { Link } from "react-router-dom";
import { getAdminApiKey } from "../api/adminClient";

type Variant = "sidebar";

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
    ? "Open ATLAS admin dashboard"
    : "Sign in with admin API key";

  if (variant === "sidebar") {
    return (
      <Link
        to="/admin"
        title={title}
        className="flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-navy-600 ring-1 ring-navy-200 transition hover:bg-white hover:text-brand-600 hover:ring-brand-200"
      >
        <LockIcon className="h-4 w-4 shrink-0" />
        {label}
      </Link>
    );
  }

  return null;
}
