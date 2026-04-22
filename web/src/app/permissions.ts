import { Session } from "../api/client";

export type AppPermission =
  | "overview.read"
  | "quality.read"
  | "reviews.read"
  | "reviews.resolve"
  | "reviews.recheck"
  | "rules.read"
  | "rules.write"
  | "settings.telegram.read"
  | "settings.telegram.write"
  | "settings.enforcement.read"
  | "settings.enforcement.write"
  | "settings.access.read"
  | "settings.access.write"
  | "data.read"
  | "data.write"
  | "modules.read"
  | "modules.write"
  | "modules.token_reveal"
  | "audit.read";

export function hasPermission(session: Session | null | undefined, permission: AppPermission): boolean {
  if (!session) return false;
  return Array.isArray(session.permissions) ? session.permissions.includes(permission) : false;
}

export function firstAccessibleRoute(session: Session | null | undefined): string {
  if (hasPermission(session, "overview.read")) return "/overview";
  if (hasPermission(session, "reviews.read")) return "/queue";
  if (hasPermission(session, "quality.read")) return "/quality";
  if (hasPermission(session, "modules.read")) return "/modules";
  if (hasPermission(session, "data.read")) return "/data/users";
  return "/overview";
}
