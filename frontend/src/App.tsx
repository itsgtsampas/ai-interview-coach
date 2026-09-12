import { useCallback, useEffect, useState } from "react";
import {
  Navigate, Outlet, Route, BrowserRouter as Router, Routes, useParams,
} from "react-router-dom";

import { api } from "./api/client";
import type { SessionOut } from "./api/types";
import { Rail } from "./components/Rail";
import { TopBar } from "./components/TopBar";
import { Spinner } from "./components/bits";
import { AuthProvider, useAuth } from "./lib/auth";
import { Coach } from "./pages/Coach";
import { Dashboard } from "./pages/Dashboard";
import { Letter } from "./pages/Letter";
import { Profile } from "./pages/Profile";
import { Progress } from "./pages/Progress";
import { Report } from "./pages/Report";
import { Room } from "./pages/Room";
import { ScorecardPage } from "./pages/ScorecardPage";
import { SignIn } from "./pages/SignIn";
import { Upload } from "./pages/Upload";

function Shell({
  session, refresh, withRail = true,
}: {
  session: SessionOut | null;
  refresh: () => Promise<void>;
  withRail?: boolean;
}) {
  return (
    <div className="app">
      <TopBar />
      <div className={withRail ? "shell" : "shell shell--plain"}>
        {withRail ? <Rail session={session} /> : null}
        <main>
          <Outlet context={{ session, refresh }} />
        </main>
      </div>
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
        <Route element={<Shell session={null} refresh={async () => {}} withRail={false} />}>
          <Route index element={<Dashboard />} />
          <Route path="/progress" element={<Progress />} />
          <Route path="/profile" element={<Profile />} />
        </Route>
        <Route path="/session/:id" element={<SessionShell />}>
          <Route index element={<Navigate to="report" replace />} />
          <Route path="upload" element={<Upload />} />
          <Route path="report" element={<Report />} />
          <Route path="room" element={<Room />} />
          <Route path="scorecard" element={<ScorecardPage />} />
          <Route path="letter" element={<Letter />} />
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
