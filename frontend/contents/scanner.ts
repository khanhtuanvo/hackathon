import { Readability } from "@mozilla/readability";
// contents/scanner.ts

export const config = {
  matches: ["<all_urls>"],
  run_at: "document_end"
};

let isEnabled = false;

// in contents/scanner.ts

function highlightJargon(terms: any[], descriptions: string[]) {
  console.log("Attempting to highlight terms:", terms);

  if (!terms || terms.length === 0) {
    return; // Do nothing if there are no terms
  }

  // Helper to escape special characters for use in a RegExp
  const escapeRegex = (str: string) => {
    return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  };

  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => {
      // Don't search inside scripts, styles, or already highlighted spans
      if (node.parentElement.closest('script, style, .jargon-highlight')) {
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
  
  // Build a single, case-insensitive regex to find any of the terms
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

    // Use replace with a callback to build up our new nodes
    content.replace(allTermsRegex, (match, ...args) => {
      const offset = args[args.length - 2];
      
      // Add the text before the match
      if (offset > lastIndex) {
        fragment.appendChild(document.createTextNode(content.substring(lastIndex, offset)));
      }

      // Create and add the highlight span
      const span = document.createElement('span');
      span.className = 'jargon-highlight';
      span.textContent = match;
      span.title = descriptionMap.get(match.toLowerCase()) || "No description available.";
      fragment.appendChild(span);

      lastIndex = offset + match.length;
      return match; 
    });

    // Add any text remaining after the last match
    if (lastIndex < content.length) {
      fragment.appendChild(document.createTextNode(content.substring(lastIndex)));
    }
    
    // Replace the original text node with our fragment containing highlights
    parent.replaceChild(fragment, node);
  });
}

// --- Your original functions (they are good) ---

// in contents/scanner.ts

function getArticleContent(): string {
  /*
   * This function uses Mozilla's Readability library to find the main
   * content of the page, stripping out ads, nav bars, and other clutter.
   * It clones the document first so the original page is not modified.
  */
  const documentClone = document.cloneNode(true) as Document;
  const reader = new Readability(documentClone);
  const article = reader.parse();

  // The 'article' object contains the clean title, content, textContent, etc.
  // We return the clean text content.
  if (article && article.textContent) {
    return article.textContent.trim();
  }

  // Fallback to the simple method if Readability fails for any reason
  console.warn("Readability.js failed to parse the article, falling back to body.innerText");
  return document.body.innerText || "";
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
      console.log('✅ Content sent successfully');
      const data = await response.json();
      if (data.terms && data.descriptions) {
        highlightJargon(data.terms, data.descriptions);

      }
    } else {
      console.error('❌ Failed to send content:', await response.text());
    }
  } catch (error) {
    console.error('❌ Error:', error);
  }
}

async function scanPage() {
  if (isEnabled) {
    console.log('📄 Scanning page:', window.location.href);
    const content = getArticleContent();
    
    if (content.length > 100) {
      await sendToBackend(content);
    }
  }
}

chrome.runtime.onMessage.addListener((message) => {
  if (message.action === 'toggleScanning') {
    isEnabled = message.enabled;
    if (isEnabled) {
      console.log('🔄 Scanning enabled, scanning current page...');
      scanPage();
    } else {
      console.log('⏸️ Scanning disabled. Reload page to remove highlights.');
    }
  }
});