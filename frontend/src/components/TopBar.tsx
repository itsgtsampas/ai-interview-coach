import { useEffect, useRef, useState } from "react";
import { Link, NavLink } from "react-router-dom";

import { useAuth } from "../lib/auth";
import { useT } from "../lib/i18n";
import { Logo } from "./Logo";

/** Global navigation. The left rail handles movement *within* a session; this
 *  handles movement between the things a session is not — the session list and
 *  the profile — which previously had no home at all. */
export function TopBar() {
  const { user, signOut } = useAuth();
  const { t, lang, setLang } = useT();
  const [menuOpen, setMenuOpen] = useState(false);
  const menu = useRef<HTMLDivElement>(null);

  // Close on an outside click or Escape, the two ways anyone expects to dismiss
  // a menu they opened by accident.
  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (!menu.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const initials = (user?.full_name || user?.email || "?")
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");

  return (
    <header className="topbar">
      <Link to="/" className="topbar__brand">
        <Logo />
        <span className="topbar__word">Interview Coach</span>
      </Link>

      <nav className="topbar__nav" aria-label="Sections">
        <NavLink to="/" end className="topbar__link">{t("nav.sessions")}</NavLink>
        <NavLink to="/progress" className="topbar__link">{t("nav.progress")}</NavLink>
        <NavLink to="/profile" className="topbar__link">{t("nav.profile")}</NavLink>
      </nav>

      <div className="topbar__account" ref={menu}>
        <button
          className="avatar"
          onClick={() => setMenuOpen((o) => !o)}
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          aria-label={t("nav.account")}
        >
          {initials}
        </button>
        {menuOpen ? (
          <div className="menu" role="menu">
            <p className="menu__who">
              {user?.full_name}
              <span className="menu__email">{user?.email}</span>
            </p>
            <Link to="/progress" className="menu__item" role="menuitem"
                  onClick={() => setMenuOpen(false)}>
              {t("nav.yourProgress")}
            </Link>
            <Link to="/profile" className="menu__item" role="menuitem"
                  onClick={() => setMenuOpen(false)}>
              {t("nav.yourProfile")}
            </Link>
            {/* A two-locale switcher is a pair of buttons, not a dropdown. */}
            <div className="menu__lang" role="group" aria-label={t("nav.language")}>
              {(["en", "el"] as const).map((code) => (
                <button
                  key={code}
                  className="menu__langbtn"
                  data-on={lang === code}
                  aria-pressed={lang === code}
                  onClick={() => setLang(code)}
                >
                  {code === "en" ? "English" : "Ελληνικά"}
                </button>
              ))}
            </div>
            <button className="menu__item" role="menuitem" onClick={signOut}>
              {t("nav.signOut")}
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}
