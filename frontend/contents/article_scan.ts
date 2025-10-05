// contents/article.ts
export const config = { matches: ["<all_urls>"], run_at: "document_idle", all_frames: true }

const clean = (s: string) => (s || "").replace(/\s+/g, " ").trim()
const isVisible = (el: Element) => {
  const st = getComputedStyle(el as HTMLElement)
  if (st.display === "none" || st.visibility === "hidden" || +st.opacity === 0) return false
  const r = (el as HTMLElement).getBoundingClientRect()
  return r.width > 0 && r.height > 0
}

const AVOID = ["nav","header","footer","aside","[role='navigation']","[role='banner']","[role='contentinfo']",
               ".sidebar",".menu",".advert",".ad",".ads",".share",".social",".promo",".breadcrumbs",".subscribe"]
const ROOTS = ["article","main","[role='main']","[role='article']",".article",".post",".entry",".content",
               ".article-content",".post-content","#article","#content","[itemprop='articleBody']"]

const score = (el: Element) => {
  const text = clean((el as HTMLElement).innerText || "")
  if (text.length < 200) return 0
  const links = el.querySelectorAll("a")
  const linkLen = Array.from(links).reduce((s, a) => s + clean(a.textContent || "").length, 0)
  const linkDensity = linkLen ? linkLen / text.length : 0
  const paraCount = el.querySelectorAll("p, li").length
  return (Math.log10(text.length) * 10 + paraCount) * (1 - Math.min(linkDensity, 0.8))
}

function bestContainer(doc: Document): Element {
  const candidates = ROOTS.flatMap((sel) => Array.from(doc.querySelectorAll(sel))).filter(isVisible)
  if (!candidates.length) return doc.body || doc.documentElement
  return candidates.reduce((best, el) => (score(el) > score(best) ? el : best)) as Element
}

function extract(doc: Document) {
  const root = bestContainer(doc)
  AVOID.forEach((sel) => root.querySelectorAll(sel).forEach((n) => n.remove()))
  const blocks = Array.from(root.querySelectorAll("h1,h2,h3,p,li,blockquote,figure figcaption"))
    .filter(isVisible)
    .map((n) => ({ tag: n.tagName.toLowerCase(), text: clean(n.textContent || "") }))
    .filter((t) => t.text.length > 25)

  // dedupe consecutive
  const out: { tag: string; text: string }[] = []
  let last = ""
  for (const b of blocks) {
    if (b.text !== last) out.push(b)
    last = b.text
  }
  return out
}

function meta(doc: Document) {
  const g = (sel: string) => doc.querySelector(sel)?.getAttribute("content") || null
  const t = (sel: string) => clean(doc.querySelector(sel)?.textContent || "") || null
  return {
    url: doc.defaultView?.location.href || null,
    canonical: doc.querySelector("link[rel='canonical']")?.getAttribute("href") || null,
    title: g("meta[property='og:title']") || g("meta[name='twitter:title']") || doc.title || null,
    description: g("meta[name='description']") || g("meta[property='og:description']") || null,
    author: g("meta[name='author']") || t("[itemprop='author']") || t("[rel='author']") || null,
    published: g("meta[property='article:published_time']") || g("meta[itemprop='datePublished']") || null,
    lang: (doc.documentElement.getAttribute("lang") || null)
  }
}

function extractSameOriginIframes() {
  const res: any[] = []
  document.querySelectorAll("iframe").forEach((f) => {
    try {
      const d = (f as HTMLIFrameElement).contentDocument
      if (!d) return
      const pars = extract(d)
      if (pars.length) res.push({ url: d.location?.href || null, title: d.title || null, paragraphs: pars })
    } catch { /* cross-origin -> ignore */ }
  })
  return res
}

let LATEST = {
  meta: meta(document),
  paragraphs: extract(document),
  frame_extractions: extractSameOriginIframes()
}

const mo = new MutationObserver(() => {
  clearTimeout((window as any).__debounce)
  ;(window as any).__debounce = setTimeout(() => {
    LATEST = {
      meta: meta(document),
      paragraphs: extract(document),
      frame_extractions: extractSameOriginIframes()
    }
  }, 200)
})
mo.observe(document.documentElement, { childList: true, subtree: true })

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === "GET_FULLTEXT") {
    sendResponse(LATEST)
    return true
  }
})