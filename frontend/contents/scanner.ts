// contents/scanner.ts

export const config = {
  matches: ["<all_urls>"],
  run_at: "document_end"
}

// CHANGED: Move isEnabled to top-level scope (outside functions)
let isEnabled = false;

// Get page content safely
function getPageContent(): string {
  if (!document.body) return ""
  return document.body.innerText || ""
}

// Get article-specific content (tries common article containers first)
function getArticleContent(): string {
  const selectors = [
    'article',
    'main',
    '[role="main"]',
    '.article-content',
    '.post-content',
    '#content',
    '.entry-content'
  ]
  
  for (const selector of selectors) {
    const element = document.querySelector(selector)
    if (element && element.textContent) {
      return element.textContent.trim()
    }
  }
  
  return getPageContent()
}

// Send content to your backend
async function sendToBackend(content: string) {
  try {
    const response = await fetch('YOUR_BACKEND_URL/api/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: window.location.href,
        title: document.title,
        content: content,
        timestamp: new Date().toISOString()
      })
    })
    
    if (response.ok) {
      console.log('✅ Content sent successfully')
    } else {
      console.error('❌ Failed to send content')
    }
  } catch (error) {
    console.error('❌ Error:', error)
  }
}

// CHANGED: Simplified - just scans if enabled
async function scanPage() {
  if (isEnabled) {
    console.log('📄 Scanning page:', window.location.href)
    const content = getArticleContent()
    
    if (content.length > 100) {
      await sendToBackend(content)
    }
  }
}

// CHANGED: Listen for toggle messages from popup (moved outside scanPage)
chrome.runtime.onMessage.addListener((message) => {
  if (message.action === 'toggleScanning') {
    isEnabled = message.enabled;
    
    if (isEnabled) {
      console.log('🔄 Scanning enabled, scanning current page...');
      scanPage();
    } else {
      console.log('⏸️ Scanning disabled');
    }
  }
});