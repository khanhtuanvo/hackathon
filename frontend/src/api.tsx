// api.ts
const API = "http://localhost:8000";

export async function extractText(text: string) {
  const res = await fetch(`${API}/v1/extract_terms`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text })
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function extractUpload(file: File) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${API}/v1/extract_terms_upload`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// NEW: plain search for a term
export async function searchTerm(term: string, lang: "en" | "es" = "en") {
  const url = new URL(`${API}/v1/mp/search`);
  url.searchParams.set("term", term);
  url.searchParams.set("lang", lang);
  const res = await fetch(url.toString());
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<{ result: { title?: string; url?: string; summary?: string } | null }>;
}
