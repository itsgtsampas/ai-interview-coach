import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { ProfileOut, ProfileUpdate, Seniority } from "../api/types";
import { ErrorBox, Head, Row, Spinner } from "../components/bits";

const SENIORITY: { value: Seniority | ""; label: string }[] = [
  { value: "", label: "—" },
  { value: "intern", label: "Intern" },
  { value: "junior", label: "Junior" },
  { value: "mid", label: "Mid" },
  { value: "senior", label: "Senior" },
  { value: "lead", label: "Lead" },
  { value: "principal", label: "Principal" },
];

function Field({
  label, hint, children,
}: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="field">
      <label className="label">{label}</label>
      {children}
      {hint ? <span className="hint">{hint}</span> : null}
    </div>
  );
}

export function Profile() {
  const [profile, setProfile] = useState<ProfileOut | null>(null);
  const [form, setForm] = useState<ProfileUpdate | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [cvBusy, setCvBusy] = useState(false);

  useEffect(() => {
    api.getProfile()
      .then((p) => { setProfile(p); setForm(toForm(p)); })
      .catch(setError);
  }, []);

  function toForm(p: ProfileOut): ProfileUpdate {
    const { id, full_name, email, age, has_cv, cv_filename, cv_page_count,
            cv_uploaded_at, updated_at, ...rest } = p;
    void id; void full_name; void email; void age; void has_cv;
    void cv_filename; void cv_page_count; void cv_uploaded_at; void updated_at;
    return rest;
  }

  function set<K extends keyof ProfileUpdate>(key: K, value: ProfileUpdate[K]) {
    setForm((f) => (f ? { ...f, [key]: value } : f));
    setSaved(false);
  }

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setBusy(true); setError(null);
    try {
      const updated = await api.updateProfile(form);
      setProfile(updated);
      setSaved(true);
    } catch (err) { setError(err); } finally { setBusy(false); }
  }

  async function uploadCv(file: File) {
    setCvBusy(true); setError(null);
    try {
      setProfile(await api.uploadProfileCv(file));
    } catch (err) { setError(err); } finally { setCvBusy(false); }
  }

  async function removeCv() {
    setCvBusy(true); setError(null);
    try {
      setProfile(await api.deleteProfileCv());
    } catch (err) { setError(err); } finally { setCvBusy(false); }
  }

  if (!profile || !form) {
    return <div className="sheet"><Spinner label="Loading your profile…" /></div>;
  }

  return (
    <div className="sheet">
      <Head margin={<span className="label">Your file</span>}>
        <h1 className="display h1">{profile.full_name}</h1>
        <p className="prose" style={{ marginBottom: 0 }}>
          What stays the same across applications lives here. New sessions start from
          your CV automatically — you can still use a different one for any single
          application.
        </p>
      </Head>

      <Row margin={<span className="label">Your CV</span>}>
        <div className="drop" data-state={profile.has_cv ? "ready" : "idle"}>
          {profile.has_cv ? (
            <>
              <div className="label">Default CV</div>
              <p style={{ margin: "0.5rem 0 0.2rem", fontWeight: 600 }}>
                {profile.cv_filename}
              </p>
              <p className="hint" style={{ margin: 0 }}>
                {profile.cv_page_count} page{profile.cv_page_count === 1 ? "" : "s"}
                {profile.cv_uploaded_at
                  ? ` · added ${new Date(profile.cv_uploaded_at).toLocaleDateString()}`
                  : ""}
              </p>
            </>
          ) : (
            <>
              <div className="label">No CV yet</div>
              <p className="hint" style={{ margin: "0.5rem 0 0.7rem" }}>
                Add it once and every new session will start from it.
              </p>
            </>
          )}

          {cvBusy ? (
            <p style={{ margin: "0.7rem 0" }}><Spinner label="Reading…" /></p>
          ) : (
            <div className="split" style={{ justifyContent: "center" }}>
              <label className="drop__cta">
                {profile.has_cv ? "Replace CV" : "Choose a PDF"}
                <input
                  type="file" accept="application/pdf"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) uploadCv(f);
                    e.target.value = "";
                  }}
                />
              </label>
              {profile.has_cv ? (
                <button className="btn btn--link card__delete" onClick={removeCv}>
                  Remove
                </button>
              ) : null}
            </div>
          )}
        </div>
        <ErrorBox error={error} />
      </Row>

      <form onSubmit={save}>
        <Row margin={<span className="label">Professional</span>}>
          <p className="prose" style={{ margin: "0 0 1rem", fontSize: "0.88rem" }}>
            These are used when writing your interview questions.
          </p>
          <Field label="Current title">
            <input className="input" value={form.headline}
                   placeholder="Software Engineer"
                   onChange={(e) => set("headline", e.target.value)} />
          </Field>
          <div className="grid-2">
            <Field label="Seniority">
              <select className="input" value={form.seniority ?? ""}
                      onChange={(e) => set("seniority", (e.target.value || null) as Seniority | null)}>
                {SENIORITY.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </Field>
            <Field label="Years of experience">
              <input className="input" type="number" min={0} max={60}
                     value={form.years_experience ?? ""}
                     onChange={(e) => set("years_experience",
                       e.target.value === "" ? null : Number(e.target.value))} />
            </Field>
          </div>
          <Field label="Roles you are targeting"
                 hint="Shapes the behavioural questions.">
            <input className="input" value={form.target_roles}
                   placeholder="Backend Engineer, Platform Engineer"
                   onChange={(e) => set("target_roles", e.target.value)} />
          </Field>
          <Field label="Languages">
            <input className="input" value={form.languages}
                   placeholder="Greek (native), English (B2)"
                   onChange={(e) => set("languages", e.target.value)} />
          </Field>
        </Row>

        <Row margin={<span className="label">Contact</span>}>
          <div className="grid-2">
            <Field label="Location">
              <input className="input" value={form.location} placeholder="Athens, Greece"
                     onChange={(e) => set("location", e.target.value)} />
            </Field>
            <Field label="Phone">
              <input className="input" value={form.phone}
                     onChange={(e) => set("phone", e.target.value)} />
            </Field>
          </div>
          <Field label="LinkedIn">
            <input className="input" value={form.linkedin_url} placeholder="https://linkedin.com/in/…"
                   onChange={(e) => set("linkedin_url", e.target.value)} />
          </Field>
          <div className="grid-2">
            <Field label="GitHub">
              <input className="input" value={form.github_url}
                     onChange={(e) => set("github_url", e.target.value)} />
            </Field>
            <Field label="Portfolio">
              <input className="input" value={form.portfolio_url}
                     onChange={(e) => set("portfolio_url", e.target.value)} />
            </Field>
          </div>
        </Row>

        <Row
          margin={
            <>
              <span className="label">Personal</span>
              <span className="label">Optional</span>
            </>
          }
        >
          {/* These are on the Europass CV, which is why they are offered. They
              are also protected characteristics, so they are kept out of every
              prompt — see UserProfile.profile_context in the backend. */}
          <p className="prose" style={{ margin: "0 0 1rem", fontSize: "0.88rem" }}>
            The Europass CV asks for these, so they are here if you use that format.
            They are never sent to the AI: they cannot make a requirement met or
            unmet, and they have no business influencing your feedback.
          </p>
          <div className="grid-2">
            <Field label="Date of birth"
                   hint={profile.age != null ? `Age ${profile.age}` : undefined}>
              <input className="input" type="date" value={form.date_of_birth ?? ""}
                     onChange={(e) => set("date_of_birth", e.target.value || null)} />
            </Field>
            <Field label="Nationality">
              <input className="input" value={form.nationality}
                     onChange={(e) => set("nationality", e.target.value)} />
            </Field>
          </div>
          <Field label="Gender">
            <input className="input" value={form.gender} placeholder="Leave blank to omit"
                   onChange={(e) => set("gender", e.target.value)} />
          </Field>
        </Row>

        <Row margin={<span className="label">Save</span>}>
          <ErrorBox error={error} />
          <div className="split">
            <button className="btn" disabled={busy}>
              {busy ? "Saving…" : "Save profile"}
            </button>
            {saved ? <span className="hint">Saved.</span> : null}
          </div>
        </Row>
      </form>
    </div>
  );
}
