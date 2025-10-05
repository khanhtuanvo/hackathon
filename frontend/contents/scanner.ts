import { Readability } from "@mozilla/readability";

export const config = {
  matches: ["<all_urls>"],
  run_at: "document_end"
};

let isEnabled = false;

function getArticleContent(): string {
  const documentClone = document.cloneNode(true) as Document;
  
  // Remove unwanted elements before Readability parses
  const unwantedSelectors = [
    // Ads
    '[class*="ad-"]',
    '[id*="ad-"]',
    '[class*="advertisement"]',
    '.sponsored',
    '.promo',
    '[data-ad]',
    'iframe[src*="doubleclick"]',
    'iframe[src*="googlesyndication"]',
    '.ad',
    '.ads',
    
    // Navigation and UI
    'nav',
    'header',
    'footer',
    'aside',
    '[role="navigation"]',
    '[role="banner"]',
    '[role="contentinfo"]',
    '.sidebar',
    '.menu',
    
    // Legal/Terms
    '[class*="terms"]',
    '[class*="privacy"]',
    '[class*="legal"]',
    '[class*="disclaimer"]',
    '[class*="footer"]',
    '#footer',
    
    // Comments and social
    '[class*="comment"]',
    '[class*="social"]',
    '.share',
    '[class*="related"]',
    
    // Other noise
    'script',
    'style',
    'noscript'
  ];
  
  unwantedSelectors.forEach(selector => {
    documentClone.querySelectorAll(selector).forEach(el => el.remove());
  });
  
  const reader = new Readability(documentClone);
  const article = reader.parse();

  if (article && article.textContent) {
    let content = article.textContent.trim();
    
    // Filter out common legal/terms text patterns
    const unwantedPatterns = [
      /terms\s+(and|&)\s+conditions/gi,
      /privacy\s+policy/gi,
      /cookie\s+policy/gi,
      /all\s+rights\s+reserved/gi,
      /©.*?\d{4}/g,
      /please\s+confirm\s+any\s+data/gi,
      /do\s+not\s+provide\s+medical\s+advice/gi,
      /read\s+the\s+full\s+terms/gi
    ];
    
    unwantedPatterns.forEach(pattern => {
      content = content.replace(pattern, '');
    });
    
    return content.trim();
  }

  console.warn("Readability.js failed, falling back to body.innerText");
  return document.body.innerText || "";
}

function highlightJargon(terms: any[], descriptions: string[]) {
  console.log("Highlighting terms:", terms);

  if (!terms || terms.length === 0) return;

  const escapeRegex = (str: string) => {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  };

  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => {
      const parent = node.parentElement;
      // Skip ads, scripts, styles, and already highlighted text
      if (parent?.closest('script, style, .jargon-highlight, [class*="ad-"], [id*="ad-"], .advertisement, .sponsored, footer, [class*="footer"]')) {
        return NodeFilter.FILTER_REJECT;
      }
      return NodeFilter.FILTER_ACCEPT;
    }
  });

  const textNodes: Node[] = [];
  while (walker.nextNode()) {
    textNodes.push(walker.currentNode);
  }

  const sortedTerms = [...terms].sort((a, b) => b.term.length - a.term.length);
  const descriptionMap = new Map<string, string>();
  terms.forEach((t, i) => {
    descriptionMap.set(t.term.toLowerCase(), descriptions[i]);
  });
  
  const allTermsRegex = new RegExp(
    sortedTerms.map(t => `\\b(${escapeRegex(t.term)})\\b`).join('|'), 
    'gi'
  );

  textNodes.forEach(node => {
    const content = node.textContent;
    const parent = node.parentNode;
    if (!content || !parent || !allTermsRegex.test(content)) {
      return;
    }

    const fragment = document.createDocumentFragment();
    let lastIndex = 0;

    content.replace(allTermsRegex, (match, ...args) => {
      const offset = args[args.length - 2];
      
      if (offset > lastIndex) {
        fragment.appendChild(document.createTextNode(content.substring(lastIndex, offset)));
      }

      const span = document.createElement('span');
      span.className = 'jargon-highlight';
      span.textContent = match;
      span.title = descriptionMap.get(match.toLowerCase()) || "No description available.";
      fragment.appendChild(span);

      lastIndex = offset + match.length;
      return match; 
    });

    if (lastIndex < content.length) {
      fragment.appendChild(document.createTextNode(content.substring(lastIndex)));
    }
    
    parent.replaceChild(fragment, node);
  });
}

async function sendToBackend(content: string) {
  try {
    const backendUrl = 'http://127.0.0.1:8000/execute';
    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: content })
    });
    
    if (response.ok) {
      console.log('Content sent successfully');
      const data = await response.json();
      if (data.terms && data.descriptions) {
        highlightJargon(data.terms, data.descriptions);
      }
    } else {
      console.error('Failed to send content:', await response.text());
    }
  } catch (error) {
    console.error('Error:', error);
  }
}

async function scanPage() {
  if (isEnabled) {
    console.log('Scanning page:', window.location.href);
    const content = getArticleContent();
    console.log('Extracted content length:', content.length);
    await sendToBackend(content);
  }
}

chrome.runtime.onMessage.addListener((message) => {
  if (message.action === 'toggleScanning') {
    isEnabled = message.enabled;
    if (isEnabled) {
      console.log('Scanning enabled, scanning current page...');
      scanPage();
    } else {
      console.log('Scanning disabled. Reload page to remove highlights.');
    }
  }
});