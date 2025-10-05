import "~style.css";
import React, { useState, useEffect } from 'react';
import { Settings, ChevronDown, ChevronUp } from 'lucide-react';

export default function Popup() {
  // CHANGED: Default to false instead of true
  const [isEnabled, setIsEnabled] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [autoScan, setAutoScan] = useState(true);
  const [option2, setOption2] = useState(false);
  const [option3, setOption3] = useState(false);

  return (
    <div className="w-full h-full min-w-[400px] bg-gradient-to-br from-blue-50 to-indigo-50 font-sans flex flex-col">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white p-6 flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* Logo - Animated Glass Jar with Word Tags */}
            <div className="w-12 h-12 bg-white rounded-xl flex items-center justify-center shadow-lg overflow-visible relative">
              <svg viewBox="0 0 40 40" fill="none" className="w-10 h-10">
                {/* Jar body - glass effect */}
                <defs>
                  <linearGradient id="glassGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style={{ stopColor: '#E0F2FE', stopOpacity: 0.6 }} />
                    <stop offset="100%" style={{ stopColor: '#BAE6FD', stopOpacity: 0.3 }} />
                  </linearGradient>
                </defs>
                
                {/* Jar lid (wider) */}
                <ellipse cx="20" cy="10" rx="8" ry="2" fill="#3B82F6"/>
                <rect x="12" y="9" width="16" height="2" fill="#2563EB"/>
                
                {/* Jar neck (narrow part) */}
                <path 
                  d="M 15 11 L 15 13 L 12 15 L 12 32 Q 12 34 14 34 L 26 34 Q 28 34 28 32 L 28 15 L 25 13 L 25 11 Z" 
                  fill="url(#glassGradient)" 
                  stroke="#3B82F6" 
                  strokeWidth="1.5"
                />
                
                {/* Glass shine effect */}
                <path 
                  d="M 14 16 L 14 30 Q 14 32 15 32" 
                  stroke="white" 
                  strokeWidth="1.5" 
                  strokeOpacity="0.6"
                  strokeLinecap="round"
                />
                
                {/* Word tags inside jar */}
                <g className="animate-pulse" style={{ animationDuration: '2s' }}>
                  <rect x="15" y="20" width="7" height="2.5" rx="1" fill="#3B82F6" opacity="0.8"/>
                  <rect x="16" y="25" width="6" height="2.5" rx="1" fill="#6366F1" opacity="0.7"/>
                  <rect x="14" y="28" width="5" height="2" rx="0.8" fill="#8B5CF6" opacity="0.6"/>
                </g>
                
                {/* Floating word tags (popping out) */}
                <g className="animate-bounce" style={{ animationDuration: '3s', animationDelay: '0s' }}>
                  <rect x="29" y="16" width="6" height="2.5" rx="1" fill="#3B82F6" opacity="0.9"/>
                </g>
                <g className="animate-bounce" style={{ animationDuration: '3s', animationDelay: '1s' }}>
                  <rect x="5" y="22" width="5" height="2.5" rx="1" fill="#6366F1" opacity="0.85"/>
                </g>
              </svg>
            </div>
            <h1 className="text-3xl font-bold tracking-wide" style={{ fontFamily: "'Georgia', 'Playfair Display', serif", letterSpacing: '0.02em' }}>
              MedJar
            </h1>
          </div>
          <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center backdrop-blur-sm">
            <Settings className="w-5 h-5" />
          </div>
        </div>
        <p className="text-blue-100 text-sm mt-2 ml-15">Medical Information Assistant</p>
      </div>

      {/* Main Content */}
      <div className="p-6 space-y-4 flex-1 overflow-auto">
        {/* Power Toggle */}
        <div className="bg-white rounded-xl shadow-sm p-4 border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-gray-800">Extension Status</h3>
              <p className="text-sm text-gray-500 mt-0.5">
                {isEnabled ? 'Active' : 'Inactive'}
              </p>
            </div>
            <button
              // onClick={() => setIsEnabled(!isEnabled)}
              onClick={() => {
                const newState = !isEnabled;
                setIsEnabled(newState);
                
                // Send message to all tabs
                chrome.tabs.query({}, (tabs) => {
                  tabs.forEach(tab => {
                    if (tab.id) {
                      chrome.tabs.sendMessage(tab.id, {
                        action: 'toggleScanning',
                        enabled: newState
                      }).catch(() => {});
                    }
                  });
                });
              }}
              className={`relative w-14 h-7 rounded-full transition-colors duration-300 ease-in-out focus:outline-none focus:ring-2 focus:ring-offset-2 ${
                isEnabled
                  ? 'bg-gradient-to-r from-blue-500 to-indigo-500 focus:ring-blue-400'
                  : 'bg-gray-300 focus:ring-gray-400'
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-6 h-6 bg-white rounded-full shadow-md transform transition-transform duration-300 ease-in-out ${
                  isEnabled ? 'translate-x-7' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </div>

        {/* Customization Section */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="w-full p-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <Settings className="w-5 h-5 text-blue-600" />
              <span className="font-semibold text-gray-800">Customization</span>
            </div>
            {showSettings ? (
              <ChevronUp className="w-5 h-5 text-gray-400" />
            ) : (
              <ChevronDown className="w-5 h-5 text-gray-400" />
            )}
          </button>

          {/* Settings Options */}
          {showSettings && (
            <div className="border-t border-gray-100 p-4 space-y-3 bg-gray-50">
              {/* Auto Scan */}
              <div className="flex items-center justify-between py-2">
                <div className="flex-1">
                  <label htmlFor="autoScan" className="font-medium text-gray-700 text-sm cursor-pointer">
                    Auto Scan
                  </label>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Automatically scan pages for medical terms
                  </p>
                </div>
                <button
                  id="autoScan"
                  onClick={() => setAutoScan(!autoScan)}
                  className={`relative w-11 h-6 rounded-full transition-colors duration-300 ease-in-out focus:outline-none focus:ring-2 focus:ring-offset-2 ml-3 flex-shrink-0 ${
                    autoScan
                      ? 'bg-blue-500 focus:ring-blue-400'
                      : 'bg-gray-300 focus:ring-gray-400'
                  }`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transform transition-transform duration-300 ease-in-out ${
                      autoScan ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>

              {/* Option 2 */}
              <div className="flex items-center justify-between py-2">
                <div className="flex-1">
                  <label htmlFor="option2" className="font-medium text-gray-700 text-sm cursor-pointer">
                    Option 2
                  </label>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Description for option 2
                  </p>
                </div>
                <button
                  id="option2"
                  onClick={() => setOption2(!option2)}
                  className={`relative w-11 h-6 rounded-full transition-colors duration-300 ease-in-out focus:outline-none focus:ring-2 focus:ring-offset-2 ml-3 flex-shrink-0 ${
                    option2
                      ? 'bg-blue-500 focus:ring-blue-400'
                      : 'bg-gray-300 focus:ring-gray-400'
                  }`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transform transition-transform duration-300 ease-in-out ${
                      option2 ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>

              {/* Option 3 */}
              <div className="flex items-center justify-between py-2">
                <div className="flex-1">
                  <label htmlFor="option3" className="font-medium text-gray-700 text-sm cursor-pointer">
                    Option 3
                  </label>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Description for option 3
                  </p>
                </div>
                <button
                  id="option3"
                  onClick={() => setOption3(!option3)}
                  className={`relative w-11 h-6 rounded-full transition-colors duration-300 ease-in-out focus:outline-none focus:ring-2 focus:ring-offset-2 ml-3 flex-shrink-0 ${
                    option3
                      ? 'bg-blue-500 focus:ring-blue-400'
                      : 'bg-gray-300 focus:ring-gray-400'
                  }`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transform transition-transform duration-300 ease-in-out ${
                      option3 ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* View Docs Button */}
        <a
          href="https://docs.example.com"
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full text-center py-2.5 px-4 bg-white border-2 border-blue-600 text-blue-600 rounded-lg font-medium hover:bg-blue-50 transition-colors"
        >
          View Docs
        </a>
      </div>
    </div>
  );
}