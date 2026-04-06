import { Link, NavLink, Outlet } from "react-router-dom";

type LayoutProps = {
  onLogout: () => void;
  username?: string;
};

export function Layout({ onLogout, username }: LayoutProps) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <Link to="/" className="brand">
          <span className="brand-mark">MG</span>
          <div>
            <strong>MobGuard</strong>
            <small>Admin panel</small>
          </div>
        </Link>
        <nav className="nav">
          <NavLink to="/">Queue</NavLink>
          <NavLink to="/rules">Rules</NavLink>
          <NavLink to="/quality">Quality</NavLink>
        </nav>
        <div className="sidebar-footer">
          <span>{username || "Admin"}</span>
          <button onClick={onLogout}>Logout</button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
