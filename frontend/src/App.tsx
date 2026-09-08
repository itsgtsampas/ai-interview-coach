import { useCallback, useEffect, useState } from "react";
import {
  Navigate, Outlet, Route, BrowserRouter as Router, Routes, useParams,
} from "react-router-dom";

import { api } from "./api/client";
import type { SessionOut } from "./api/types";
import { Rail } from "./components/Rail";
import { Spinner } from "./components/bits";
import { AuthProvider, useAuth } from "./lib/auth";
import { Coach } from "./pages/Coach";
import { Dashboard } from "./pages/Dashboard";
import { Report } from "./pages/Report";
import { Room } from "./pages/Room";
import { ScorecardPage } from "./pages/ScorecardPage";
import { SignIn } from "./pages/SignIn";
import { Upload } from "./pages/Upload";

function Shell({ session, refresh }: { session: SessionOut | null; refresh: () => Promise<void> }) {
  return (
    <div className="shell">
      <Rail session={session} />
      <main>
        <Outlet context={{ session, refresh }} />
      </main>
    </div>
  );
}

/** Loads the session once for the whole stage sequence, so the rail's stepper
 *  and every page below it read the same state. */
function SessionShell() {
  const { id } = useParams();
  const [session, setSession] = useState<SessionOut | null>(null);

  const refresh = useCallback(async () => {
    if (!id) return;
    setSession(await api.getSession(Number(id)));
  }, [id]);

  useEffect(() => { refresh(); }, [refresh]);

  return <Shell session={session} refresh={refresh} />;
}

function Protected() {
  const { user, loading } = useAuth();
  if (loading) {
    return <div className="centre"><Spinner label="Signing you in…" /></div>;
  }
  return user ? <Outlet /> : <Navigate to="/signin" replace />;
}

function Routing() {
  const { user, loading } = useAuth();
  return (
    <Routes>
      <Route
        path="/signin"
        element={loading ? <div className="centre"><Spinner /></div>
          : user ? <Navigate to="/" replace /> : <SignIn />}
      />
      <Route element={<Protected />}>
        <Route element={<Shell session={null} refresh={async () => {}} />}>
          <Route index element={<Dashboard />} />
        </Route>
        <Route path="/session/:id" element={<SessionShell />}>
          <Route index element={<Navigate to="report" replace />} />
          <Route path="upload" element={<Upload />} />
          <Route path="report" element={<Report />} />
          <Route path="room" element={<Room />} />
          <Route path="scorecard" element={<ScorecardPage />} />
          <Route path="coach" element={<Coach />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <Routing />
      </Router>
    </AuthProvider>
  );
}
