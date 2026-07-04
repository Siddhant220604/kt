import { Link, NavLink, useNavigate } from "react-router-dom";
import { ShoppingCart, User, Package, SignOut, Storefront } from "@phosphor-icons/react";
import { useAuth } from "../context/AuthContext";
import { useCart } from "../context/CartContext";
import { Button } from "./ui/button";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from "./ui/dropdown-menu";

export default function Navbar() {
  const { user, logout } = useAuth();
  const { totals, setOpen } = useCart();
  const navigate = useNavigate();

  const nav = [
    { to: "/", label: "Home" },
    { to: "/catalog", label: "Catalog" },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6">
        <Link to="/" data-testid="navbar-logo" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center bg-primary text-primary-foreground">
            <Storefront weight="fill" size={18} aria-hidden="true" />
          </div>
          <div className="flex flex-col leading-none">
            <span className="text-lg font-black tracking-tight">BULKHAUS</span>
            <span className="label-caps text-[9px]">Wholesale Disposables</span>
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              data-testid={`navbar-link-${n.label.toLowerCase()}`}
              className={({ isActive }) =>
                `text-sm font-medium ${isActive ? "text-foreground" : "text-muted-foreground hover:text-foreground"}`
              }
              end={n.to === "/"}
            >
              {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setOpen(true)}
            data-testid="navbar-cart-button"
            className="relative rounded-sm"
          >
            <ShoppingCart size={16} aria-hidden="true" />
            <span className="ml-2 hidden sm:inline">Cart</span>
            {totals.lines > 0 && (
              <span
                data-testid="navbar-cart-count"
                className="ml-2 inline-flex h-5 min-w-[20px] items-center justify-center bg-primary px-1 text-[10px] font-bold text-primary-foreground"
              >
                {totals.lines}
              </span>
            )}
          </Button>

          {user && user !== false ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" data-testid="navbar-user-menu" className="rounded-sm">
                  <User size={16} aria-hidden="true" />
                  <span className="ml-2 hidden sm:inline">{user.name.split(" ")[0]}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56 rounded-sm">
                <DropdownMenuLabel className="label-caps">{user.email}</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => navigate("/orders")} data-testid="menu-orders">
                  <Package size={16} className="mr-2" /> My Orders
                </DropdownMenuItem>
                {user.role === "admin" && (
                  <DropdownMenuItem onClick={() => navigate("/admin")} data-testid="menu-admin">
                    <Storefront size={16} className="mr-2" /> Admin Dashboard
                  </DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  onClick={async () => {
                    await logout();
                    navigate("/");
                  }}
                  data-testid="menu-logout"
                >
                  <SignOut size={16} className="mr-2" /> Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => navigate("/login")}
                data-testid="navbar-login-button"
                className="rounded-sm"
              >
                Sign in
              </Button>
              <Button
                size="sm"
                onClick={() => navigate("/register")}
                data-testid="navbar-register-button"
                className="rounded-sm"
              >
                Create Account
              </Button>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
