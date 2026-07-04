import { NavLink, Outlet, Link } from "react-router-dom";
import { ChartLine, Package, ListChecks, TagChevron, Star, ArrowLeft } from "@phosphor-icons/react";

const LINKS = [
  { to: "/admin", label: "Dashboard", icon: ChartLine, end: true, testId: "admin-sidebar-link-dashboard" },
  { to: "/admin/products", label: "Products", icon: Package, testId: "admin-sidebar-link-products" },
  { to: "/admin/categories", label: "Categories", icon: TagChevron, testId: "admin-sidebar-link-categories" },
  { to: "/admin/orders", label: "Orders", icon: ListChecks, testId: "admin-sidebar-link-orders" },
  { to: "/admin/reviews", label: "Reviews", icon: Star, testId: "admin-sidebar-link-reviews" },
];

export default function AdminLayout() {
  return (
    <div className="mx-auto flex max-w-[1600px] gap-0">
      <aside className="hidden lg:flex w-60 shrink-0 flex-col border-r border-border bg-card min-h-screen sticky top-16 self-start" style={{ height: "calc(100vh - 4rem)" }}>
        <div className="border-b border-border p-5">
          <div className="label-caps mb-1">Admin</div>
          <div className="text-sm font-bold">Control Panel</div>
        </div>
        <nav className="flex-1 py-3">
          {LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              data-testid={l.testId}
              className={({ isActive }) =>
                `flex items-center gap-3 px-5 py-2.5 text-sm ${
                  isActive
                    ? "bg-muted font-semibold text-foreground border-l-2 border-primary"
                    : "text-muted-foreground hover:text-foreground border-l-2 border-transparent"
                }`
              }
            >
              <l.icon size={16} />
              {l.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-border p-4">
          <Link to="/" className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground">
            <ArrowLeft size={12} /> Back to storefront
          </Link>
        </div>
      </aside>

      {/* Mobile top nav for admin */}
      <div className="lg:hidden fixed top-16 left-0 right-0 z-20 border-b border-border bg-card overflow-x-auto">
        <div className="flex gap-1 px-4 py-2">
          {LINKS.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              className={({ isActive }) =>
                `flex items-center gap-1.5 whitespace-nowrap px-3 py-1.5 text-xs ${
                  isActive ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                }`
              }
            >
              <l.icon size={12} /> {l.label}
            </NavLink>
          ))}
        </div>
      </div>

      <main className="flex-1 min-w-0 lg:mt-0 mt-12 p-6 lg:p-8">
        <Outlet />
      </main>
    </div>
  );
}
