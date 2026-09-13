/** Interface language.
 *
 *  No i18n library: this is two locales and a flat dictionary, where
 *  react-intl or i18next would add a bundle and a message syntax to learn for
 *  no behaviour we need. What is worth keeping from those libraries is the
 *  discipline, so the dictionary is typed - a key that exists in English and
 *  not in Greek is a compile error, not a blank on the page.
 *
 *  The model answers in the language of the candidate's documents, decided
 *  server-side. This setting is separate and controls only the chrome, so a
 *  Greek CV can be reviewed through an English interface and the other way
 *  round.
 */

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Lang = "en" | "el";

const KEY = "cvcoach.lang";

const en = {
  "nav.sessions": "Sessions",
  "nav.progress": "Progress",
  "nav.profile": "Profile",
  "nav.yourProfile": "Your profile",
  "nav.yourProgress": "Your progress",
  "nav.signOut": "Sign out",
  "nav.account": "Account",
  "nav.language": "Language",

  "stage.documents": "Documents",
  "stage.report": "Gap analysis",
  "stage.room": "Practice",
  "stage.scorecard": "Scorecard",
  "stage.letter": "Cover letter",
  "stage.coach": "Coach",
  "stage.label": "Stage",
  "stage.allSessions": "All sessions",
  "stage.switch": "Switch session",
  "stage.newSession": "+ New session",
  "stage.onlySession": "This is your only session.",
  "stage.ofStages": "{done} of {total} stages",

  "verdict.strong": "Evidenced",
  "verdict.partial": "Thin",
  "verdict.missing": "No evidence",
  "verdict.mustHave": "Must have",
  "verdict.niceToHave": "Nice to have",

  "common.loading": "Loading…",
  "common.save": "Save",
  "common.saved": "Saved.",
  "common.copy": "Copy",
  "common.copied": "Copied",
  "common.delete": "Delete",
  "common.keep": "Keep",
  "common.replace": "Replace",
  "common.remove": "Remove",
  "common.next": "Next",
  "common.back": "Back",
  "common.of": "of",
  "common.optional": "Optional",
  "common.noEvidenceLine": "No sentence in the CV supports this.",

  "dash.title": "Sessions",
  "dash.lead":
    "One session pairs a CV with a job description. Everything else — the gap analysis, the questions, the scorecard — is derived from that pair.",
  "dash.new": "New",
  "dash.existing": "Existing",
  "dash.name": "Session name",
  "dash.role": "Target role",
  "dash.roleHint": "Used to shape the behavioural questions.",
  "dash.create": "Create session",
  "dash.creating": "Creating…",
  "dash.empty": "Nothing here yet. Create your first session above.",
  "dash.confirmDelete": "Delete this session and its documents?",
  "dash.ready": "Ready",
  "dash.scored": "Scored",
  "dash.analysed": "Analysed",
  "dash.needsDocs": "Needs documents",
  "dash.answered": "{n} answered",

  "report.title": "Gap analysis",
  "report.run": "Run gap analysis",
  "report.running": "Analysing…",
  "report.none": "No analysis has been run for this session yet.",
  "report.ofRole": "of what the role asks for",
  "report.notOnCv": "Not on a CV",
  "report.askedInInterview": "Asked about in the interview",
  "report.suggestBullet": "Suggest a CV bullet",
  "report.suggestedBullet": "Suggested bullet",
  "report.slotsNote":
    "The highlighted parts are yours to fill in. Nothing in this bullet is a claim about you until you make it one.",
  "report.whyShape": "Why this shape:",
  "report.goToPractice": "Go to practice",

  "score.title": "Scorecard",
  "score.competencies": "Competencies",
  "score.strengths": "Strengths",
  "score.gaps": "Gaps",
  "score.doNext": "Do this next",
  "score.build": "Build scorecard",
  "score.building": "Building…",
  "score.rebuild": "Rebuild from latest answers",
  "score.download": "Download PDF",
  "score.how": "How:",

  "letter.title": "Cover letter",
  "letter.tone": "Tone",
  "letter.write": "Write the letter",
  "letter.writing": "Writing…",
  "letter.rewrite": "Rewrite",
  "letter.stop": "Stop",
  "letter.draft": "Draft",
  "letter.builtFrom": "Built from",
  "letter.plain": "Plain",
  "letter.warm": "Warm",
  "letter.formal": "Formal",

  "progress.title": "Progress",
  "progress.acrossSessions": "Across sessions",
  "progress.whereYouAre": "Where you are",
  "progress.sessions": "Sessions",
  "progress.avgMatch": "Average CV match",
  "progress.answers": "Answers practised",
  "progress.avgAnswer": "Average answer",
  "progress.latest": "Latest readiness",
  "progress.readiness": "Readiness",
  "progress.keepsCosting": "Keeps costing you",
  "progress.showNumbers": "Show the numbers",
  "progress.allSessions": "All sessions",

  "rail.bothDocs": "CV + job description",
  "rail.docsOf": "{n} of 2",
  "rail.answeredOf": "{done} of {total} answered",
  "rail.ready": "{n}/100 ready",
  "rail.needDocs": "Add your CV and the job description first",
  "rail.needAnalysis": "Run the gap analysis first",
  "rail.needAnswer": "Answer a question first",
  "count.evidenced": "{n} evidenced",
  "count.thin": "{n} thin",
  "count.missing": "{n} missing",
  "score.outOf": "{n} out of {max}",
  "score.readySuffix": "/100 ready",
  // The four bands the scorecard prompt assigns. They arrive as fixed English
  // strings because the prompt names them literally, so they behave as an enum
  // and are translated here rather than left to the model.
  "band.Interview ready": "Interview ready",
  "band.Nearly ready": "Nearly ready",
  "band.Needs work": "Needs work",
  "band.Not ready yet": "Not ready yet",
  "upload.title": "Documents",
  "upload.lead": "Your CV as a PDF, and the job description however you have it — pasted from the posting, or as a file.",
  "upload.yourCv": "Your CV",
  "upload.jd": "Job description",
  "upload.cvHint": "A text-based PDF — the kind where you can select the text in a reader. Scans are rejected rather than misread.",
  "upload.jdHint": "Save the posting as a PDF and choose it here.",
  "upload.pasteInstead": "Paste text instead",
  "upload.uploadInstead": "Upload a PDF instead",
  "upload.choosePdf": "Choose a PDF",
  "upload.replaceFile": "Replace file",
  "upload.reading": "Reading and indexing…",
  "upload.usePasted": "Use this job description",
  "upload.nextLead": "The analysis reads every requirement in the job description and searches your CV for evidence of each one.",
  "upload.bothNeeded": "Both documents are needed first.",
  "upload.pastePlaceholder": "Paste the whole posting — requirements, responsibilities, nice-to-haves.",
  "upload.minChars": "{n} of 200 characters minimum",
  "room.title": "Practice",
  "room.lead": "Questions drawn from your gap analysis. The requirements with no evidence come first — those are the ones that end interviews.",
  "room.submit": "Submit for scoring",
  "room.scoring": "Scoring…",
  "room.again": "Answer again",
  "room.nextQuestion": "Next question",
  "room.placeholder": "Answer out loud first, then type what you actually said. Aim for 90 seconds of speech.",
  "coach.title": "Coach",
  "coach.lead": "The coach can read your CV, the job description, your gap analysis and your scores. It decides which of those to consult for each question, and shows you every lookup it made.",
  "coach.placeholder": "Ask about your CV, the role, or your scores",
  "coach.ask": "Ask",
  "signin.lead": "Upload your CV and the job description. Get an honest, evidenced read on where you stand — every claim shows the sentence it came from.",
  "signin.passwordHint": "At least 8 characters, with letters and numbers.",
  "signin.signIn": "Sign in",
  "signin.createOne": "Create one",
  "profile.lead": "What stays the same across applications lives here. New sessions start from your CV automatically — you can still use a different one for any single application.",
  "profile.cvOnce": "Add it once and every new session will start from it.",
  "profile.forQuestions": "These are used when writing your interview questions.",
  "profile.europass": "The Europass CV asks for these, so they are here if you use that format. They are never sent to the AI: they cannot make a requirement met or unmet, and they have no business influencing your feedback.",
  "profile.professional": "Professional",
  "profile.contact": "Contact",
  "profile.personal": "Personal",
  "progress.competencyNote": "Averaged per session, weakest movement first. Each is scored out of five.",
  "letter.eachMarked": "Each of these was marked Evidenced in your gap analysis, with a quote from your CV behind it.",
  "room.generate": "Generate questions",
  "room.generating": "Writing questions…",
  "room.allQuestions": "All {n} questions",
  "room.answered": "Answered",
  "room.yourAnswer": "Your answer",
  "room.score": "Score",
  "room.whyScore": "Why this score",
  "room.whatWorked": "What worked",
  "room.fixNext": "Fix next",
  "room.strongerShape": "A stronger shape",
  "room.theyWouldAsk": "They would ask",
  "room.technicalRubric": "Technical rubric",
  "room.starRubric": "STAR rubric",
  "room.difficulty": "Difficulty {n}/5",
  "room.progressLabel": "Scoring progress",
  "cat.technical": "Technical",
  "cat.behavioural": "Behavioural",
  "crit.Correctness": "Correctness",
  "crit.Depth": "Depth",
  "crit.Trade-offs": "Trade-offs",
  "crit.Communication": "Communication",
  "crit.Relevance": "Relevance",
  "crit.Situation": "Situation",
  "crit.Task": "Task",
  "crit.Action": "Action",
  "crit.Result": "Result",
  "crit.Reflection": "Reflection",
  "score.competencyNote": "Averaged across every answer you scored, weakest first. The notch on each bar is 3.5 — roughly where an answer stops costing you the interview.",
} as const;

export type Key = keyof typeof en;

const el: Record<Key, string> = {
  "nav.sessions": "Αιτήσεις",
  "nav.progress": "Πρόοδος",
  "nav.profile": "Προφίλ",
  "nav.yourProfile": "Το προφίλ σου",
  "nav.yourProgress": "Η πρόοδός σου",
  "nav.signOut": "Αποσύνδεση",
  "nav.account": "Λογαριασμός",
  "nav.language": "Γλώσσα",

  "stage.documents": "Έγγραφα",
  "stage.report": "Ανάλυση κενών",
  "stage.room": "Εξάσκηση",
  "stage.scorecard": "Καρτέλα ετοιμότητας",
  "stage.letter": "Συνοδευτική επιστολή",
  "stage.coach": "Προπονητής",
  "stage.label": "Στάδιο",
  "stage.allSessions": "Όλες οι αιτήσεις",
  "stage.switch": "Αλλαγή αίτησης",
  "stage.newSession": "+ Νέα αίτηση",
  "stage.onlySession": "Είναι η μόνη σου αίτηση.",
  "stage.ofStages": "{done} από {total} στάδια",

  "verdict.strong": "Τεκμηριωμένο",
  "verdict.partial": "Ισχνό",
  "verdict.missing": "Χωρίς τεκμήριο",
  "verdict.mustHave": "Απαραίτητο",
  "verdict.niceToHave": "Επιθυμητό",

  "common.loading": "Φόρτωση…",
  "common.save": "Αποθήκευση",
  "common.saved": "Αποθηκεύτηκε.",
  "common.copy": "Αντιγραφή",
  "common.copied": "Αντιγράφηκε",
  "common.delete": "Διαγραφή",
  "common.keep": "Διατήρηση",
  "common.replace": "Αντικατάσταση",
  "common.remove": "Αφαίρεση",
  "common.next": "Επόμενο",
  "common.back": "Πίσω",
  "common.of": "από",
  "common.optional": "Προαιρετικό",
  "common.noEvidenceLine": "Καμία πρόταση του βιογραφικού δεν το τεκμηριώνει.",

  "dash.title": "Αιτήσεις",
  "dash.lead":
    "Κάθε αίτηση συνδυάζει ένα βιογραφικό με μία αγγελία. Όλα τα υπόλοιπα — η ανάλυση κενών, οι ερωτήσεις, η καρτέλα — προκύπτουν από αυτό το ζεύγος.",
  "dash.new": "Νέα",
  "dash.existing": "Υπάρχουσες",
  "dash.name": "Όνομα αίτησης",
  "dash.role": "Θέση-στόχος",
  "dash.roleHint": "Καθορίζει τις ερωτήσεις συμπεριφοράς.",
  "dash.create": "Δημιουργία αίτησης",
  "dash.creating": "Δημιουργία…",
  "dash.empty": "Τίποτα ακόμα. Δημιούργησε την πρώτη σου αίτηση παραπάνω.",
  "dash.confirmDelete": "Διαγραφή της αίτησης και των εγγράφων της;",
  "dash.ready": "Έτοιμη",
  "dash.scored": "Βαθμολογήθηκε",
  "dash.analysed": "Αναλύθηκε",
  "dash.needsDocs": "Λείπουν έγγραφα",
  "dash.answered": "{n} απαντήθηκαν",

  "report.title": "Ανάλυση κενών",
  "report.run": "Εκτέλεση ανάλυσης",
  "report.running": "Ανάλυση…",
  "report.none": "Δεν έχει γίνει ακόμα ανάλυση για αυτή την αίτηση.",
  "report.ofRole": "όσων ζητάει η θέση",
  "report.notOnCv": "Δεν φαίνεται σε βιογραφικό",
  "report.askedInInterview": "Θα ρωτηθούν στη συνέντευξη",
  "report.suggestBullet": "Πρόταση για το βιογραφικό",
  "report.suggestedBullet": "Προτεινόμενη γραμμή",
  "report.slotsNote":
    "Τα τονισμένα σημεία τα συμπληρώνεις εσύ. Τίποτα εδώ δεν είναι ισχυρισμός για σένα μέχρι να τον κάνεις εσύ.",
  "report.whyShape": "Γιατί αυτή η μορφή:",
  "report.goToPractice": "Στην εξάσκηση",

  "score.title": "Καρτέλα ετοιμότητας",
  "score.competencies": "Δεξιότητες",
  "score.strengths": "Δυνατά σημεία",
  "score.gaps": "Κενά",
  "score.doNext": "Κάνε αυτά μετά",
  "score.build": "Δημιουργία καρτέλας",
  "score.building": "Δημιουργία…",
  "score.rebuild": "Ανανέωση με τις τελευταίες απαντήσεις",
  "score.download": "Λήψη PDF",
  "score.how": "Πώς:",

  "letter.title": "Συνοδευτική επιστολή",
  "letter.tone": "Ύφος",
  "letter.write": "Σύνταξη επιστολής",
  "letter.writing": "Γράφεται…",
  "letter.rewrite": "Ξαναγράψε",
  "letter.stop": "Διακοπή",
  "letter.draft": "Προσχέδιο",
  "letter.builtFrom": "Βασισμένη σε",
  "letter.plain": "Λιτό",
  "letter.warm": "Θερμό",
  "letter.formal": "Τυπικό",

  "progress.title": "Πρόοδος",
  "progress.acrossSessions": "Σε όλες τις αιτήσεις",
  "progress.whereYouAre": "Πού βρίσκεσαι",
  "progress.sessions": "Αιτήσεις",
  "progress.avgMatch": "Μέση αντιστοίχιση",
  "progress.answers": "Απαντήσεις",
  "progress.avgAnswer": "Μέση απάντηση",
  "progress.latest": "Τρέχουσα ετοιμότητα",
  "progress.readiness": "Ετοιμότητα",
  "progress.keepsCosting": "Σου κοστίζουν συνεχώς",
  "progress.showNumbers": "Δες τους αριθμούς",
  "progress.allSessions": "Όλες οι αιτήσεις",

  "rail.bothDocs": "Βιογραφικό + αγγελία",
  "rail.docsOf": "{n} από 2",
  "rail.answeredOf": "{done} από {total} απαντήθηκαν",
  "rail.ready": "{n}/100 ετοιμότητα",
  "rail.needDocs": "Πρόσθεσε πρώτα το βιογραφικό και την αγγελία",
  "rail.needAnalysis": "Τρέξε πρώτα την ανάλυση κενών",
  "rail.needAnswer": "Απάντησε πρώτα μία ερώτηση",
  "count.evidenced": "{n} τεκμηριωμένα",
  "count.thin": "{n} ισχνά",
  "count.missing": "{n} χωρίς τεκμήριο",
  "score.outOf": "{n} στα {max}",
  "score.readySuffix": "/100 ετοιμότητα",
  "band.Interview ready": "Έτοιμος για συνέντευξη",
  "band.Nearly ready": "Σχεδόν έτοιμος",
  "band.Needs work": "Χρειάζεται δουλειά",
  "band.Not ready yet": "Όχι ακόμα έτοιμος",
  "upload.title": "Έγγραφα",
  "upload.lead": "Το βιογραφικό σου σε PDF, και την αγγελία όπως την έχεις — επικολλημένη από τη σελίδα ή ως αρχείο.",
  "upload.yourCv": "Το βιογραφικό σου",
  "upload.jd": "Αγγελία",
  "upload.cvHint": "PDF με επιλέξιμο κείμενο. Οι σαρώσεις απορρίπτονται αντί να διαβαστούν λάθος.",
  "upload.jdHint": "Αποθήκευσε την αγγελία ως PDF και διάλεξέ την εδώ.",
  "upload.pasteInstead": "Επικόλληση κειμένου",
  "upload.uploadInstead": "Ανέβασμα PDF",
  "upload.choosePdf": "Επιλογή PDF",
  "upload.replaceFile": "Αντικατάσταση αρχείου",
  "upload.reading": "Ανάγνωση και ευρετηρίαση…",
  "upload.usePasted": "Χρήση αυτής της αγγελίας",
  "upload.nextLead": "Η ανάλυση διαβάζει κάθε απαίτηση της αγγελίας και ψάχνει στο βιογραφικό σου τεκμήριο για καθεμία.",
  "upload.bothNeeded": "Χρειάζονται πρώτα και τα δύο έγγραφα.",
  "upload.pastePlaceholder": "Επικόλλησε ολόκληρη την αγγελία — απαιτήσεις, αρμοδιότητες, επιθυμητά προσόντα.",
  "upload.minChars": "{n} από 200 χαρακτήρες κατ' ελάχιστο",
  "room.title": "Εξάσκηση",
  "room.lead": "Ερωτήσεις από την ανάλυση κενών σου. Πρώτα οι απαιτήσεις χωρίς τεκμήριο — αυτές τελειώνουν τις συνεντεύξεις.",
  "room.submit": "Υποβολή για βαθμολόγηση",
  "room.scoring": "Βαθμολόγηση…",
  "room.again": "Απάντησε ξανά",
  "room.nextQuestion": "Επόμενη ερώτηση",
  "room.placeholder": "Απάντησε πρώτα δυνατά, μετά γράψε ό,τι πραγματικά είπες. Στόχευσε σε 90 δευτερόλεπτα ομιλίας.",
  "coach.title": "Προπονητής",
  "coach.lead": "Ο προπονητής διαβάζει το βιογραφικό σου, την αγγελία, την ανάλυση κενών και τις βαθμολογίες σου. Αποφασίζει μόνος του τι θα συμβουλευτεί, και σου δείχνει κάθε αναζήτηση που έκανε.",
  "coach.placeholder": "Ρώτησε για το βιογραφικό, τη θέση ή τις βαθμολογίες σου",
  "coach.ask": "Ρώτησε",
  "signin.lead": "Ανέβασε το βιογραφικό σου και την αγγελία. Δες πού στέκεσαι, με τεκμήρια — κάθε ισχυρισμός δείχνει την πρόταση από την οποία προέκυψε.",
  "signin.passwordHint": "Τουλάχιστον 8 χαρακτήρες, με γράμματα και αριθμούς.",
  "signin.signIn": "Σύνδεση",
  "signin.createOne": "Δημιούργησε έναν",
  "profile.lead": "Εδώ ζει ό,τι μένει ίδιο σε κάθε αίτηση. Οι νέες αιτήσεις ξεκινούν αυτόματα από το βιογραφικό σου — μπορείς πάντα να χρησιμοποιήσεις άλλο για μία συγκεκριμένη.",
  "profile.cvOnce": "Ανέβασέ το μία φορά και κάθε νέα αίτηση θα ξεκινά από αυτό.",
  "profile.forQuestions": "Χρησιμοποιούνται στη σύνταξη των ερωτήσεων συνέντευξης.",
  "profile.europass": "Το Europass τα ζητάει, οπότε είναι εδώ αν χρησιμοποιείς αυτή τη μορφή. Δεν στέλνονται ποτέ στο AI: δεν μπορούν να κάνουν μια απαίτηση καλυμμένη ή ακάλυπτη, και δεν έχουν καμία δουλειά να επηρεάζουν την αξιολόγησή σου.",
  "profile.professional": "Επαγγελματικά",
  "profile.contact": "Επικοινωνία",
  "profile.personal": "Προσωπικά",
  "progress.competencyNote": "Μέσος όρος ανά αίτηση, με τη μικρότερη μεταβολή πρώτη. Κάθε μία βαθμολογείται στα πέντε.",
  "letter.eachMarked": "Καθένα από αυτά σημειώθηκε ως Τεκμηριωμένο στην ανάλυση κενών, με μια πρόταση του βιογραφικού σου από πίσω.",
  "room.generate": "Δημιουργία ερωτήσεων",
  "room.generating": "Σύνταξη ερωτήσεων…",
  "room.allQuestions": "Και οι {n} ερωτήσεις",
  "room.answered": "Απαντήθηκε",
  "room.yourAnswer": "Η απάντησή σου",
  "room.score": "Βαθμολογία",
  "room.whyScore": "Γιατί αυτή η βαθμολογία",
  "room.whatWorked": "Τι πήγε καλά",
  "room.fixNext": "Διόρθωσε μετά",
  "room.strongerShape": "Μια δυνατότερη μορφή",
  "room.theyWouldAsk": "Θα ρωτούσαν",
  "room.technicalRubric": "Τεχνικό κριτήριο",
  "room.starRubric": "Κριτήριο STAR",
  "room.difficulty": "Δυσκολία {n}/5",
  "room.progressLabel": "Πρόοδος βαθμολόγησης",
  "cat.technical": "Τεχνική",
  "cat.behavioural": "Συμπεριφοράς",
  "crit.Correctness": "Ορθότητα",
  "crit.Depth": "Βάθος",
  "crit.Trade-offs": "Συμβιβασμοί",
  "crit.Communication": "Επικοινωνία",
  "crit.Relevance": "Συνάφεια",
  "crit.Situation": "Κατάσταση",
  "crit.Task": "Καθήκον",
  "crit.Action": "Ενέργεια",
  "crit.Result": "Αποτέλεσμα",
  "crit.Reflection": "Αναστοχασμός",
  "score.competencyNote": "Μέσος όρος από κάθε απάντηση που βαθμολόγησες, με τη χαμηλότερη πρώτη. Η εγκοπή σε κάθε μπάρα είναι στο 3.5 — εκεί περίπου που μια απάντηση παύει να σου κοστίζει τη συνέντευξη.",
};

const DICT: Record<Lang, Record<Key, string>> = { en, el };

interface Ctx {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: Key, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<Ctx>({
  lang: "en",
  setLang: () => {},
  t: (k) => en[k],
});

function initial(): Lang {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "en" || saved === "el") return saved;
  } catch {
    // private browsing, or storage blocked — fall through to the browser's
  }
  return navigator.language?.toLowerCase().startsWith("el") ? "el" : "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initial);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const setLang = (l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(KEY, l);
    } catch {
      // a remembered preference is a convenience, not a requirement
    }
  };

  const t = (key: Key, vars?: Record<string, string | number>) => {
    let s: string = DICT[lang][key] ?? en[key] ?? key;
    if (vars) {
      for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, String(v));
    }
    return s;
  };

  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>;
}

export function useT(): Ctx {
  return useContext(I18nContext);
}

/** Translate a rubric criterion name, falling back to the model's own wording.
 *
 *  Like the bands, these arrive in English because the prompt names the five
 *  dimensions literally, so they behave as an enum rather than as prose. */
export function useCriterion(): (name: string) => string {
  const { t } = useT();
  return (name: string) => {
    const key = `crit.${name}` as Key;
    return key in en ? t(key) : name;
  };
}

/** Translate a readiness band, falling back to whatever the model produced. */
export function useBand(): (band: string) => string {
  const { t } = useT();
  return (band: string) => {
    const key = `band.${band}` as Key;
    return key in en ? t(key) : band;
  };
}
