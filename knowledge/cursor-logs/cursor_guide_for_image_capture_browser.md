# Guide for image capture browser extension
_Exported on 11/9/2025 at 22:51:16 PST from Cursor (2.0.69)_

---

**User**

@imagebrowserextensiondev i want the program to be able to "capture" all images on a tab you're on, and then send them tothe imagecapture collection page. from there you can organize/prune images to your liking as well as create new folders. eventually there will be ai assisted functionality as well. can you guide the browser extension to do this ?

---

**Cursor**

1. Should the capture trigger run automatically when the user opens the collection page, or only when they click a button in the extension UI?  
2. Where do you want the captured images stored for pruning—locally in the extension (e.g. IndexedDB) or sent to a backend API?

---

**User**

this is what confuses me. the browser extension already has the beginnings of a "collection" page. but it's only available in the dropdown menu. once there, in the "main" section is a "view collection" button. this is where you brought to the collection page, see the screenshot for what it looks like currently. 



right clicking and utilizing the context menu allows you to "capture" an image once it has been selected via the "Capture Selected Images" context menu entry. this send it to the "Collection Page"



can you determine what the collection page is, a local browser based cache or otherwise?

---

**Cursor**

The collection is entirely local to the extension. In `background.js`, captured images are kept in a `globalState` object and written to `chrome.storage.local` under the `capturedImages` key, alongside the rest of the extension state:

```42:46:imagebrowserextensiondev/browserextension/browser-extension/background.js
    chrome.storage.local.set({
        globalState: globalState,
        capturedImages: globalState.capturedImages
    });
```

Whenever an image is captured (via the context-menu action), the content script notifies the background script, which pushes the image metadata into that array and persists it locally. When you hit “View Collection” in the popup, the popup requests those images (`getCapturedImages`), builds an HTML page on the fly, and opens it in a new tab—no remote API or separate cache layer is involved.

So the “collection page” you’re seeing is just a dynamically generated HTML view of whatever entries are currently saved in `chrome.storage.local`. Clearing the collection empties that local array; there’s no server-side storage yet.

```javascript
    chrome.storage.local.set({
        globalState: globalState,
        capturedImages: globalState.capturedImages
    });
```

---

**User**

can you add a "View Collection" button in the sidebar and overlay menus?

Implement the plan as specified, it is attached for your reference. Do NOT edit the plan file itself.

To-do's from the plan have already been created. Do not create them again. Mark them as in_progress as you work, starting with the first one. Don't stop until you have completed all the to-dos.

---

**Cursor**

```javascript
// Background script for ImageCapture extension
let globalState = {
  overlayVisible: false,
  floatingMenuPosition: {
    x: 20,
    y: 20,
    width: 200,
    height: 'auto'
  },
  settings: {
    hoverSelectDelay: 500,
    hoverDeselectDelay: 300,
    autoCaptureHover: false, // Disabled hover selection
    showNotifications: true,
    showSelectionIndicator: true,
    telegramEnabled: true,
    showFloatingMenu: true,
    minImageWidth: 100,
    preferredFileTypes: ['jpg', 'jpeg', 'png'],
    overlayHoverDelay: 1000,
    overlayButtons: ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'download', 'quickToolbar'],
    overlayDraggable: true,
    quickToolbarMode: false,
    useOverlayIcons: false // New setting for toggleable selection indicators
  },
  capturedImages: [],
  selectedImages: []
};

// Initialize state from storage
chrome.storage.local.get(['globalState', 'capturedImages'], (result) => {
  if (result.globalState) {
    globalState = { ...globalState, ...result.globalState };
  }
  if (result.capturedImages) {
    globalState.capturedImages = result.capturedImages;
  }
  saveGlobalState();
});

// Save global state to storage
function saveGlobalState() {
  chrome.storage.local.set({
    globalState: globalState,
    capturedImages: globalState.capturedImages
  });
}

// Handle messages from content scripts and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'getSettings':
      sendResponse({ settings: globalState.settings });
      break;
      
    case 'setSettings':
      globalState.settings = { ...globalState.settings, ...request.settings };
      saveGlobalState();
      // Broadcast settings update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateSettings', settings: globalState.settings }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'getGlobalState':
      sendResponse({ globalState: globalState });
      break;
      
    case 'setOverlayVisible':
      globalState.overlayVisible = request.visible;
      saveGlobalState();
      // Broadcast overlay visibility update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateOverlayVisibility', visible: request.visible }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'setFloatingMenuPosition':
      globalState.floatingMenuPosition = { ...globalState.floatingMenuPosition, ...request.position };
      saveGlobalState();
      // Broadcast position update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateFloatingMenuPosition', position: globalState.floatingMenuPosition }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'updateSettings':
      globalState.settings = { ...globalState.settings, ...request.settings };
      saveGlobalState();
      // Broadcast settings update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateSettings', settings: globalState.settings }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'captureImage':
      const imageData = {
        url: request.url,
        timestamp: Date.now(),
        domain: new URL(request.url).hostname,
        title: request.title || 'Captured Image'
      };
      
      if (!globalState.capturedImages.find(img => img.url === request.url)) {
        globalState.capturedImages.push(imageData);
        saveGlobalState();
        
        // Broadcast new image to all tabs
        chrome.tabs.query({}, (tabs) => {
          tabs.forEach(tab => {
            chrome.tabs.sendMessage(tab.id, { action: 'newImageCaptured', image: imageData }).catch(() => {});
          });
        });
      }
      sendResponse({ success: true });
      break;
      
    case 'getCapturedImages':
      sendResponse({ images: globalState.capturedImages });
      break;
      
    case 'clearCapturedImages':
      globalState.capturedImages = [];
      saveGlobalState();
      // Broadcast clear to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'imagesCleared' }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'downloadImages':
      console.log('Download request received:', request);
      const imagesToDownload = request.images || globalState.capturedImages;
      if (imagesToDownload.length === 0) {
        console.log('No images to download');
        sendResponse({ success: false, error: 'No images to download' });
        return;
      }
      
      console.log('Images to download:', imagesToDownload);
      
      // Download each image file individually
      let downloadCount = 0;
      const totalImages = imagesToDownload.length;
      
      imagesToDownload.forEach((img, index) => {
        const imageUrl = img.url || img;
        const filename = `image_${Date.now()}_${index + 1}.jpg`;
        
        console.log(`Downloading image ${index + 1}/${totalImages}:`, imageUrl);
        
        // Download the actual image file
        chrome.downloads.download({
          url: imageUrl,
          filename: filename,
          saveAs: false // Don't prompt for each file, use browser's default download folder
        }, (downloadId) => {
          downloadCount++;
          console.log(`Download ${index + 1} completed, downloadId:`, downloadId);
          
          // Check if all downloads are complete
          if (downloadCount === totalImages) {
            console.log('All downloads completed');
            sendResponse({ success: true, downloaded: downloadCount });
          }
        });
      });
      
      return true; // Keep message channel open for async response
      break;
      
    case 'sendToTelegram':
      const imagesToSend = request.images || globalState.capturedImages;
      if (imagesToSend.length === 0) {
        sendResponse({ success: false, error: 'No images to send' });
        return;
      }
      
      const imageUrls = imagesToSend.map(img => img.url);
      
      fetch('http://localhost:5000/send_multiple_telegram', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({image_urls: imageUrls})
      })
      .then(response => response.json())
      .then(data => {
        sendResponse({ success: data.success, data: data });
      })
      .catch(error => {
        sendResponse({ success: false, error: error.message });
      });
      
      return true; // Keep message channel open for async response
      
    case 'viewCollection':
      if (globalState.capturedImages.length === 0) {
        sendResponse({ success: false, error: 'No images in collection' });
        break;
      }
      
      try {
        const collectionHtml = generateCollectionHTML(globalState.capturedImages);
        const blob = new Blob([collectionHtml], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        
        chrome.tabs.create({ url }, (tab) => {
          if (chrome.runtime.lastError) {
            sendResponse({ success: false, error: chrome.runtime.lastError.message });
            URL.revokeObjectURL(url);
            return;
          }
          
          sendResponse({ success: true, tabId: tab && tab.id });
          
          // Revoke the object URL after the tab has loaded
          setTimeout(() => URL.revokeObjectURL(url), 60_000);
        });
        
        return true; // Keep message channel open for async response
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;
      
    default:
      sendResponse({ success: false, error: 'Unknown action' });
  }
});

// Handle tab updates to sync state
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url && tab.url.startsWith('http')) {
    // Send current state to new tab
    setTimeout(() => {
      chrome.tabs.sendMessage(tabId, { 
        action: 'initializeState', 
        globalState: globalState 
      }).catch(() => {});
    }, 1000);
  }
});

// Handle extension installation/update
chrome.runtime.onInstalled.addListener(() => {
  saveGlobalState();
  
  // Create context menu items
  chrome.contextMenus.create({
    id: 'imagecapture-main',
    title: '🖼️ ImageCapture',
    contexts: ['all']
  });
  
  chrome.contextMenus.create({
    id: 'toggle-sidebar',
    title: '📱 Toggle Sidebar',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'toggle-overlay-menu',
    title: '👁️ Toggle Overlay Menu',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'toggle-selection-mode',
    title: '🎯 Toggle Selection Mode',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'select-all-images',
    title: '☑️ Select All Images',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'capture-selected-images',
    title: '📸 Capture Selected Images',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'download-selected-images',
    title: '📥 Download Selected Images',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'clear-collection',
    title: '🗑️ Clear Collection',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
});

function generateCollectionHTML(images) {
  const totalSources = (() => {
    try {
      return new Set(images.map(img => new URL(img.url).hostname)).size;
    } catch (error) {
      console.warn('Failed to compute image hostnames:', error);
      return 1;
    }
  })();
  
  const statsStorage = formatBytes(images.length * 100);
  
  const cards = images.map((img, index) => {
    let hostname = '';
    let filename = 'Image';
    try {
      const url = new URL(img.url);
      hostname = url.hostname;
      filename = url.pathname.split('/').pop() || 'Image';
    } catch (_) {}
    
    const capturedDate = new Date(img.timestamp).toLocaleDateString();
    
    return `
                <div class="image-item" data-index="${index}" onclick="toggleImageSelection(this)">
                    <img src="${img.url}" alt="Captured image ${index + 1}" onerror="this.style.display='none'">
                    <div class="image-info">
                        <div class="image-title">${filename}</div>
                        <div class="image-meta">
                            <span>${hostname}</span>
                            <span>${capturedDate}</span>
                        </div>
                    </div>
                </div>
    `;
  }).join('');
  
  return `
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ImageCapture Collection</title>
        <style>
${generateCollectionStyles()}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🖼️ ImageCapture Collection</h1>
            <p>${images.length} images captured</p>
        </div>
        
        <div class="stats">
            <div class="stat-item">
                <span class="stat-number">${images.length}</span>
                <span class="stat-label">Total Images</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">${totalSources}</span>
                <span class="stat-label">Sources</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">${statsStorage}</span>
                <span class="stat-label">Storage Used</span>
            </div>
        </div>
        
        <div class="controls">
            <button class="btn primary" onclick="downloadSelected()">📥 Download Selected</button>
            <button class="btn telegram" onclick="sendToTelegram()">📤 Send to Telegram</button>
            <button class="btn" onclick="toggleSelectionMode()">🎯 Toggle Selection Mode</button>
            <button class="btn" onclick="selectAll()">☑️ Select All</button>
            <button class="btn danger" onclick="clearCollection()">🗑️ Clear Collection</button>
        </div>
        
        <div class="image-grid" id="imageGrid">
${cards}
        </div>
        
        <div class="selection-mode" id="selectionMode">
            <div class="selection-controls">
                <button class="btn" onclick="selectAll()">☑️ Select All</button>
                <button class="btn" onclick="deselectAll()">☐ Deselect All</button>
                <button class="btn danger" onclick="toggleSelectionMode()">✕ Exit Selection</button>
            </div>
            <div class="selection-stats">
                Selected: <span id="selectedCount">0</span> / ${images.length}
            </div>
        </div>
        
        <script>
${generateCollectionScript(images.length)}
        </script>
    </body>
    </html>
  `;
}

function generateCollectionStyles() {
  return `            body {
                margin: 0;
                padding: 20px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                min-height: 100vh;
            }
            
            .header {
                text-align: center;
                margin-bottom: 30px;
            }
            
            .header h1 {
                margin: 0;
                font-size: 32px;
                font-weight: 600;
                margin-bottom: 10px;
            }
            
            .stats {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 30px;
                backdrop-filter: blur(10px);
                display: flex;
                justify-content: space-around;
                flex-wrap: wrap;
                gap: 20px;
            }
            
            .stat-item {
                text-align: center;
            }
            
            .stat-number {
                font-size: 24px;
                font-weight: bold;
                display: block;
            }
            
            .stat-label {
                font-size: 14px;
                opacity: 0.8;
            }
            
            .controls {
                display: flex;
                gap: 12px;
                margin-bottom: 30px;
                flex-wrap: wrap;
                justify-content: center;
            }
            
            .btn {
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
                padding: 12px 20px;
                color: white;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s ease;
                text-decoration: none;
                display: inline-block;
            }
            
            .btn:hover {
                background: rgba(255, 255, 255, 0.3);
                transform: translateY(-2px);
            }
            
            .btn.primary {
                background: #4CAF50;
                border-color: #4CAF50;
            }
            
            .btn.primary:hover {
                background: #45a049;
            }
            
            .btn.danger {
                background: #f44336;
                border-color: #f44336;
            }
            
            .btn.danger:hover {
                background: #da190b;
            }
            
            .btn.telegram {
                background: #0088cc;
                border-color: #0088cc;
            }
            
            .btn.telegram:hover {
                background: #006699;
            }
            
            .image-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            
            .image-item {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                overflow: hidden;
                backdrop-filter: blur(10px);
                border: 3px solid transparent;
                background-clip: padding-box;
                position: relative;
                transition: all 0.3s ease;
                cursor: pointer;
            }
            
            .image-item::before {
                content: '';
                position: absolute;
                top: -3px;
                left: -3px;
                right: -3px;
                bottom: -3px;
                padding: 3px;
                background: linear-gradient(135deg, rgba(255, 255, 255, 0.3), rgba(255, 255, 255, 0.1));
                mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
                mask-composite: exclude;
                border-radius: 12px;
                opacity: 0.75;
                z-index: -1;
            }
            
            .image-item.selected::before {
                background: linear-gradient(135deg, #4CAF50, #45a049);
                opacity: 1;
            }
            
            .image-item:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
            }
            
            .image-item img {
                width: 100%;
                height: 200px;
                object-fit: cover;
                display: block;
            }
            
            .image-info {
                padding: 15px;
            }
            
            .image-title {
                font-size: 14px;
                font-weight: 600;
                margin-bottom: 8px;
                word-break: break-all;
            }
            
            .image-meta {
                font-size: 12px;
                opacity: 0.8;
                display: flex;
                justify-content: space-between;
            }
            
            .selection-mode {
                position: fixed;
                top: 20px;
                right: 20px;
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 15px;
                border-radius: 8px;
                backdrop-filter: blur(10px);
                z-index: 1000;
                display: none;
            }
            
            .selection-mode.active {
                display: block;
            }
            
            .selection-controls {
                display: flex;
                gap: 10px;
                margin-bottom: 10px;
            }
            
            .selection-stats {
                font-size: 12px;
                opacity: 0.8;
            }
            
            @media (max-width: 768px) {
                .image-grid {
                    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                    gap: 15px;
                }
                
                .controls {
                    flex-direction: column;
                    align-items: center;
                }
                
                .btn {
                    width: 100%;
                    max-width: 300px;
                }
            }`;
}

function generateCollectionScript(totalImages) {
  return `            const images = ${JSON.stringify(globalState.capturedImages)};
            let selectionMode = false;
            let selectedImages = new Set();
            
            function toggleSelectionMode() {
                selectionMode = !selectionMode;
                const modeDiv = document.getElementById('selectionMode');
                const toggleBtn = document.querySelector('button[onclick="toggleSelectionMode()"]');
                
                if (selectionMode) {
                    modeDiv.classList.add('active');
                    toggleBtn.textContent = '🎯 Exit Selection Mode';
                    toggleBtn.style.background = '#f44336';
                    document.body.style.cursor = 'crosshair';
                } else {
                    modeDiv.classList.remove('active');
                    toggleBtn.textContent = '🎯 Toggle Selection Mode';
                    toggleBtn.style.background = 'rgba(255, 255, 255, 0.2)';
                    document.body.style.cursor = 'default';
                    selectedImages.clear();
                    updateSelectionDisplay();
                    document.querySelectorAll('.image-item').forEach(item => item.classList.remove('selected'));
                }
            }
            
            function toggleImageSelection(element) {
                if (!selectionMode) return;
                
                const index = element.dataset.index;
                if (selectedImages.has(index)) {
                    selectedImages.delete(index);
                    element.classList.remove('selected');
                } else {
                    selectedImages.add(index);
                    element.classList.add('selected');
                }
                updateSelectionDisplay();
            }
            
            function selectAll() {
                if (!selectionMode) {
                    toggleSelectionMode();
                }
                selectedImages.clear();
                document.querySelectorAll('.image-item').forEach((item, index) => {
                    selectedImages.add(index.toString());
                    item.classList.add('selected');
                });
                updateSelectionDisplay();
            }
            
            function deselectAll() {
                selectedImages.clear();
                document.querySelectorAll('.image-item').forEach(item => {
                    item.classList.remove('selected');
                });
                updateSelectionDisplay();
            }
            
            function updateSelectionDisplay() {
                const counter = document.getElementById('selectedCount');
                if (counter) {
                    counter.textContent = selectedImages.size;
                }
            }
            
            function downloadSelected() {
                const imagesToDownload = selectionMode && selectedImages.size > 0 
                    ? Array.from(selectedImages).map(index => images[index])
                    : images;
                
                const urls = imagesToDownload.map(img => img.url).join('\\n');
                const blob = new Blob([urls], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                
                const a = document.createElement('a');
                a.href = url;
                a.download = 'captured_images.txt';
                a.click();
                
                setTimeout(() => URL.revokeObjectURL(url), 0);
                
                alert(\`\${imagesToDownload.length} image URLs downloaded!\`);
            }
            
            function sendToTelegram() {
                const imagesToSend = selectionMode && selectedImages.size > 0 
                    ? Array.from(selectedImages).map(index => images[index])
                    : images;
                
                const imageUrls = imagesToSend.map(img => img.url);
                
                fetch('http://localhost:5000/send_multiple_telegram', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({image_urls: imageUrls})
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert(\`✅ Successfully sent \${data.successful}/\${data.total_images} images to Telegram!\`);
                    } else {
                        alert(\`❌ Failed to send images: \${data.error}\`);
                    }
                })
                .catch(error => {
                    alert(\`❌ Error sending to Telegram: \${error.message}\`);
                });
            }
            
            function clearCollection() {
                if (confirm('Are you sure you want to clear all captured images?')) {
                    chrome.runtime.sendMessage({ action: 'clearCapturedImages' }, (response) => {
                        if (response && response.success) {
                            alert('Collection cleared!');
                            location.reload();
                        } else {
                            alert('Failed to clear collection');
                        }
                    });
                }
            }
            
            document.addEventListener('keydown', (e) => {
                if (e.target.tagName === 'INPUT') return;
                
                switch (e.key.toLowerCase()) {
                    case 's':
                        if (!e.ctrlKey && !e.metaKey) {
                            e.preventDefault();
                            toggleSelectionMode();
                        }
                        break;
                    case 'escape':
                        if (selectionMode) {
                            toggleSelectionMode();
                        }
                        break;
                }
            });
        `;
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!tab || !tab.url || !tab.url.startsWith('http')) return;
  
  switch (info.menuItemId) {
    case 'toggle-sidebar':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleSidebar' }).catch(() => {});
      break;
      
    case 'toggle-overlay-menu':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleOverlayMenu' }).catch(() => {});
      break;
      
    case 'toggle-selection-mode':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleSelectionMode' }).catch(() => {});
      break;
      
    case 'select-all-images':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleSelectAll' }).catch(() => {});
      break;
      
    case 'capture-selected-images':
      chrome.tabs.sendMessage(tab.id, { action: 'captureSelectedImages' }).catch(() => {});
      break;
      
    case 'download-selected-images':
      chrome.tabs.sendMessage(tab.id, { action: 'downloadSelectedImages' }).catch(() => {});
      break;
      
    case 'clear-collection':
      chrome.tabs.sendMessage(tab.id, { action: 'clearCapturedImages' }).catch(() => {});
      break;
  }
}); 
```

```javascript
// Popup script for ImageCapture extension
document.addEventListener('DOMContentLoaded', function() {
  // Tab switching
  const tabs = document.querySelectorAll('.tab');
  const tabContents = document.querySelectorAll('.tab-content');
  
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.getAttribute('data-tab');
      
      // Update active tab
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      
      // Show target content
      tabContents.forEach(content => {
        if (content.id === `${target}-tab`) {
          content.classList.add('active');
        } else {
          content.classList.remove('active');
        }
      });
    });
  });
  
  // Load hotkeys
  loadHotkeys();
  
  // Load settings
  loadSettings();
  
  // Load collection stats
  loadCollectionStats();
  
  // Add event listeners for save buttons
  document.getElementById('saveHotkeys').addEventListener('click', saveHotkeys);
  document.getElementById('saveSettings').addEventListener('click', saveSettings);
  
  // Event listeners
  document.getElementById('toggleSelection').addEventListener('click', () => {
    const button = document.getElementById('toggleSelection');
    const currentText = button.textContent;
    const isCurrentlyOn = currentText.includes('ON');
    
    // Update button text immediately for better UX
    button.textContent = isCurrentlyOn ? '🎯 Selection Mode: OFF' : '🎯 Selection Mode: ON';
    button.style.background = isCurrentlyOn ? '#ff9800' : '#4CAF50';
    
    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
      chrome.tabs.sendMessage(tabs[0].id, {action: 'toggleSelectionMode'});
    });
  });
  
  document.getElementById('toggleSelectAll').addEventListener('click', () => {
    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
      chrome.tabs.sendMessage(tabs[0].id, {action: 'toggleSelectAll'});
    });
  });
  
  document.getElementById('toggleOverlayMenu').addEventListener('click', () => {
    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
      chrome.tabs.sendMessage(tabs[0].id, {action: 'toggleOverlayMenu'});
    });
  });
  
  document.getElementById('downloadAll').addEventListener('click', () => {
    chrome.runtime.sendMessage({action: 'downloadImages'}, (response) => {
      if (response && response.success) {
        alert('Images downloaded successfully!');
      } else {
        alert('No images to download or download failed!');
      }
    });
  });
  
  document.getElementById('clearCollection').addEventListener('click', () => {
    if (confirm('Are you sure you want to clear all captured images?')) {
      chrome.runtime.sendMessage({action: 'clearCapturedImages'}, (response) => {
        if (response && response.success) {
          alert('Collection cleared!');
          loadCollectionStats();
        }
      });
    }
  });
  
  document.getElementById('toggleSidebar').addEventListener('click', () => {
    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
      chrome.tabs.sendMessage(tabs[0].id, {action: 'toggleSidebar'});
    });
  });
  
  document.getElementById('viewCollection').addEventListener('click', () => {
    chrome.runtime.sendMessage({action: 'viewCollection'}, (response) => {
      if (!response || !response.success) {
        alert(response && response.error ? response.error : 'Unable to open collection');
      }
    });
  });
  
  // Send to Telegram button
  document.getElementById('sendToTelegram').addEventListener('click', () => {
    // Show processing indicator
    const btn = document.getElementById('sendToTelegram');
    const originalText = btn.textContent;
    btn.textContent = '📤 Sending...';
    btn.disabled = true;
    
    // Send to backend
    chrome.runtime.sendMessage({action: 'sendToTelegram'}, (response) => {
      if (response && response.success) {
        alert(`✅ Successfully sent ${response.data.successful}/${response.data.total_images} images to Telegram!`);
      } else {
        alert(`❌ Failed to send images: ${response.error || 'Unknown error'}`);
      }
      
      btn.textContent = originalText;
      btn.disabled = false;
    });
  });
});

// Load hotkeys from storage
function loadHotkeys() {
  chrome.storage.local.get(['hotkeys'], (result) => {
    const hotkeys = result.hotkeys || {
      toggleSelection: 'S',
      captureAll: 'I',
      quickCapture: 'Q',
      downloadSelected: 'D',
      toggleSidebar: 'B',
      mouse3Action: 'quickCapture'
    };
    
    document.getElementById('toggleSelectionKey').value = hotkeys.toggleSelection || 'S';
    document.getElementById('captureAllKey').value = hotkeys.captureAll || 'I';
    document.getElementById('quickCaptureKey').value = hotkeys.quickCapture || 'Q';
    document.getElementById('downloadSelectedKey').value = hotkeys.downloadSelected || 'D';
    document.getElementById('toggleSidebarKey').value = hotkeys.toggleSidebar || 'B';
    document.getElementById('mouse3Action').value = hotkeys.mouse3Action || 'quickCapture';
  });
}

// Load settings from storage
function loadSettings() {
  chrome.runtime.sendMessage({action: 'getGlobalState'}, (response) => {
    if (response && response.globalState) {
      const globalState = response.globalState;
      const settings = globalState.settings || {};
      
      // Load basic settings
      document.getElementById('hoverSelectDelay').value = settings.hoverSelectDelay || 500;
      document.getElementById('hoverDeselectDelay').value = settings.hoverDeselectDelay || 300;
      document.getElementById('autoCaptureHover').checked = settings.autoCaptureHover !== false;
      document.getElementById('showNotifications').checked = settings.showNotifications !== false;
      document.getElementById('showSelectionIndicator').checked = settings.showSelectionIndicator !== false;
      document.getElementById('telegramEnabled').checked = settings.telegramEnabled !== false;
      document.getElementById('showFloatingMenu').checked = settings.showFloatingMenu !== false;
      document.getElementById('minImageWidth').value = settings.minImageWidth || 100;
      document.getElementById('overlayHoverDelay').value = settings.overlayHoverDelay || 1000;
      document.getElementById('overlayDraggable').checked = settings.overlayDraggable !== false;
      document.getElementById('quickToolbarMode').checked = settings.quickToolbarMode || false;
      document.getElementById('useOverlayIcons').checked = settings.useOverlayIcons || false;
      
      // Load overlay buttons
      const overlayButtons = settings.overlayButtons || ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'download', 'quickToolbar'];
      document.getElementById('btn-overlay').checked = overlayButtons.includes('overlay');
      document.getElementById('btn-selection').checked = overlayButtons.includes('selection');
      document.getElementById('btn-selectAll').checked = overlayButtons.includes('selectAll');
      document.getElementById('btn-sidebar').checked = overlayButtons.includes('sidebar');
      document.getElementById('btn-isolation').checked = overlayButtons.includes('isolation');
      document.getElementById('btn-capture').checked = overlayButtons.includes('capture');
      document.getElementById('btn-download').checked = overlayButtons.includes('download');
      document.getElementById('btn-quickToolbar').checked = overlayButtons.includes('quickToolbar');
    }
  });
}

// Save hotkeys to storage
function saveHotkeys() {
  const hotkeys = {
    toggleSelection: document.getElementById('toggleSelectionKey').value.toUpperCase(),
    captureAll: document.getElementById('captureAllKey').value.toUpperCase(),
    quickCapture: document.getElementById('quickCaptureKey').value.toUpperCase(),
    downloadSelected: document.getElementById('downloadSelectedKey').value.toUpperCase(),
    toggleSidebar: document.getElementById('toggleSidebarKey').value.toUpperCase(),
    mouse3Action: document.getElementById('mouse3Action').value
  };
  
  chrome.storage.local.set({hotkeys: hotkeys}, () => {
    alert('Hotkeys saved successfully!');
  });
}

// Save settings to storage
function saveSettings() {
  // Get overlay buttons configuration
  const overlayButtons = [];
  const buttonTypes = ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'download', 'quickToolbar'];
  buttonTypes.forEach(buttonType => {
    const checkbox = document.getElementById(`btn-${buttonType}`);
    if (checkbox && checkbox.checked) {
      overlayButtons.push(buttonType);
    }
  });
  
  const settings = {
    hoverSelectDelay: parseInt(document.getElementById('hoverSelectDelay').value),
    hoverDeselectDelay: parseInt(document.getElementById('hoverDeselectDelay').value),
    autoCaptureHover: document.getElementById('autoCaptureHover').checked,
    showNotifications: document.getElementById('showNotifications').checked,
    showSelectionIndicator: document.getElementById('showSelectionIndicator').checked,
    telegramEnabled: document.getElementById('telegramEnabled').checked,
    showFloatingMenu: document.getElementById('showFloatingMenu').checked,
    overlayHoverDelay: parseInt(document.getElementById('overlayHoverDelay').value),
    overlayDraggable: document.getElementById('overlayDraggable').checked,
    minImageWidth: parseInt(document.getElementById('minImageWidth').value),
    preferredFileTypes: Array.from(document.getElementById('preferredFileTypes').selectedOptions).map(option => option.value),
    overlayButtons: overlayButtons,
    quickToolbarMode: document.getElementById('quickToolbarMode').checked,
    useOverlayIcons: document.getElementById('useOverlayIcons').checked
  };
  
  chrome.runtime.sendMessage({action: 'setSettings', settings: settings}, (response) => {
    if (response && response.success) {
      alert('Settings saved successfully!');
      
      // Update content script settings
      chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
        chrome.tabs.sendMessage(tabs[0].id, {action: 'updateSettings', settings: settings});
      });
    }
  });
}

// Load collection statistics
function loadCollectionStats() {
  chrome.runtime.sendMessage({action: 'getCapturedImages'}, (response) => {
    const images = response.images || [];
    const capturedCount = document.getElementById('capturedCount');
    const storageUsed = document.getElementById('storageUsed');
    const lastCapture = document.getElementById('lastCapture');
    
    capturedCount.textContent = images.length;
    
    // Calculate storage size (rough estimate)
    const storageSize = images.length * 100; // Assume 100 bytes per image entry
    storageUsed.textContent = formatBytes(storageSize);
    
    if (images.length > 0) {
      const lastImage = images[images.length - 1];
      const date = new Date(lastImage.timestamp);
      lastCapture.textContent = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    } else {
      lastCapture.textContent = 'Never';
    }
  });
}

// Format bytes to human readable format
function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

```

```javascript
// Background script for ImageCapture extension
let globalState = {
  overlayVisible: false,
  floatingMenuPosition: {
    x: 20,
    y: 20,
    width: 200,
    height: 'auto'
  },
  settings: {
    hoverSelectDelay: 500,
    hoverDeselectDelay: 300,
    autoCaptureHover: false, // Disabled hover selection
    showNotifications: true,
    showSelectionIndicator: true,
    telegramEnabled: true,
    showFloatingMenu: true,
    minImageWidth: 100,
    preferredFileTypes: ['jpg', 'jpeg', 'png'],
    overlayHoverDelay: 1000,
    overlayButtons: ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'],
    overlayDraggable: true,
    quickToolbarMode: false,
    useOverlayIcons: false // New setting for toggleable selection indicators
  },
  capturedImages: [],
  selectedImages: []
};

// Initialize state from storage
chrome.storage.local.get(['globalState', 'capturedImages'], (result) => {
  if (result.globalState) {
    globalState = { ...globalState, ...result.globalState };
  }
  if (result.capturedImages) {
    globalState.capturedImages = result.capturedImages;
  }
  saveGlobalState();
});

// Save global state to storage
function saveGlobalState() {
  chrome.storage.local.set({
    globalState: globalState,
    capturedImages: globalState.capturedImages
  });
}

// Handle messages from content scripts and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'getSettings':
      sendResponse({ settings: globalState.settings });
      break;
      
    case 'setSettings':
      globalState.settings = { ...globalState.settings, ...request.settings };
      saveGlobalState();
      // Broadcast settings update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateSettings', settings: globalState.settings }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'getGlobalState':
      sendResponse({ globalState: globalState });
      break;
      
    case 'setOverlayVisible':
      globalState.overlayVisible = request.visible;
      saveGlobalState();
      // Broadcast overlay visibility update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateOverlayVisibility', visible: request.visible }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'setFloatingMenuPosition':
      globalState.floatingMenuPosition = { ...globalState.floatingMenuPosition, ...request.position };
      saveGlobalState();
      // Broadcast position update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateFloatingMenuPosition', position: globalState.floatingMenuPosition }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'updateSettings':
      globalState.settings = { ...globalState.settings, ...request.settings };
      saveGlobalState();
      // Broadcast settings update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateSettings', settings: globalState.settings }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'captureImage':
      const imageData = {
        url: request.url,
        timestamp: Date.now(),
        domain: new URL(request.url).hostname,
        title: request.title || 'Captured Image'
      };
      
      if (!globalState.capturedImages.find(img => img.url === request.url)) {
        globalState.capturedImages.push(imageData);
        saveGlobalState();
        
        // Broadcast new image to all tabs
        chrome.tabs.query({}, (tabs) => {
          tabs.forEach(tab => {
            chrome.tabs.sendMessage(tab.id, { action: 'newImageCaptured', image: imageData }).catch(() => {});
          });
        });
      }
      sendResponse({ success: true });
      break;
      
    case 'getCapturedImages':
      sendResponse({ images: globalState.capturedImages });
      break;
      
    case 'clearCapturedImages':
      globalState.capturedImages = [];
      saveGlobalState();
      // Broadcast clear to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'imagesCleared' }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'downloadImages':
      console.log('Download request received:', request);
      const imagesToDownload = request.images || globalState.capturedImages;
      if (imagesToDownload.length === 0) {
        console.log('No images to download');
        sendResponse({ success: false, error: 'No images to download' });
        return;
      }
      
      console.log('Images to download:', imagesToDownload);
      
      // Download each image file individually
      let downloadCount = 0;
      const totalImages = imagesToDownload.length;
      
      imagesToDownload.forEach((img, index) => {
        const imageUrl = img.url || img;
        const filename = `image_${Date.now()}_${index + 1}.jpg`;
        
        console.log(`Downloading image ${index + 1}/${totalImages}:`, imageUrl);
        
        // Download the actual image file
        chrome.downloads.download({
          url: imageUrl,
          filename: filename,
          saveAs: false // Don't prompt for each file, use browser's default download folder
        }, (downloadId) => {
          downloadCount++;
          console.log(`Download ${index + 1} completed, downloadId:`, downloadId);
          
          // Check if all downloads are complete
          if (downloadCount === totalImages) {
            console.log('All downloads completed');
            sendResponse({ success: true, downloaded: downloadCount });
          }
        });
      });
      
      return true; // Keep message channel open for async response
      break;
      
    case 'sendToTelegram':
      const imagesToSend = request.images || globalState.capturedImages;
      if (imagesToSend.length === 0) {
        sendResponse({ success: false, error: 'No images to send' });
        return;
      }
      
      const imageUrls = imagesToSend.map(img => img.url);
      
      fetch('http://localhost:5000/send_multiple_telegram', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({image_urls: imageUrls})
      })
      .then(response => response.json())
      .then(data => {
        sendResponse({ success: data.success, data: data });
      })
      .catch(error => {
        sendResponse({ success: false, error: error.message });
      });
      
      return true; // Keep message channel open for async response
      
    case 'viewCollection':
      if (globalState.capturedImages.length === 0) {
        sendResponse({ success: false, error: 'No images in collection' });
        break;
      }
      
      try {
        const collectionHtml = generateCollectionHTML(globalState.capturedImages);
        const blob = new Blob([collectionHtml], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        
        chrome.tabs.create({ url }, (tab) => {
          if (chrome.runtime.lastError) {
            sendResponse({ success: false, error: chrome.runtime.lastError.message });
            URL.revokeObjectURL(url);
            return;
          }
          
          sendResponse({ success: true, tabId: tab && tab.id });
          
          // Revoke the object URL after the tab has loaded
          setTimeout(() => URL.revokeObjectURL(url), 60_000);
        });
        
        return true; // Keep message channel open for async response
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;
      
    default:
      sendResponse({ success: false, error: 'Unknown action' });
  }
});

// Handle tab updates to sync state
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url && tab.url.startsWith('http')) {
    // Send current state to new tab
    setTimeout(() => {
      chrome.tabs.sendMessage(tabId, { 
        action: 'initializeState', 
        globalState: globalState 
      }).catch(() => {});
    }, 1000);
  }
});

// Handle extension installation/update
chrome.runtime.onInstalled.addListener(() => {
  saveGlobalState();
  
  // Create context menu items
  chrome.contextMenus.create({
    id: 'imagecapture-main',
    title: '🖼️ ImageCapture',
    contexts: ['all']
  });
  
  chrome.contextMenus.create({
    id: 'toggle-sidebar',
    title: '📱 Toggle Sidebar',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'toggle-overlay-menu',
    title: '👁️ Toggle Overlay Menu',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'toggle-selection-mode',
    title: '🎯 Toggle Selection Mode',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'select-all-images',
    title: '☑️ Select All Images',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'capture-selected-images',
    title: '📸 Capture Selected Images',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'download-selected-images',
    title: '📥 Download Selected Images',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'clear-collection',
    title: '🗑️ Clear Collection',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
});

function generateCollectionHTML(images) {
  const totalSources = (() => {
    try {
      return new Set(images.map(img => new URL(img.url).hostname)).size;
    } catch (error) {
      console.warn('Failed to compute image hostnames:', error);
      return 1;
    }
  })();
  
  const statsStorage = formatBytes(images.length * 100);
  
  const cards = images.map((img, index) => {
    let hostname = '';
    let filename = 'Image';
    try {
      const url = new URL(img.url);
      hostname = url.hostname;
      filename = url.pathname.split('/').pop() || 'Image';
    } catch (_) {}
    
    const capturedDate = new Date(img.timestamp).toLocaleDateString();
    
    return `
                <div class="image-item" data-index="${index}" onclick="toggleImageSelection(this)">
                    <img src="${img.url}" alt="Captured image ${index + 1}" onerror="this.style.display='none'">
                    <div class="image-info">
                        <div class="image-title">${filename}</div>
                        <div class="image-meta">
                            <span>${hostname}</span>
                            <span>${capturedDate}</span>
                        </div>
                    </div>
                </div>
    `;
  }).join('');
  
  return `
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ImageCapture Collection</title>
        <style>
${generateCollectionStyles()}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🖼️ ImageCapture Collection</h1>
            <p>${images.length} images captured</p>
        </div>
        
        <div class="stats">
            <div class="stat-item">
                <span class="stat-number">${images.length}</span>
                <span class="stat-label">Total Images</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">${totalSources}</span>
                <span class="stat-label">Sources</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">${statsStorage}</span>
                <span class="stat-label">Storage Used</span>
            </div>
        </div>
        
        <div class="controls">
            <button class="btn primary" onclick="downloadSelected()">📥 Download Selected</button>
            <button class="btn telegram" onclick="sendToTelegram()">📤 Send to Telegram</button>
            <button class="btn" onclick="toggleSelectionMode()">🎯 Toggle Selection Mode</button>
            <button class="btn" onclick="selectAll()">☑️ Select All</button>
            <button class="btn danger" onclick="clearCollection()">🗑️ Clear Collection</button>
        </div>
        
        <div class="image-grid" id="imageGrid">
${cards}
        </div>
        
        <div class="selection-mode" id="selectionMode">
            <div class="selection-controls">
                <button class="btn" onclick="selectAll()">☑️ Select All</button>
                <button class="btn" onclick="deselectAll()">☐ Deselect All</button>
                <button class="btn danger" onclick="toggleSelectionMode()">✕ Exit Selection</button>
            </div>
            <div class="selection-stats">
                Selected: <span id="selectedCount">0</span> / ${images.length}
            </div>
        </div>
        
        <script>
${generateCollectionScript(images.length)}
        </script>
    </body>
    </html>
  `;
}

function generateCollectionStyles() {
  return `            body {
                margin: 0;
                padding: 20px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                min-height: 100vh;
            }
            
            .header {
                text-align: center;
                margin-bottom: 30px;
            }
            
            .header h1 {
                margin: 0;
                font-size: 32px;
                font-weight: 600;
                margin-bottom: 10px;
            }
            
            .stats {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 30px;
                backdrop-filter: blur(10px);
                display: flex;
                justify-content: space-around;
                flex-wrap: wrap;
                gap: 20px;
            }
            
            .stat-item {
                text-align: center;
            }
            
            .stat-number {
                font-size: 24px;
                font-weight: bold;
                display: block;
            }
            
            .stat-label {
                font-size: 14px;
                opacity: 0.8;
            }
            
            .controls {
                display: flex;
                gap: 12px;
                margin-bottom: 30px;
                flex-wrap: wrap;
                justify-content: center;
            }
            
            .btn {
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
                padding: 12px 20px;
                color: white;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s ease;
                text-decoration: none;
                display: inline-block;
            }
            
            .btn:hover {
                background: rgba(255, 255, 255, 0.3);
                transform: translateY(-2px);
            }
            
            .btn.primary {
                background: #4CAF50;
                border-color: #4CAF50;
            }
            
            .btn.primary:hover {
                background: #45a049;
            }
            
            .btn.danger {
                background: #f44336;
                border-color: #f44336;
            }
            
            .btn.danger:hover {
                background: #da190b;
            }
            
            .btn.telegram {
                background: #0088cc;
                border-color: #0088cc;
            }
            
            .btn.telegram:hover {
                background: #006699;
            }
            
            .image-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            
            .image-item {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                overflow: hidden;
                backdrop-filter: blur(10px);
                border: 3px solid transparent;
                background-clip: padding-box;
                position: relative;
                transition: all 0.3s ease;
                cursor: pointer;
            }
            
            .image-item::before {
                content: '';
                position: absolute;
                top: -3px;
                left: -3px;
                right: -3px;
                bottom: -3px;
                padding: 3px;
                background: linear-gradient(135deg, rgba(255, 255, 255, 0.3), rgba(255, 255, 255, 0.1));
                mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
                mask-composite: exclude;
                border-radius: 12px;
                opacity: 0.75;
                z-index: -1;
            }
            
            .image-item.selected::before {
                background: linear-gradient(135deg, #4CAF50, #45a049);
                opacity: 1;
            }
            
            .image-item:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
            }
            
            .image-item img {
                width: 100%;
                height: 200px;
                object-fit: cover;
                display: block;
            }
            
            .image-info {
                padding: 15px;
            }
            
            .image-title {
                font-size: 14px;
                font-weight: 600;
                margin-bottom: 8px;
                word-break: break-all;
            }
            
            .image-meta {
                font-size: 12px;
                opacity: 0.8;
                display: flex;
                justify-content: space-between;
            }
            
            .selection-mode {
                position: fixed;
                top: 20px;
                right: 20px;
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 15px;
                border-radius: 8px;
                backdrop-filter: blur(10px);
                z-index: 1000;
                display: none;
            }
            
            .selection-mode.active {
                display: block;
            }
            
            .selection-controls {
                display: flex;
                gap: 10px;
                margin-bottom: 10px;
            }
            
            .selection-stats {
                font-size: 12px;
                opacity: 0.8;
            }
            
            @media (max-width: 768px) {
                .image-grid {
                    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                    gap: 15px;
                }
                
                .controls {
                    flex-direction: column;
                    align-items: center;
                }
                
                .btn {
                    width: 100%;
                    max-width: 300px;
                }
            }`;
}

function generateCollectionScript(totalImages) {
  return `            const images = ${JSON.stringify(globalState.capturedImages)};
            let selectionMode = false;
            let selectedImages = new Set();
            
            function toggleSelectionMode() {
                selectionMode = !selectionMode;
                const modeDiv = document.getElementById('selectionMode');
                const toggleBtn = document.querySelector('button[onclick="toggleSelectionMode()"]');
                
                if (selectionMode) {
                    modeDiv.classList.add('active');
                    toggleBtn.textContent = '🎯 Exit Selection Mode';
                    toggleBtn.style.background = '#f44336';
                    document.body.style.cursor = 'crosshair';
                } else {
                    modeDiv.classList.remove('active');
                    toggleBtn.textContent = '🎯 Toggle Selection Mode';
                    toggleBtn.style.background = 'rgba(255, 255, 255, 0.2)';
                    document.body.style.cursor = 'default';
                    selectedImages.clear();
                    updateSelectionDisplay();
                    document.querySelectorAll('.image-item').forEach(item => item.classList.remove('selected'));
                }
            }
            
            function toggleImageSelection(element) {
                if (!selectionMode) return;
                
                const index = element.dataset.index;
                if (selectedImages.has(index)) {
                    selectedImages.delete(index);
                    element.classList.remove('selected');
                } else {
                    selectedImages.add(index);
                    element.classList.add('selected');
                }
                updateSelectionDisplay();
            }
            
            function selectAll() {
                if (!selectionMode) {
                    toggleSelectionMode();
                }
                selectedImages.clear();
                document.querySelectorAll('.image-item').forEach((item, index) => {
                    selectedImages.add(index.toString());
                    item.classList.add('selected');
                });
                updateSelectionDisplay();
            }
            
            function deselectAll() {
                selectedImages.clear();
                document.querySelectorAll('.image-item').forEach(item => {
                    item.classList.remove('selected');
                });
                updateSelectionDisplay();
            }
            
            function updateSelectionDisplay() {
                const counter = document.getElementById('selectedCount');
                if (counter) {
                    counter.textContent = selectedImages.size;
                }
            }
            
            function downloadSelected() {
                const imagesToDownload = selectionMode && selectedImages.size > 0 
                    ? Array.from(selectedImages).map(index => images[index])
                    : images;
                
                const urls = imagesToDownload.map(img => img.url).join('\\n');
                const blob = new Blob([urls], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                
                const a = document.createElement('a');
                a.href = url;
                a.download = 'captured_images.txt';
                a.click();
                
                setTimeout(() => URL.revokeObjectURL(url), 0);
                
                alert(\`\${imagesToDownload.length} image URLs downloaded!\`);
            }
            
            function sendToTelegram() {
                const imagesToSend = selectionMode && selectedImages.size > 0 
                    ? Array.from(selectedImages).map(index => images[index])
                    : images;
                
                const imageUrls = imagesToSend.map(img => img.url);
                
                fetch('http://localhost:5000/send_multiple_telegram', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({image_urls: imageUrls})
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert(\`✅ Successfully sent \${data.successful}/\${data.total_images} images to Telegram!\`);
                    } else {
                        alert(\`❌ Failed to send images: \${data.error}\`);
                    }
                })
                .catch(error => {
                    alert(\`❌ Error sending to Telegram: \${error.message}\`);
                });
            }
            
            function clearCollection() {
                if (confirm('Are you sure you want to clear all captured images?')) {
                    chrome.runtime.sendMessage({ action: 'clearCapturedImages' }, (response) => {
                        if (response && response.success) {
                            alert('Collection cleared!');
                            location.reload();
                        } else {
                            alert('Failed to clear collection');
                        }
                    });
                }
            }
            
            document.addEventListener('keydown', (e) => {
                if (e.target.tagName === 'INPUT') return;
                
                switch (e.key.toLowerCase()) {
                    case 's':
                        if (!e.ctrlKey && !e.metaKey) {
                            e.preventDefault();
                            toggleSelectionMode();
                        }
                        break;
                    case 'escape':
                        if (selectionMode) {
                            toggleSelectionMode();
                        }
                        break;
                }
            });
        `;
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!tab || !tab.url || !tab.url.startsWith('http')) return;
  
  switch (info.menuItemId) {
    case 'toggle-sidebar':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleSidebar' }).catch(() => {});
      break;
      
    case 'toggle-overlay-menu':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleOverlayMenu' }).catch(() => {});
      break;
      
    case 'toggle-selection-mode':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleSelectionMode' }).catch(() => {});
      break;
      
    case 'select-all-images':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleSelectAll' }).catch(() => {});
      break;
      
    case 'capture-selected-images':
      chrome.tabs.sendMessage(tab.id, { action: 'captureSelectedImages' }).catch(() => {});
      break;
      
    case 'download-selected-images':
      chrome.tabs.sendMessage(tab.id, { action: 'downloadSelectedImages' }).catch(() => {});
      break;
      
    case 'clear-collection':
      chrome.tabs.sendMessage(tab.id, { action: 'clearCapturedImages' }).catch(() => {});
      break;
  }
}); 
```

```javascript
// Content script for ImageCapture extension
let selectionMode = false;
let selectedImages = new Set();
let sidebarVisible = false;
let sidebarElement = null;
let floatingMenu = null;
let isolationMode = false;
let overlayMenuVisible = false;
let overlayHoverTimer = null;
let floatingMenuPosition = { x: 20, y: 20, width: 280, height: 'auto' };
let settings = {
  hoverSelectDelay: 500,
  hoverDeselectDelay: 300,
  autoCaptureHover: false, // Disabled hover selection
  showNotifications: true,
  showSelectionIndicator: true,
  telegramEnabled: true,
  showFloatingMenu: true,
  minImageWidth: 100,
  preferredFileTypes: ['jpg', 'jpeg', 'png'],
  overlayHoverDelay: 1000,
      overlayButtons: ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'],
  overlayDraggable: true,
  quickToolbarMode: false,
  useOverlayIcons: false // New setting for toggleable selection indicators
};

// Load global state from background script
chrome.runtime.sendMessage({action: 'getGlobalState'}, (response) => {
  if (response && response.globalState) {
    const globalState = response.globalState;
    settings = { ...settings, ...globalState.settings };
    overlayMenuVisible = globalState.overlayVisible;
    selectedImages = new Set(globalState.selectedImages || []);
    floatingMenuPosition = globalState.floatingMenuPosition || { x: 20, y: 20, width: 280, height: 'auto' };
  }
});

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  addImageIndicators();
  createFloatingMenu();
  
  // Monitor for dynamically added images
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'childList') {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            const images = node.querySelectorAll('img');
            if (images.length > 0) {
              addImageIndicators();
            }
          }
        });
      }
    });
  });
  
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
});

// Also initialize if DOM is already loaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeExtension);
} else {
  initializeExtension();
}

function initializeExtension() {
  addImageIndicators();
  if (settings.showFloatingMenu) {
    createFloatingMenu();
  }
  
  // Add window resize handler to keep menu within bounds
  window.addEventListener('resize', handleWindowResize);
}

// Handle window resize to keep floating menu within viewport
function handleWindowResize() {
  if (!floatingMenu) return;
  
  const rect = floatingMenu.getBoundingClientRect();
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  
  let needsUpdate = false;
  let newX = floatingMenuPosition.x;
  let newY = floatingMenuPosition.y;
  
  // Check if menu is outside viewport - use absolute positioning
  if (rect.right > viewportWidth) {
    newX = Math.max(20, viewportWidth - rect.width - 20);
    needsUpdate = true;
  }
  
  if (rect.bottom > viewportHeight) {
    newY = Math.max(20, viewportHeight - rect.height - 20);
    needsUpdate = true;
  }
  
  if (rect.left < 0) {
    newX = 20; // Keep menu at minimum left position
    needsUpdate = true;
  }
  
  if (rect.top < 0) {
    newY = Math.min(viewportHeight - rect.height - 20, 20);
    needsUpdate = true;
  }
  
  if (needsUpdate) {
    floatingMenuPosition.x = newX;
    floatingMenuPosition.y = newY;
    
    // Use absolute positioning instead of right-based
    floatingMenu.style.left = `${newX}px`;
    floatingMenu.style.top = `${newY}px`;
    floatingMenu.style.right = 'auto';
    
    // Save updated position
    chrome.runtime.sendMessage({
      action: 'setFloatingMenuPosition',
      position: floatingMenuPosition
    });
  }
}

// Add visual indicators to images with enhanced styling
function addImageIndicators() {
  const images = document.querySelectorAll('img');
  
  images.forEach(img => {
    if (img.dataset.imagecaptureInitialized) return;
    
    img.dataset.imagecaptureInitialized = 'true';
    img.style.cursor = 'pointer';
    
    // Only show borders/overlays when selection mode is active
    if (selectionMode) {
      // Enhanced border styling with increased thickness and reduced opacity
      if (selectedImages.has(img.src)) {
        if (settings.useOverlayIcons) {
          addSelectionOverlay(img);
        } else {
          img.style.border = '10px solid rgba(76, 175, 80, 0.75)';
          img.style.borderRadius = '8px';
          img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
          img.style.boxShadow = '0 0 20px rgba(76, 175, 80, 0.5), inset 0 0 20px rgba(76, 175, 80, 0.2)';
        }
      } else {
        if (settings.useOverlayIcons) {
          addCheckboxOverlay(img);
        } else {
          img.style.border = '10px solid rgba(255, 107, 107, 0.5625)';
          img.style.borderRadius = '8px';
          img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
          img.style.boxShadow = '0 0 20px rgba(255, 107, 107, 0.375), inset 0 0 20px rgba(255, 107, 107, 0.15)';
        }
      }
    } else {
      // Clear any existing borders/overlays when selection mode is off
      if (settings.useOverlayIcons) {
        removeSelectionOverlay(img);
      } else {
        img.style.border = 'none';
        img.style.boxShadow = 'none';
      }
    }
    
    // Click event
    img.addEventListener('click', (e) => {
      if (selectionMode) {
        e.preventDefault();
        e.stopPropagation();
        toggleImageSelection(img);
      }
    });
    
    // Mouse 3 (middle click) event
    img.addEventListener('auxclick', (e) => {
      if (e.button === 1) {
        e.preventDefault();
        e.stopPropagation();
        handleImageAuxClick(e);
      }
    });
  });
}

// Add selection overlay icon
function addSelectionOverlay(img) {
  // Remove any existing overlay
  removeSelectionOverlay(img);
  
  // Create overlay container
  const overlay = document.createElement('div');
  overlay.className = 'imagecapture-selection-overlay';
  overlay.style.cssText = `
    position: absolute;
    top: 10px;
    right: 10px;
    width: 30px;
    height: 30px;
    background: #4CAF50;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 18px;
    font-weight: bold;
    z-index: 1000;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  `;
  overlay.innerHTML = '✓';
  
  // Ensure img has relative positioning
  if (img.style.position !== 'relative' && img.style.position !== 'absolute') {
    img.style.position = 'relative';
  }
  
  img.appendChild(overlay);
}

// Add checkbox overlay for unselected images
function addCheckboxOverlay(img) {
  // Remove any existing overlay
  removeSelectionOverlay(img);
  
  // Create checkbox overlay container
  const overlay = document.createElement('div');
  overlay.className = 'imagecapture-checkbox-overlay';
  overlay.style.cssText = `
    position: absolute;
    top: 10px;
    right: 10px;
    width: 30px;
    height: 30px;
    background: rgba(255, 255, 255, 0.9);
    border: 2px solid #ccc;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #666;
    font-size: 16px;
    font-weight: bold;
    z-index: 1000;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    cursor: pointer;
  `;
  overlay.innerHTML = '';
  
  // Add click handler to the checkbox
  overlay.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    toggleImageSelection(img);
  });
  
  // Ensure img has relative positioning
  if (img.style.position !== 'relative' && img.style.position !== 'absolute') {
    img.style.position = 'relative';
  }
  
  img.appendChild(overlay);
}

// Remove selection overlay icon
function removeSelectionOverlay(img) {
  const overlay = img.querySelector('.imagecapture-selection-overlay, .imagecapture-checkbox-overlay');
  if (overlay) {
    overlay.remove();
  }
}

// Handle image aux click (Mouse 3)
function handleImageAuxClick(e) {
  const img = e.target;
  const imageUrl = img.src;
  
  if (selectedImages.has(imageUrl)) {
    selectedImages.delete(imageUrl);
    animateImageSelection(img, false);
  } else {
    selectedImages.add(imageUrl);
    animateImageSelection(img, true);
  }
  
  updateSelectionCounter();
}

// Animate image selection with enhanced visual feedback
function animateImageSelection(img, isSelected) {
  if (isSelected) {
    if (settings.useOverlayIcons) {
      addSelectionOverlay(img);
    } else {
      img.style.border = '10px solid rgba(76, 175, 80, 0.75)';
      img.style.boxShadow = `
        0 0 20px rgba(76, 175, 80, 0.5), 
        inset 0 0 20px rgba(76, 175, 80, 0.2),
        0 0 40px rgba(76, 175, 80, 0.3),
        0 0 60px rgba(76, 175, 80, 0.1)
      `;
    }
    img.style.transform = 'scale(1.02)';
    img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
    
    setTimeout(() => {
      img.style.transform = 'scale(1)';
    }, 200);
  } else {
    if (settings.useOverlayIcons) {
      addCheckboxOverlay(img);
    } else {
      img.style.border = '10px solid rgba(255, 107, 107, 0.5625)';
      img.style.boxShadow = `
        0 0 20px rgba(255, 107, 107, 0.375), 
        inset 0 0 20px rgba(255, 107, 107, 0.15),
        0 0 40px rgba(255, 107, 107, 0.25),
        0 0 60px rgba(255, 107, 107, 0.1)
      `;
    }
    img.style.transform = 'scale(1)';
    img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
  }
}

// Remove border after download
function removeImageBorder(img) {
  if (settings.useOverlayIcons) {
    removeSelectionOverlay(img);
  } else {
    img.style.border = 'none';
    img.style.boxShadow = 'none';
  }
  img.style.transform = 'scale(1)';
}

// Toggle image selection
function toggleImageSelection(img) {
  const imageUrl = img.src;
  
  if (selectedImages.has(imageUrl)) {
    selectedImages.delete(imageUrl);
    animateImageSelection(img, false);
  } else {
    selectedImages.add(imageUrl);
    animateImageSelection(img, true);
  }
  
  updateSelectionCounter();
}

// Select all images
function selectAllImages() {
  const images = document.querySelectorAll('img');
  images.forEach(img => {
    if (shouldCaptureImage(img)) {
      selectedImages.add(img.src);
      animateImageSelection(img, true);
    }
  });
  updateSelectionCounter();
  showNotification(`Selected ${selectedImages.size} images`);
}

// Deselect all images
function deselectAllImages() {
  const images = document.querySelectorAll('img');
  images.forEach(img => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      animateImageSelection(img, false);
    }
  });
  updateSelectionCounter();
  showNotification('Deselected all images');
}

// Toggle select all/deselect all
function toggleSelectAll() {
  const images = document.querySelectorAll('img');
  const capturableImages = Array.from(images).filter(img => shouldCaptureImage(img));
  const selectedCapturableImages = capturableImages.filter(img => selectedImages.has(img.src));
  
  if (selectedCapturableImages.length === capturableImages.length) {
    deselectAllImages();
  } else {
    selectAllImages();
  }
}

// Capture selected images
function captureSelectedImages() {
  const imagesToCapture = Array.from(selectedImages);
  if (imagesToCapture.length === 0) {
    showNotification('No images selected to capture');
    return;
  }
  
  imagesToCapture.forEach(imageUrl => {
    chrome.runtime.sendMessage({
      action: 'captureImage',
      url: imageUrl,
      title: document.title
    });
    
    // Remove border after capture
    const img = document.querySelector(`img[src="${imageUrl}"]`);
    if (img) {
      removeImageBorder(img);
    }
  });
  
  selectedImages.clear();
  updateSelectionCounter();
  showNotification(`Captured ${imagesToCapture.length} images`);
}

// Update selection counter
function updateSelectionCounter() {
  if (floatingMenu && floatingMenu.counter) {
    floatingMenu.counter.textContent = `Selected: ${selectedImages.size}`;
  }
  if (sidebarElement && sidebarElement.counter) {
    sidebarElement.counter.textContent = `Selected: ${selectedImages.size}`;
  }
}

// Toggle selection mode
function toggleSelectionMode() {
  selectionMode = !selectionMode;
  
  if (selectionMode) {
    document.body.style.cursor = 'crosshair';
    showNotification('Selection mode ON - Click images to select');
  } else {
    document.body.style.cursor = 'default';
    showNotification('Selection mode OFF');
  }
  
  // Refresh image indicators to show/hide borders based on selection mode
  addImageIndicators();
  
  // Update floating menu button
  if (floatingMenu && floatingMenu.toggleBtn) {
    floatingMenu.toggleBtn.textContent = selectionMode ? '🎯 Selection: ON' : '🎯 Selection: OFF';
    floatingMenu.toggleBtn.style.background = selectionMode ? '#4CAF50' : '#ff9800';
    floatingMenu.toggleBtn.style.borderColor = selectionMode ? '#4CAF50' : 'transparent';
  }
  
  // Update sidebar button if exists
  if (sidebarElement && sidebarElement.toggleBtn) {
    sidebarElement.toggleBtn.textContent = selectionMode ? '🎯 Selection: ON' : '🎯 Selection: OFF';
    sidebarElement.toggleBtn.style.background = selectionMode ? '#4CAF50' : '#ff9800';
  }
}

// Toggle overlay menu visibility with hover delay
function toggleOverlayMenu() {
  if (settings.overlayHoverDelay > 0) {
    if (overlayHoverTimer) {
      clearTimeout(overlayHoverTimer);
      overlayHoverTimer = null;
    }
    
    overlayHoverTimer = setTimeout(() => {
      overlayMenuVisible = !overlayMenuVisible;
      
      if (floatingMenu) {
        floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
      }
      
      // Save state to background
      chrome.runtime.sendMessage({
        action: 'setOverlayVisible',
        visible: overlayMenuVisible
      });
      
      showNotification(overlayMenuVisible ? 'Overlay menu shown' : 'Overlay menu hidden');
    }, settings.overlayHoverDelay);
  } else {
    overlayMenuVisible = !overlayMenuVisible;
    
    if (floatingMenu) {
      floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
    }
    
    chrome.runtime.sendMessage({
      action: 'setOverlayVisible',
      visible: overlayMenuVisible
    });
    
    showNotification(overlayMenuVisible ? 'Overlay menu shown' : 'Overlay menu hidden');
  }
}

// Create draggable floating menu with customizable buttons
function createFloatingMenu() {
  if (floatingMenu) return;
  
  floatingMenu = document.createElement('div');
  floatingMenu.id = 'imagecapture-floating-menu';
  floatingMenu.style.cssText = `
    position: fixed;
    left: ${floatingMenuPosition.x}px;
    top: ${floatingMenuPosition.y}px;
    background: rgba(0, 0, 0, 0.8);
    backdrop-filter: blur(10px);
    border-radius: 12px;
    padding: 16px;
    z-index: 10000;
    display: flex;
    flex-direction: column;
    gap: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    transition: all 0.3s ease;
    min-width: 200px;
    max-width: 280px;
    width: 280px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    resize: both;
    overflow: auto;
  `;
  
  // Add drag handle
  const dragHandle = document.createElement('div');
  dragHandle.innerHTML = '⋮⋮';
  dragHandle.style.cssText = `
    position: absolute;
    top: 8px;
    left: 8px;
    color: rgba(255, 255, 255, 0.6);
    cursor: move;
    font-size: 14px;
    font-weight: bold;
    user-select: none;
  `;
  
  // Add close button
  const closeBtn = document.createElement('button');
  closeBtn.innerHTML = '✕';
  closeBtn.style.cssText = `
    position: absolute;
    top: 8px;
    right: 8px;
    background: #f44336;
    color: white;
    border: none;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    cursor: pointer;
    font-size: 12px;
    font-weight: bold;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10001;
    transition: all 0.2s ease;
  `;
  closeBtn.onmouseenter = () => {
    closeBtn.style.background = '#d32f2f';
    closeBtn.style.transform = 'scale(1.1)';
  };
  closeBtn.onmouseleave = () => {
    closeBtn.style.background = '#f44336';
    closeBtn.style.transform = 'scale(1)';
  };
  closeBtn.onclick = () => {
    floatingMenu.remove();
    floatingMenu = null;
  };
  
  // Create button container
  const buttonContainer = document.createElement('div');
  buttonContainer.style.cssText = `
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 20px;
  `;
  
  // Create buttons based on settings
  const buttonConfigs = {
    overlay: {
      text: '👁️ Overlay',
      color: '#607D8B',
      action: () => toggleOverlayMenu()
    },
    selection: {
      text: '🎯 Selection: OFF',
      color: '#ff9800',
      action: () => toggleSelectionMode()
    },
    selectAll: {
      text: '☑️ Select All',
      color: '#2196F3',
      action: () => toggleSelectAll()
    },
    sidebar: {
      text: '📱 Sidebar',
      color: '#2196F3',
      action: () => toggleSidebar()
    },
    isolation: {
      text: '🖼️ Image Mode',
      color: '#9C27B0',
      action: () => toggleIsolationMode()
    },
    capture: {
      text: '📸 Capture',
      color: '#4CAF50',
      action: () => captureSelectedImages()
    },
    download: {
      text: '📥 Download',
      color: '#FF9800',
      action: () => downloadSelectedImages()
    },
    quickToolbar: {
      text: '⚡ Quick Toolbar',
      color: '#E91E63',
      action: () => toggleQuickToolbar()
    }
  };
  
  const buttons = {};
  const buttonOrder = [...settings.overlayButtons];
  
  function createButtonElement(buttonType) {
    if (!buttonConfigs[buttonType]) return null;
    
    const config = buttonConfigs[buttonType];
    const btn = document.createElement('div');
    btn.className = 'overlay-button';
    btn.dataset.buttonType = buttonType;
    btn.style.cssText = `
      background: ${config.color};
      color: white;
      border: none;
      padding: 10px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 500;
      transition: all 0.2s ease;
      position: relative;
      user-select: none;
      display: flex;
      align-items: center;
      gap: 8px;
    `;
    
    // Add drag handle for reordering
    const handle = document.createElement('div');
    handle.innerHTML = '⋮';
    handle.className = 'button-handle';
    handle.style.cssText = `
      color: rgba(255, 255, 255, 0.6);
      cursor: move;
      font-size: 10px;
      font-weight: bold;
      user-select: none;
      padding: 2px;
    `;
    
    const textSpan = document.createElement('span');
    textSpan.textContent = config.text;
    
    btn.appendChild(handle);
    btn.appendChild(textSpan);
    
    // Add drag functionality for reordering
    makeButtonDraggable(btn, handle, buttonContainer);
    
    btn.onclick = (e) => {
      if (e.target !== handle) {
        config.action();
      }
    };
    
    btn.onmouseenter = () => {
      if (!btn.classList.contains('dragging')) {
        btn.style.transform = 'translateY(-1px)';
        btn.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.2)';
      }
    };
    
    btn.onmouseleave = () => {
      if (!btn.classList.contains('dragging')) {
        btn.style.transform = 'translateY(0)';
        btn.style.boxShadow = 'none';
      }
    };
    
    return btn;
  }
  
  // Create and add buttons in order
  buttonOrder.forEach(buttonType => {
    const btn = createButtonElement(buttonType);
    if (btn) {
      buttonContainer.appendChild(btn);
      buttons[buttonType] = btn;
    }
  });
  
  const counter = document.createElement('div');
  counter.textContent = 'Selected: 0';
  counter.style.cssText = `
    color: white;
    font-size: 11px;
    text-align: center;
    margin-top: 8px;
    padding: 4px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
  `;
  
  floatingMenu.appendChild(dragHandle);
  floatingMenu.appendChild(closeBtn);
  floatingMenu.appendChild(buttonContainer);
  floatingMenu.appendChild(counter);
  
  // Store references
  floatingMenu.toggleBtn = buttons.selection;
  floatingMenu.selectAllBtn = buttons.selectAll;
  floatingMenu.sidebarBtn = buttons.sidebar;
  floatingMenu.isolationBtn = buttons.isolation;
  floatingMenu.captureBtn = buttons.capture;
  floatingMenu.downloadBtn = buttons.download;
  floatingMenu.counter = counter;
  floatingMenu.buttonContainer = buttonContainer;
  
  // Add drag functionality for moving the menu
  if (settings.overlayDraggable) {
    makeDraggable(floatingMenu, dragHandle);
  }
  
  // Add resize observer to track manual resizing
  const resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      if (entry.target === floatingMenu) {
        const rect = entry.target.getBoundingClientRect();
        
        // Only update width and height, preserve current x and y positions
        // This prevents the menu from "jumping" when resizing from the right edge
        // Apply max-width constraint to prevent full-screen stretching
        const maxWidth = settings.quickToolbarMode ? 400 : 280;
        const constrainedWidth = Math.min(rect.width, maxWidth);
        
        const newPosition = {
          x: floatingMenuPosition.x, // Preserve current x position
          y: floatingMenuPosition.y, // Preserve current y position
          width: constrainedWidth,
          height: rect.height
        };
        
        // Only update if the size actually changed to prevent unnecessary updates
        if (newPosition.width !== floatingMenuPosition.width || 
            newPosition.height !== floatingMenuPosition.height) {
          
          floatingMenuPosition = newPosition;
          
          // Temporarily disable transitions during resize to prevent stretching effect
          const originalTransition = floatingMenu.style.transition;
          floatingMenu.style.transition = 'none';
          
          // Apply the constrained width to the element
          floatingMenu.style.width = `${constrainedWidth}px`;
          
          // Don't update min-width dynamically - this causes stretching issues
          // The min-width should remain fixed at the initial value
          
          // Re-enable transitions after a brief delay
          setTimeout(() => {
            floatingMenu.style.transition = originalTransition;
          }, 50);
          
          chrome.runtime.sendMessage({
            action: 'setFloatingMenuPosition',
            position: newPosition
          });
        }
      }
    }
  });
  resizeObserver.observe(floatingMenu);
  
  // Set initial visibility - ensure it's visible if overlayMenuVisible is true
  floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
  
  // Apply toolbar mode if enabled
  if (settings.quickToolbarMode) {
    toggleQuickToolbar();
  }
  
  document.body.appendChild(floatingMenu);
}

// Make element draggable
function makeDraggable(element, handle) {
  let isDragging = false;
  let currentX;
  let currentY;
  let initialX;
  let initialY;
  let xOffset = 0;
  let yOffset = 0;
  
  handle.addEventListener('mousedown', dragStart);
  document.addEventListener('mousemove', drag);
  document.addEventListener('mouseup', dragEnd);
  
  function dragStart(e) {
    // Only allow dragging if the target is the handle or its children
    if (e.target === handle || handle.contains(e.target)) {
      initialX = e.clientX - xOffset;
      initialY = e.clientY - yOffset;
      isDragging = true;
      e.preventDefault(); // Prevent text selection
    }
  }
  
  function drag(e) {
    if (isDragging) {
      e.preventDefault();
      
      currentX = e.clientX - initialX;
      currentY = e.clientY - initialY;
      
      xOffset = currentX;
      yOffset = currentY;
      
      setTranslate(currentX, currentY, element);
    }
  }
  
  function setTranslate(xPos, yPos, el) {
    el.style.transform = `translate3d(${xPos}px, ${yPos}px, 0)`;
  }
  
  function dragEnd(e) {
    initialX = currentX;
    initialY = currentY;
    isDragging = false;
    
    // Save position to background script - use absolute positioning
    const rect = element.getBoundingClientRect();
    const newPosition = {
      x: rect.left,
      y: rect.top,
      width: rect.width,
      height: rect.height
    };
    
    floatingMenuPosition = newPosition;
    
    // Reset transform and apply absolute positioning
    element.style.transform = 'none';
    element.style.left = `${newPosition.x}px`;
    element.style.top = `${newPosition.y}px`;
    
    chrome.runtime.sendMessage({
      action: 'setFloatingMenuPosition',
      position: newPosition
    });
  }
}

// Make button draggable for reordering
function makeButtonDraggable(button, handle, container) {
  let isDragging = false;
  let dragStartY = 0;
  let originalY = 0;
  let placeholder = null;
  
  handle.addEventListener('mousedown', (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    isDragging = true;
    dragStartY = e.clientY;
    originalY = button.offsetTop;
    
    // Create placeholder
    placeholder = document.createElement('div');
    placeholder.style.cssText = `
      height: ${button.offsetHeight}px;
      background: rgba(255, 255, 255, 0.1);
      border: 2px dashed rgba(255, 255, 255, 0.3);
      border-radius: 6px;
      margin: 4px 0;
    `;
    
    // Add dragging class
    button.classList.add('dragging');
    button.style.opacity = '0.8';
    button.style.transform = 'rotate(2deg) scale(1.02)';
    button.style.zIndex = '1000';
    
    // Insert placeholder
    container.insertBefore(placeholder, button);
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  });
  
  function handleMouseMove(e) {
    if (!isDragging) return;
    
    const deltaY = e.clientY - dragStartY;
    const newY = originalY + deltaY;
    
    // Find the new position
    const buttons = Array.from(container.children).filter(child => 
      child.classList.contains('overlay-button') && child !== button
    );
    
    let insertIndex = 0;
    for (let i = 0; i < buttons.length; i++) {
      const btn = buttons[i];
      const btnRect = btn.getBoundingClientRect();
      const btnCenter = btnRect.top + btnRect.height / 2;
      
      if (e.clientY < btnCenter) {
        insertIndex = i;
        break;
      }
      insertIndex = i + 1;
    }
    
    // Move placeholder
    const allButtons = Array.from(container.children).filter(child => 
      child.classList.contains('overlay-button') && child !== button
    );
    
    if (placeholder && allButtons.length > 0) {
      if (insertIndex >= allButtons.length) {
        container.appendChild(placeholder);
      } else {
        container.insertBefore(placeholder, allButtons[insertIndex]);
      }
    }
  }
  
  function handleMouseUp() {
    if (!isDragging) return;
    
    isDragging = false;
    
    // Remove dragging class
    button.classList.remove('dragging');
    button.style.opacity = '1';
    button.style.transform = 'rotate(0deg) scale(1)';
    button.style.zIndex = 'auto';
    
    // Move button to placeholder position
    if (placeholder && placeholder.parentNode) {
      placeholder.parentNode.insertBefore(button, placeholder);
      placeholder.remove();
    }
    
    // Update button order in settings
    updateButtonOrder();
    
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  }
}

// Update button order in settings
function updateButtonOrder() {
  if (!floatingMenu || !floatingMenu.buttonContainer) return;
  
  const buttons = Array.from(floatingMenu.buttonContainer.children)
    .filter(child => child.classList.contains('overlay-button'))
    .map(btn => btn.dataset.buttonType);
  
  settings.overlayButtons = buttons;
  
  // Save to background
  chrome.runtime.sendMessage({
    action: 'updateSettings',
    settings: { overlayButtons: buttons }
  });
}

// Download selected images
function downloadSelectedImages() {
  const imagesToDownload = Array.from(selectedImages);
  if (imagesToDownload.length === 0) {
    showNotification('No images selected to download');
    return;
  }
  
  showNotification(`Starting download of ${imagesToDownload.length} images...`);
  
  // Debug logging
  console.log('Downloading images:', imagesToDownload);
  
  chrome.runtime.sendMessage({
    action: 'downloadImages',
    images: imagesToDownload.map(url => ({ url, title: document.title }))
  }, (response) => {
    console.log('Download response:', response);
    if (response && response.success) {
      // Remove borders after download
      imagesToDownload.forEach(imageUrl => {
        const img = document.querySelector(`img[src="${imageUrl}"]`);
        if (img) {
          removeImageBorder(img);
        }
      });
      
      selectedImages.clear();
      updateSelectionCounter();
      showNotification(`Successfully downloaded ${response.downloaded || imagesToDownload.length} images to your browser's download folder`);
    } else {
      showNotification(`Failed to download images: ${response.error || 'Unknown error'}`);
    }
  });
}

// Create sidebar with enhanced features
function createSidebar() {
  if (sidebarElement) return;
  
  sidebarElement = document.createElement('div');
  sidebarElement.id = 'imagecapture-sidebar';
  sidebarElement.style.cssText = `
    position: fixed;
    top: 0;
    right: 0;
    width: 300px;
    height: 100vh;
    background: white;
    box-shadow: -2px 0 10px rgba(0, 0, 0, 0.3);
    z-index: 9999;
    display: flex;
    flex-direction: column;
    transition: width 0.3s ease;
    resize: horizontal;
    overflow: auto;
    min-width: 200px;
    max-width: 80vw;
  `;
  
  // Header
  const header = document.createElement('div');
  header.style.cssText = `
    background: #667eea;
    color: white;
    padding: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
  `;
  header.innerHTML = `
    <h3 style="margin: 0; font-size: 16px;">🖼️ ImageCapture Sidebar</h3>
    <button id="sidebar-close" style="background: #f44336; border: none; color: white; font-size: 18px; cursor: pointer; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">✕</button>
  `;
  
  // Controls
  const controls = document.createElement('div');
  controls.style.cssText = `
    padding: 12px;
    border-bottom: 1px solid #eee;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    flex-shrink: 0;
  `;
  
  const toggleBtn = document.createElement('button');
  toggleBtn.textContent = '🎯 Selection: OFF';
  toggleBtn.style.cssText = `
    background: #ff9800;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  toggleBtn.onclick = () => toggleSelectionMode();
  
  const selectAllBtn = document.createElement('button');
  selectAllBtn.textContent = '☑️ Select All';
  selectAllBtn.style.cssText = `
    background: #2196F3;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  selectAllBtn.onclick = () => toggleSelectAll();
  
  const refreshBtn = document.createElement('button');
  refreshBtn.textContent = '🔄 Refresh';
  refreshBtn.style.cssText = `
    background: #4CAF50;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  refreshBtn.onclick = () => refreshSidebar();
  
  const expandBtn = document.createElement('button');
  expandBtn.textContent = '📏 Expand';
  expandBtn.style.cssText = `
    background: #2196F3;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  expandBtn.onclick = () => toggleSidebarExpansion();
  
  const gridBtn = document.createElement('button');
  gridBtn.textContent = '🔲 Grid';
  gridBtn.style.cssText = `
    background: #9C27B0;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  gridBtn.onclick = () => toggleGridMode();
  
  const captureBtn = document.createElement('button');
  captureBtn.textContent = '📸 Capture All';
  captureBtn.style.cssText = `
    background: #4CAF50;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  captureBtn.onclick = () => captureAllImagesToSidebar();
  
  const downloadBtn = document.createElement('button');
  downloadBtn.textContent = '📥 Download Selected';
  downloadBtn.style.cssText = `
    background: #FF9800;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  downloadBtn.onclick = () => downloadSelectedImages();
  
  const isolationBtn = document.createElement('button');
  isolationBtn.textContent = '🖼️ Image Mode';
  isolationBtn.style.cssText = `
    background: #9C27B0;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  isolationBtn.onclick = () => toggleIsolationMode();
  
  const overlayToggleBtn = document.createElement('button');
  overlayToggleBtn.textContent = '👁️ Overlay Menu On/Off';
  overlayToggleBtn.style.cssText = `
    background: #607D8B;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  overlayToggleBtn.onclick = () => toggleOverlayMenu();
  
  const toolbarToggleBtn = document.createElement('button');
  toolbarToggleBtn.textContent = '⚡ Quick Toolbar';
  toolbarToggleBtn.style.cssText = `
    background: #FF5722;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  toolbarToggleBtn.onclick = () => toggleQuickToolbar();
  
  controls.appendChild(toggleBtn);
  controls.appendChild(selectAllBtn);
  controls.appendChild(refreshBtn);
  controls.appendChild(expandBtn);
  controls.appendChild(gridBtn);
  controls.appendChild(captureBtn);
  controls.appendChild(downloadBtn);
  controls.appendChild(isolationBtn);
  controls.appendChild(overlayToggleBtn);
  controls.appendChild(toolbarToggleBtn);
  
  // Counter
  const counter = document.createElement('div');
  counter.textContent = 'Selected: 0';
  counter.style.cssText = `
    padding: 8px 12px;
    background: #f5f5f5;
    border-bottom: 1px solid #eee;
    font-size: 12px;
    font-weight: 500;
    color: #333;
    flex-shrink: 0;
  `;
  
  // Content area
  const content = document.createElement('div');
  content.style.cssText = `
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    min-height: 0;
  `;
  
  sidebarElement.appendChild(header);
  sidebarElement.appendChild(controls);
  sidebarElement.appendChild(counter);
  sidebarElement.appendChild(content);
  
  // Store references
  sidebarElement.toggleBtn = toggleBtn;
  sidebarElement.selectAllBtn = selectAllBtn;
  sidebarElement.refreshBtn = refreshBtn;
  sidebarElement.expandBtn = expandBtn;
  sidebarElement.gridBtn = gridBtn;
  sidebarElement.overlayToggleBtn = overlayToggleBtn;
  sidebarElement.toolbarToggleBtn = toolbarToggleBtn;
  sidebarElement.counter = counter;
  sidebarElement.content = content;
  sidebarElement.isExpanded = false;
  sidebarElement.isGridMode = true;
  
  // Close button event
  header.querySelector('#sidebar-close').onclick = () => toggleSidebar();
  
  document.body.appendChild(sidebarElement);
}

// Refresh sidebar content
function refreshSidebar() {
  if (!sidebarElement) return;
  
  captureAllImagesToSidebar();
  showNotification('Sidebar refreshed');
}

// Toggle sidebar
function toggleSidebar() {
  if (sidebarVisible) {
    if (sidebarElement) {
      sidebarElement.remove();
      sidebarElement = null;
    }
    sidebarVisible = false;
  } else {
    createSidebar();
    sidebarVisible = true;
  }
}

// Toggle sidebar expansion
function toggleSidebarExpansion() {
  if (!sidebarElement) return;
  
  sidebarElement.isExpanded = !sidebarElement.isExpanded;
  
  if (sidebarElement.isExpanded) {
    sidebarElement.style.width = '66vw';
    sidebarElement.expandBtn.textContent = '📏 Collapse';
  } else {
    sidebarElement.style.width = '300px';
    sidebarElement.expandBtn.textContent = '📏 Expand';
  }
}

// Toggle grid mode
function toggleGridMode() {
  if (!sidebarElement) return;
  
  sidebarElement.isGridMode = !sidebarElement.isGridMode;
  
  if (sidebarElement.isGridMode) {
    sidebarElement.content.style.gridTemplateColumns = 'repeat(2, 1fr)';
    sidebarElement.gridBtn.textContent = '🔲 Grid';
  } else {
    sidebarElement.content.style.gridTemplateColumns = '1fr';
    sidebarElement.gridBtn.textContent = '📱 Single';
  }
}

// Toggle quick toolbar mode
function toggleQuickToolbar() {
  settings.quickToolbarMode = !settings.quickToolbarMode;
  
  if (floatingMenu) {
    if (settings.quickToolbarMode) {
      // Switch to toolbar mode
      floatingMenu.style.cssText = `
        position: fixed;
        left: ${floatingMenuPosition.x}px;
        top: ${floatingMenuPosition.y}px;
        background: rgba(0, 0, 0, 0.9);
        backdrop-filter: blur(10px);
        border-radius: 8px;
        padding: 8px;
        z-index: 10000;
        display: flex;
        flex-direction: row;
        gap: 4px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
        border: 1px solid rgba(255, 255, 255, 0.1);
        resize: both;
        overflow: auto;
        min-width: auto;
        max-width: 400px;
        width: auto;
        min-height: auto;
      `;
      
      // Update button container for horizontal layout
      if (floatingMenu.buttonContainer) {
        floatingMenu.buttonContainer.style.cssText = `
          display: flex;
          flex-direction: row;
          gap: 4px;
          margin-top: 0;
        `;
        
        // Update all buttons to compact size
        const buttons = floatingMenu.buttonContainer.querySelectorAll('.overlay-button');
        buttons.forEach(btn => {
          btn.style.cssText = `
            background: ${btn.style.background};
            color: white;
            border: none;
            padding: 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 10px;
            font-weight: 500;
            transition: all 0.2s ease;
            position: relative;
            user-select: none;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 16px;
            height: 16px;
            min-width: 16px;
            min-height: 16px;
          `;
          
          // Hide text, show only icon
          const textSpan = btn.querySelector('span');
          if (textSpan) {
            textSpan.style.display = 'none';
          }
          
          // Hide handle in toolbar mode
          const handle = btn.querySelector('.button-handle');
          if (handle) {
            handle.style.display = 'none';
          }
        });
      }
      
      // Hide counter in toolbar mode
      if (floatingMenu.counter) {
        floatingMenu.counter.style.display = 'none';
      }
      
      // Update sidebar button
      if (sidebarElement && sidebarElement.toolbarToggleBtn) {
        sidebarElement.toolbarToggleBtn.textContent = '📱 Full Menu';
        sidebarElement.toolbarToggleBtn.style.background = '#4CAF50';
      }
      
    } else {
      // Switch back to full menu mode
      floatingMenu.style.cssText = `
        position: fixed;
        left: ${floatingMenuPosition.x}px;
        top: ${floatingMenuPosition.y}px;
        background: rgba(0, 0, 0, 0.8);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        padding: 16px;
        z-index: 10000;
        display: flex;
        flex-direction: column;
        gap: 8px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
        min-width: 200px;
        max-width: 280px;
        width: 280px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        resize: both;
        overflow: auto;
      `;
      
      // Update button container for vertical layout
      if (floatingMenu.buttonContainer) {
        floatingMenu.buttonContainer.style.cssText = `
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-top: 20px;
        `;
        
        // Update all buttons to full size
        const buttons = floatingMenu.buttonContainer.querySelectorAll('.overlay-button');
        buttons.forEach(btn => {
          btn.style.cssText = `
            background: ${btn.style.background};
            color: white;
            border: none;
            padding: 10px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.2s ease;
            position: relative;
            user-select: none;
            display: flex;
            align-items: center;
            gap: 8px;
            width: auto;
            height: auto;
            min-width: auto;
            min-height: auto;
          `;
          
          // Show text
          const textSpan = btn.querySelector('span');
          if (textSpan) {
            textSpan.style.display = 'inline';
          }
          
          // Show handle
          const handle = btn.querySelector('.button-handle');
          if (handle) {
            handle.style.display = 'inline';
          }
        });
      }
      
      // Show counter
      if (floatingMenu.counter) {
        floatingMenu.counter.style.display = 'block';
      }
      
      // Update sidebar button
      if (sidebarElement && sidebarElement.toolbarToggleBtn) {
        sidebarElement.toolbarToggleBtn.textContent = '📱 Toolbar';
        sidebarElement.toolbarToggleBtn.style.background = '#2196F3';
      }
    }
    
    // Ensure menu is visible
    floatingMenu.style.display = 'flex';
    
    // Save settings
    chrome.runtime.sendMessage({
      action: 'updateSettings',
      settings: settings
    });
  }
}

// Capture all images to sidebar
function captureAllImagesToSidebar() {
  if (!sidebarElement) return;
  
  const images = document.querySelectorAll('img');
  sidebarElement.content.innerHTML = '';
  
  images.forEach(img => {
    if (shouldCaptureImage(img)) {
      const item = createSidebarImageItem(img);
      sidebarElement.content.appendChild(item);
    }
  });
}

// Check if image should be captured
function shouldCaptureImage(img) {
  const minWidth = settings.minImageWidth || 100;
  const preferredTypes = settings.preferredFileTypes || ['jpg', 'jpeg', 'png'];
  
  if (img.naturalWidth < minWidth) return false;
  
  const url = img.src.toLowerCase();
  const hasPreferredType = preferredTypes.some(type => url.includes('.' + type));
  if (!hasPreferredType) return false;
  
  if (img.offsetParent === null) return false;
  
  return true;
}

// Create sidebar image item
function createSidebarImageItem(img) {
  const item = document.createElement('div');
  item.style.cssText = `
    border: 1px solid #ddd;
    border-radius: 4px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s ease;
  `;
  
  const imgElement = document.createElement('img');
  imgElement.src = img.src;
  imgElement.style.cssText = `
    width: 100%;
    height: auto;
    display: block;
  `;
  
  item.appendChild(imgElement);
  
  item.onclick = () => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      item.style.borderColor = '#ddd';
    } else {
      selectedImages.add(img.src);
      item.style.borderColor = '#4CAF50';
    }
    updateSelectionCounter();
  };
  
  return item;
}

// Toggle isolation mode
function toggleIsolationMode() {
  isolationMode = !isolationMode;
  
  if (isolationMode) {
    const images = document.querySelectorAll('img');
    const container = document.createElement('div');
    container.id = 'imagecapture-isolation';
    container.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: #000;
      z-index: 10000;
      overflow: auto;
      padding: 20px;
    `;
    
    const header = document.createElement('div');
    header.style.cssText = `
      position: sticky;
      top: 0;
      background: rgba(0, 0, 0, 0.8);
      color: white;
      padding: 16px;
      margin: -20px -20px 20px -20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    `;
    
    const closeBtn = document.createElement('button');
    closeBtn.textContent = '✕ Close';
    closeBtn.style.cssText = `
      background: #f44336;
      color: white;
      border: none;
      padding: 8px 12px;
      border-radius: 4px;
      cursor: pointer;
      font-weight: bold;
      font-size: 14px;
    `;
    closeBtn.onclick = () => toggleIsolationMode();
    
    header.innerHTML = '<h2>🖼️ Image Isolation Mode</h2>';
    header.appendChild(closeBtn);
    
    const grid = document.createElement('div');
    grid.style.cssText = `
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
    `;
    
    images.forEach(img => {
      if (shouldCaptureImage(img)) {
        const item = createIsolationImageItem(img);
        grid.appendChild(item);
      }
    });
    
    container.appendChild(header);
    container.appendChild(grid);
    document.body.appendChild(container);
  } else {
    const container = document.getElementById('imagecapture-isolation');
    if (container) {
      container.remove();
    }
  }
}

// Create isolation image item
function createIsolationImageItem(img) {
  const item = document.createElement('div');
  item.style.cssText = `
    border: 2px solid #333;
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s ease;
    background: #222;
  `;
  
  const imgElement = document.createElement('img');
  imgElement.src = img.src;
  imgElement.style.cssText = `
    width: 100%;
    height: auto;
    display: block;
  `;
  
  item.appendChild(imgElement);
  
  item.onclick = () => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      item.style.borderColor = '#333';
    } else {
      selectedImages.add(img.src);
      item.style.borderColor = '#4CAF50';
    }
    updateSelectionCounter();
  };
  
  return item;
}

// Show notification
function showNotification(message) {
  if (settings.showNotifications) {
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: #333;
      color: white;
      padding: 12px 20px;
      border-radius: 6px;
      z-index: 10001;
      font-size: 14px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
      notification.remove();
    }, 3000);
  }
}

// Handle keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  
  switch (e.key.toLowerCase()) {
    case 's':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        toggleSelectionMode();
      }
      break;
    case 'i':
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        captureAllImagesToSidebar();
      }
      break;
    case 'q':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        // Quick capture logic
      }
      break;
    case 'd':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        downloadSelectedImages();
      }
      break;
    case 'escape':
      if (selectionMode) {
        selectionMode = false;
        document.body.style.cursor = 'default';
        showNotification('Selection mode OFF');
      }
      break;
  }
});

// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'toggleOverlay':
      overlayMenuVisible = !overlayMenuVisible;
      if (floatingMenu) {
        floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
      }
      break;
      
    case 'updateSettings':
      const oldUseOverlayIcons = settings.useOverlayIcons;
      const oldShowSelectionIndicator = settings.showSelectionIndicator;
      
      settings = { ...settings, ...request.settings };
      
      // If overlay icons setting changed, refresh all image indicators
      if (oldUseOverlayIcons !== settings.useOverlayIcons || 
          oldShowSelectionIndicator !== settings.showSelectionIndicator) {
        addImageIndicators();
      }
      break;
      
    case 'updateFloatingMenuPosition':
      floatingMenuPosition = request.position;
      if (floatingMenu) {
        // Use absolute positioning
        floatingMenu.style.left = `${floatingMenuPosition.x}px`;
        floatingMenu.style.top = `${floatingMenuPosition.y}px`;
        floatingMenu.style.right = 'auto';
        if (floatingMenuPosition.width && !settings.quickToolbarMode) {
          floatingMenu.style.minWidth = `${floatingMenuPosition.width}px`;
        }
      }
      break;
      
    case 'captureImages':
      captureSelectedImages();
      break;
      
    case 'downloadImages':
      downloadSelectedImages();
      break;
      
    case 'toggleSelectionMode':
      toggleSelectionMode();
      break;
      
    case 'selectAllImages':
      selectAllImages();
      break;
      
    case 'deselectAllImages':
      deselectAllImages();
      break;
      
    case 'toggleSidebar':
      toggleSidebar();
      break;
      
    case 'toggleIsolationMode':
      toggleIsolationMode();
      break;
      
    case 'toggleQuickToolbar':
      toggleQuickToolbar();
      break;
      
    case 'toggleOverlayMenu':
      toggleOverlayMenu();
      break;
      
    case 'toggleSelectAll':
      toggleSelectAll();
      break;
      
    case 'captureSelectedImages':
      captureSelectedImages();
      break;
      
    case 'downloadSelectedImages':
      downloadSelectedImages();
      break;
      
    case 'clearCapturedImages':
      chrome.runtime.sendMessage({
        action: 'clearCapturedImages'
      });
      showNotification('Collection cleared');
      break;
      
    case 'imagesCleared':
      showNotification('Collection cleared');
      break;
  }
  
  sendResponse({ success: true });
}); 
```

```javascript
// Content script for ImageCapture extension
let selectionMode = false;
let selectedImages = new Set();
let sidebarVisible = false;
let sidebarElement = null;
let floatingMenu = null;
let isolationMode = false;
let overlayMenuVisible = false;
let overlayHoverTimer = null;
let floatingMenuPosition = { x: 20, y: 20, width: 280, height: 'auto' };
let settings = {
  hoverSelectDelay: 500,
  hoverDeselectDelay: 300,
  autoCaptureHover: false, // Disabled hover selection
  showNotifications: true,
  showSelectionIndicator: true,
  telegramEnabled: true,
  showFloatingMenu: true,
  minImageWidth: 100,
  preferredFileTypes: ['jpg', 'jpeg', 'png'],
  overlayHoverDelay: 1000,
      overlayButtons: ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'],
  overlayDraggable: true,
  quickToolbarMode: false,
  useOverlayIcons: false // New setting for toggleable selection indicators
};

// Load global state from background script
chrome.runtime.sendMessage({action: 'getGlobalState'}, (response) => {
  if (response && response.globalState) {
    const globalState = response.globalState;
    settings = { ...settings, ...globalState.settings };
    overlayMenuVisible = globalState.overlayVisible;
    selectedImages = new Set(globalState.selectedImages || []);
    floatingMenuPosition = globalState.floatingMenuPosition || { x: 20, y: 20, width: 280, height: 'auto' };
  }
});

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  addImageIndicators();
  createFloatingMenu();
  
  // Monitor for dynamically added images
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'childList') {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            const images = node.querySelectorAll('img');
            if (images.length > 0) {
              addImageIndicators();
            }
          }
        });
      }
    });
  });
  
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
});

// Also initialize if DOM is already loaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeExtension);
} else {
  initializeExtension();
}

function initializeExtension() {
  addImageIndicators();
  if (settings.showFloatingMenu) {
    createFloatingMenu();
  }
  
  // Add window resize handler to keep menu within bounds
  window.addEventListener('resize', handleWindowResize);
}

// Handle window resize to keep floating menu within viewport
function handleWindowResize() {
  if (!floatingMenu) return;
  
  const rect = floatingMenu.getBoundingClientRect();
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  
  let needsUpdate = false;
  let newX = floatingMenuPosition.x;
  let newY = floatingMenuPosition.y;
  
  // Check if menu is outside viewport - use absolute positioning
  if (rect.right > viewportWidth) {
    newX = Math.max(20, viewportWidth - rect.width - 20);
    needsUpdate = true;
  }
  
  if (rect.bottom > viewportHeight) {
    newY = Math.max(20, viewportHeight - rect.height - 20);
    needsUpdate = true;
  }
  
  if (rect.left < 0) {
    newX = 20; // Keep menu at minimum left position
    needsUpdate = true;
  }
  
  if (rect.top < 0) {
    newY = Math.min(viewportHeight - rect.height - 20, 20);
    needsUpdate = true;
  }
  
  if (needsUpdate) {
    floatingMenuPosition.x = newX;
    floatingMenuPosition.y = newY;
    
    // Use absolute positioning instead of right-based
    floatingMenu.style.left = `${newX}px`;
    floatingMenu.style.top = `${newY}px`;
    floatingMenu.style.right = 'auto';
    
    // Save updated position
    chrome.runtime.sendMessage({
      action: 'setFloatingMenuPosition',
      position: floatingMenuPosition
    });
  }
}

// Add visual indicators to images with enhanced styling
function addImageIndicators() {
  const images = document.querySelectorAll('img');
  
  images.forEach(img => {
    if (img.dataset.imagecaptureInitialized) return;
    
    img.dataset.imagecaptureInitialized = 'true';
    img.style.cursor = 'pointer';
    
    // Only show borders/overlays when selection mode is active
    if (selectionMode) {
      // Enhanced border styling with increased thickness and reduced opacity
      if (selectedImages.has(img.src)) {
        if (settings.useOverlayIcons) {
          addSelectionOverlay(img);
        } else {
          img.style.border = '10px solid rgba(76, 175, 80, 0.75)';
          img.style.borderRadius = '8px';
          img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
          img.style.boxShadow = '0 0 20px rgba(76, 175, 80, 0.5), inset 0 0 20px rgba(76, 175, 80, 0.2)';
        }
      } else {
        if (settings.useOverlayIcons) {
          addCheckboxOverlay(img);
        } else {
          img.style.border = '10px solid rgba(255, 107, 107, 0.5625)';
          img.style.borderRadius = '8px';
          img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
          img.style.boxShadow = '0 0 20px rgba(255, 107, 107, 0.375), inset 0 0 20px rgba(255, 107, 107, 0.15)';
        }
      }
    } else {
      // Clear any existing borders/overlays when selection mode is off
      if (settings.useOverlayIcons) {
        removeSelectionOverlay(img);
      } else {
        img.style.border = 'none';
        img.style.boxShadow = 'none';
      }
    }
    
    // Click event
    img.addEventListener('click', (e) => {
      if (selectionMode) {
        e.preventDefault();
        e.stopPropagation();
        toggleImageSelection(img);
      }
    });
    
    // Mouse 3 (middle click) event
    img.addEventListener('auxclick', (e) => {
      if (e.button === 1) {
        e.preventDefault();
        e.stopPropagation();
        handleImageAuxClick(e);
      }
    });
  });
}

// Add selection overlay icon
function addSelectionOverlay(img) {
  // Remove any existing overlay
  removeSelectionOverlay(img);
  
  // Create overlay container
  const overlay = document.createElement('div');
  overlay.className = 'imagecapture-selection-overlay';
  overlay.style.cssText = `
    position: absolute;
    top: 10px;
    right: 10px;
    width: 30px;
    height: 30px;
    background: #4CAF50;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 18px;
    font-weight: bold;
    z-index: 1000;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  `;
  overlay.innerHTML = '✓';
  
  // Ensure img has relative positioning
  if (img.style.position !== 'relative' && img.style.position !== 'absolute') {
    img.style.position = 'relative';
  }
  
  img.appendChild(overlay);
}

// Add checkbox overlay for unselected images
function addCheckboxOverlay(img) {
  // Remove any existing overlay
  removeSelectionOverlay(img);
  
  // Create checkbox overlay container
  const overlay = document.createElement('div');
  overlay.className = 'imagecapture-checkbox-overlay';
  overlay.style.cssText = `
    position: absolute;
    top: 10px;
    right: 10px;
    width: 30px;
    height: 30px;
    background: rgba(255, 255, 255, 0.9);
    border: 2px solid #ccc;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #666;
    font-size: 16px;
    font-weight: bold;
    z-index: 1000;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    cursor: pointer;
  `;
  overlay.innerHTML = '';
  
  // Add click handler to the checkbox
  overlay.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    toggleImageSelection(img);
  });
  
  // Ensure img has relative positioning
  if (img.style.position !== 'relative' && img.style.position !== 'absolute') {
    img.style.position = 'relative';
  }
  
  img.appendChild(overlay);
}

// Remove selection overlay icon
function removeSelectionOverlay(img) {
  const overlay = img.querySelector('.imagecapture-selection-overlay, .imagecapture-checkbox-overlay');
  if (overlay) {
    overlay.remove();
  }
}

// Handle image aux click (Mouse 3)
function handleImageAuxClick(e) {
  const img = e.target;
  const imageUrl = img.src;
  
  if (selectedImages.has(imageUrl)) {
    selectedImages.delete(imageUrl);
    animateImageSelection(img, false);
  } else {
    selectedImages.add(imageUrl);
    animateImageSelection(img, true);
  }
  
  updateSelectionCounter();
}

// Animate image selection with enhanced visual feedback
function animateImageSelection(img, isSelected) {
  if (isSelected) {
    if (settings.useOverlayIcons) {
      addSelectionOverlay(img);
    } else {
      img.style.border = '10px solid rgba(76, 175, 80, 0.75)';
      img.style.boxShadow = `
        0 0 20px rgba(76, 175, 80, 0.5), 
        inset 0 0 20px rgba(76, 175, 80, 0.2),
        0 0 40px rgba(76, 175, 80, 0.3),
        0 0 60px rgba(76, 175, 80, 0.1)
      `;
    }
    img.style.transform = 'scale(1.02)';
    img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
    
    setTimeout(() => {
      img.style.transform = 'scale(1)';
    }, 200);
  } else {
    if (settings.useOverlayIcons) {
      addCheckboxOverlay(img);
    } else {
      img.style.border = '10px solid rgba(255, 107, 107, 0.5625)';
      img.style.boxShadow = `
        0 0 20px rgba(255, 107, 107, 0.375), 
        inset 0 0 20px rgba(255, 107, 107, 0.15),
        0 0 40px rgba(255, 107, 107, 0.25),
        0 0 60px rgba(255, 107, 107, 0.1)
      `;
    }
    img.style.transform = 'scale(1)';
    img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
  }
}

// Remove border after download
function removeImageBorder(img) {
  if (settings.useOverlayIcons) {
    removeSelectionOverlay(img);
  } else {
    img.style.border = 'none';
    img.style.boxShadow = 'none';
  }
  img.style.transform = 'scale(1)';
}

// Toggle image selection
function toggleImageSelection(img) {
  const imageUrl = img.src;
  
  if (selectedImages.has(imageUrl)) {
    selectedImages.delete(imageUrl);
    animateImageSelection(img, false);
  } else {
    selectedImages.add(imageUrl);
    animateImageSelection(img, true);
  }
  
  updateSelectionCounter();
}

// Select all images
function selectAllImages() {
  const images = document.querySelectorAll('img');
  images.forEach(img => {
    if (shouldCaptureImage(img)) {
      selectedImages.add(img.src);
      animateImageSelection(img, true);
    }
  });
  updateSelectionCounter();
  showNotification(`Selected ${selectedImages.size} images`);
}

// Deselect all images
function deselectAllImages() {
  const images = document.querySelectorAll('img');
  images.forEach(img => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      animateImageSelection(img, false);
    }
  });
  updateSelectionCounter();
  showNotification('Deselected all images');
}

// Toggle select all/deselect all
function toggleSelectAll() {
  const images = document.querySelectorAll('img');
  const capturableImages = Array.from(images).filter(img => shouldCaptureImage(img));
  const selectedCapturableImages = capturableImages.filter(img => selectedImages.has(img.src));
  
  if (selectedCapturableImages.length === capturableImages.length) {
    deselectAllImages();
  } else {
    selectAllImages();
  }
}

// Capture selected images
function captureSelectedImages() {
  const imagesToCapture = Array.from(selectedImages);
  if (imagesToCapture.length === 0) {
    showNotification('No images selected to capture');
    return;
  }
  
  imagesToCapture.forEach(imageUrl => {
    chrome.runtime.sendMessage({
      action: 'captureImage',
      url: imageUrl,
      title: document.title
    });
    
    // Remove border after capture
    const img = document.querySelector(`img[src="${imageUrl}"]`);
    if (img) {
      removeImageBorder(img);
    }
  });
  
  selectedImages.clear();
  updateSelectionCounter();
  showNotification(`Captured ${imagesToCapture.length} images`);
}

// Update selection counter
function updateSelectionCounter() {
  if (floatingMenu && floatingMenu.counter) {
    floatingMenu.counter.textContent = `Selected: ${selectedImages.size}`;
  }
  if (sidebarElement && sidebarElement.counter) {
    sidebarElement.counter.textContent = `Selected: ${selectedImages.size}`;
  }
}

// Toggle selection mode
function toggleSelectionMode() {
  selectionMode = !selectionMode;
  
  if (selectionMode) {
    document.body.style.cursor = 'crosshair';
    showNotification('Selection mode ON - Click images to select');
  } else {
    document.body.style.cursor = 'default';
    showNotification('Selection mode OFF');
  }
  
  // Refresh image indicators to show/hide borders based on selection mode
  addImageIndicators();
  
  // Update floating menu button
  if (floatingMenu && floatingMenu.toggleBtn) {
    floatingMenu.toggleBtn.textContent = selectionMode ? '🎯 Selection: ON' : '🎯 Selection: OFF';
    floatingMenu.toggleBtn.style.background = selectionMode ? '#4CAF50' : '#ff9800';
    floatingMenu.toggleBtn.style.borderColor = selectionMode ? '#4CAF50' : 'transparent';
  }
  
  // Update sidebar button if exists
  if (sidebarElement && sidebarElement.toggleBtn) {
    sidebarElement.toggleBtn.textContent = selectionMode ? '🎯 Selection: ON' : '🎯 Selection: OFF';
    sidebarElement.toggleBtn.style.background = selectionMode ? '#4CAF50' : '#ff9800';
  }
}

// Toggle overlay menu visibility with hover delay
function toggleOverlayMenu() {
  if (settings.overlayHoverDelay > 0) {
    if (overlayHoverTimer) {
      clearTimeout(overlayHoverTimer);
      overlayHoverTimer = null;
    }
    
    overlayHoverTimer = setTimeout(() => {
      overlayMenuVisible = !overlayMenuVisible;
      
      if (floatingMenu) {
        floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
      }
      
      // Save state to background
      chrome.runtime.sendMessage({
        action: 'setOverlayVisible',
        visible: overlayMenuVisible
      });
      
      showNotification(overlayMenuVisible ? 'Overlay menu shown' : 'Overlay menu hidden');
    }, settings.overlayHoverDelay);
  } else {
    overlayMenuVisible = !overlayMenuVisible;
    
    if (floatingMenu) {
      floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
    }
    
    chrome.runtime.sendMessage({
      action: 'setOverlayVisible',
      visible: overlayMenuVisible
    });
    
    showNotification(overlayMenuVisible ? 'Overlay menu shown' : 'Overlay menu hidden');
  }
}

// Create draggable floating menu with customizable buttons
function createFloatingMenu() {
  if (floatingMenu) return;
  
  floatingMenu = document.createElement('div');
  floatingMenu.id = 'imagecapture-floating-menu';
  floatingMenu.style.cssText = `
    position: fixed;
    left: ${floatingMenuPosition.x}px;
    top: ${floatingMenuPosition.y}px;
    background: rgba(0, 0, 0, 0.8);
    backdrop-filter: blur(10px);
    border-radius: 12px;
    padding: 16px;
    z-index: 10000;
    display: flex;
    flex-direction: column;
    gap: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    transition: all 0.3s ease;
    min-width: 200px;
    max-width: 280px;
    width: 280px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    resize: both;
    overflow: auto;
  `;
  
  // Add drag handle
  const dragHandle = document.createElement('div');
  dragHandle.innerHTML = '⋮⋮';
  dragHandle.style.cssText = `
    position: absolute;
    top: 8px;
    left: 8px;
    color: rgba(255, 255, 255, 0.6);
    cursor: move;
    font-size: 14px;
    font-weight: bold;
    user-select: none;
  `;
  
  // Add close button
  const closeBtn = document.createElement('button');
  closeBtn.innerHTML = '✕';
  closeBtn.style.cssText = `
    position: absolute;
    top: 8px;
    right: 8px;
    background: #f44336;
    color: white;
    border: none;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    cursor: pointer;
    font-size: 12px;
    font-weight: bold;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10001;
    transition: all 0.2s ease;
  `;
  closeBtn.onmouseenter = () => {
    closeBtn.style.background = '#d32f2f';
    closeBtn.style.transform = 'scale(1.1)';
  };
  closeBtn.onmouseleave = () => {
    closeBtn.style.background = '#f44336';
    closeBtn.style.transform = 'scale(1)';
  };
  closeBtn.onclick = () => {
    floatingMenu.remove();
    floatingMenu = null;
  };
  
  // Create button container
  const buttonContainer = document.createElement('div');
  buttonContainer.style.cssText = `
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 20px;
  `;
  
  // Create buttons based on settings
  const buttonConfigs = {
    overlay: {
      text: '👁️ Overlay',
      color: '#607D8B',
      action: () => toggleOverlayMenu()
    },
    selection: {
      text: '🎯 Selection: OFF',
      color: '#ff9800',
      action: () => toggleSelectionMode()
    },
    selectAll: {
      text: '☑️ Select All',
      color: '#2196F3',
      action: () => toggleSelectAll()
    },
    sidebar: {
      text: '📱 Sidebar',
      color: '#2196F3',
      action: () => toggleSidebar()
    },
    isolation: {
      text: '🖼️ Image Mode',
      color: '#9C27B0',
      action: () => toggleIsolationMode()
    },
    capture: {
      text: '📸 Capture',
      color: '#4CAF50',
      action: () => captureSelectedImages()
    },
    viewCollection: {
      text: '📋 View Collection',
      color: '#3F51B5',
      action: () => openCollectionView()
    },
    download: {
      text: '📥 Download',
      color: '#FF9800',
      action: () => downloadSelectedImages()
    },
    quickToolbar: {
      text: '⚡ Quick Toolbar',
      color: '#E91E63',
      action: () => toggleQuickToolbar()
    }
  };
  
  const buttons = {};
  const buttonOrder = [...settings.overlayButtons];
  
  function createButtonElement(buttonType) {
    if (!buttonConfigs[buttonType]) return null;
    
    const config = buttonConfigs[buttonType];
    const btn = document.createElement('div');
    btn.className = 'overlay-button';
    btn.dataset.buttonType = buttonType;
    btn.style.cssText = `
      background: ${config.color};
      color: white;
      border: none;
      padding: 10px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 500;
      transition: all 0.2s ease;
      position: relative;
      user-select: none;
      display: flex;
      align-items: center;
      gap: 8px;
    `;
    
    // Add drag handle for reordering
    const handle = document.createElement('div');
    handle.innerHTML = '⋮';
    handle.className = 'button-handle';
    handle.style.cssText = `
      color: rgba(255, 255, 255, 0.6);
      cursor: move;
      font-size: 10px;
      font-weight: bold;
      user-select: none;
      padding: 2px;
    `;
    
    const textSpan = document.createElement('span');
    textSpan.textContent = config.text;
    
    btn.appendChild(handle);
    btn.appendChild(textSpan);
    
    // Add drag functionality for reordering
    makeButtonDraggable(btn, handle, buttonContainer);
    
    btn.onclick = (e) => {
      if (e.target !== handle) {
        config.action();
      }
    };
    
    btn.onmouseenter = () => {
      if (!btn.classList.contains('dragging')) {
        btn.style.transform = 'translateY(-1px)';
        btn.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.2)';
      }
    };
    
    btn.onmouseleave = () => {
      if (!btn.classList.contains('dragging')) {
        btn.style.transform = 'translateY(0)';
        btn.style.boxShadow = 'none';
      }
    };
    
    return btn;
  }
  
  // Create and add buttons in order
  buttonOrder.forEach(buttonType => {
    const btn = createButtonElement(buttonType);
    if (btn) {
      buttonContainer.appendChild(btn);
      buttons[buttonType] = btn;
    }
  });
  
  const counter = document.createElement('div');
  counter.textContent = 'Selected: 0';
  counter.style.cssText = `
    color: white;
    font-size: 11px;
    text-align: center;
    margin-top: 8px;
    padding: 4px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
  `;
  
  floatingMenu.appendChild(dragHandle);
  floatingMenu.appendChild(closeBtn);
  floatingMenu.appendChild(buttonContainer);
  floatingMenu.appendChild(counter);
  
  // Store references
  floatingMenu.toggleBtn = buttons.selection;
  floatingMenu.selectAllBtn = buttons.selectAll;
  floatingMenu.sidebarBtn = buttons.sidebar;
  floatingMenu.isolationBtn = buttons.isolation;
  floatingMenu.captureBtn = buttons.capture;
  floatingMenu.downloadBtn = buttons.download;
  floatingMenu.counter = counter;
  floatingMenu.buttonContainer = buttonContainer;
  
  // Add drag functionality for moving the menu
  if (settings.overlayDraggable) {
    makeDraggable(floatingMenu, dragHandle);
  }
  
  // Add resize observer to track manual resizing
  const resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      if (entry.target === floatingMenu) {
        const rect = entry.target.getBoundingClientRect();
        
        // Only update width and height, preserve current x and y positions
        // This prevents the menu from "jumping" when resizing from the right edge
        // Apply max-width constraint to prevent full-screen stretching
        const maxWidth = settings.quickToolbarMode ? 400 : 280;
        const constrainedWidth = Math.min(rect.width, maxWidth);
        
        const newPosition = {
          x: floatingMenuPosition.x, // Preserve current x position
          y: floatingMenuPosition.y, // Preserve current y position
          width: constrainedWidth,
          height: rect.height
        };
        
        // Only update if the size actually changed to prevent unnecessary updates
        if (newPosition.width !== floatingMenuPosition.width || 
            newPosition.height !== floatingMenuPosition.height) {
          
          floatingMenuPosition = newPosition;
          
          // Temporarily disable transitions during resize to prevent stretching effect
          const originalTransition = floatingMenu.style.transition;
          floatingMenu.style.transition = 'none';
          
          // Apply the constrained width to the element
          floatingMenu.style.width = `${constrainedWidth}px`;
          
          // Don't update min-width dynamically - this causes stretching issues
          // The min-width should remain fixed at the initial value
          
          // Re-enable transitions after a brief delay
          setTimeout(() => {
            floatingMenu.style.transition = originalTransition;
          }, 50);
          
          chrome.runtime.sendMessage({
            action: 'setFloatingMenuPosition',
            position: newPosition
          });
        }
      }
    }
  });
  resizeObserver.observe(floatingMenu);
  
  // Set initial visibility - ensure it's visible if overlayMenuVisible is true
  floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
  
  // Apply toolbar mode if enabled
  if (settings.quickToolbarMode) {
    toggleQuickToolbar();
  }
  
  document.body.appendChild(floatingMenu);
}

// Make element draggable
function makeDraggable(element, handle) {
  let isDragging = false;
  let currentX;
  let currentY;
  let initialX;
  let initialY;
  let xOffset = 0;
  let yOffset = 0;
  
  handle.addEventListener('mousedown', dragStart);
  document.addEventListener('mousemove', drag);
  document.addEventListener('mouseup', dragEnd);
  
  function dragStart(e) {
    // Only allow dragging if the target is the handle or its children
    if (e.target === handle || handle.contains(e.target)) {
      initialX = e.clientX - xOffset;
      initialY = e.clientY - yOffset;
      isDragging = true;
      e.preventDefault(); // Prevent text selection
    }
  }
  
  function drag(e) {
    if (isDragging) {
      e.preventDefault();
      
      currentX = e.clientX - initialX;
      currentY = e.clientY - initialY;
      
      xOffset = currentX;
      yOffset = currentY;
      
      setTranslate(currentX, currentY, element);
    }
  }
  
  function setTranslate(xPos, yPos, el) {
    el.style.transform = `translate3d(${xPos}px, ${yPos}px, 0)`;
  }
  
  function dragEnd(e) {
    initialX = currentX;
    initialY = currentY;
    isDragging = false;
    
    // Save position to background script - use absolute positioning
    const rect = element.getBoundingClientRect();
    const newPosition = {
      x: rect.left,
      y: rect.top,
      width: rect.width,
      height: rect.height
    };
    
    floatingMenuPosition = newPosition;
    
    // Reset transform and apply absolute positioning
    element.style.transform = 'none';
    element.style.left = `${newPosition.x}px`;
    element.style.top = `${newPosition.y}px`;
    
    chrome.runtime.sendMessage({
      action: 'setFloatingMenuPosition',
      position: newPosition
    });
  }
}

// Make button draggable for reordering
function makeButtonDraggable(button, handle, container) {
  let isDragging = false;
  let dragStartY = 0;
  let originalY = 0;
  let placeholder = null;
  
  handle.addEventListener('mousedown', (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    isDragging = true;
    dragStartY = e.clientY;
    originalY = button.offsetTop;
    
    // Create placeholder
    placeholder = document.createElement('div');
    placeholder.style.cssText = `
      height: ${button.offsetHeight}px;
      background: rgba(255, 255, 255, 0.1);
      border: 2px dashed rgba(255, 255, 255, 0.3);
      border-radius: 6px;
      margin: 4px 0;
    `;
    
    // Add dragging class
    button.classList.add('dragging');
    button.style.opacity = '0.8';
    button.style.transform = 'rotate(2deg) scale(1.02)';
    button.style.zIndex = '1000';
    
    // Insert placeholder
    container.insertBefore(placeholder, button);
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  });
  
  function handleMouseMove(e) {
    if (!isDragging) return;
    
    const deltaY = e.clientY - dragStartY;
    const newY = originalY + deltaY;
    
    // Find the new position
    const buttons = Array.from(container.children).filter(child => 
      child.classList.contains('overlay-button') && child !== button
    );
    
    let insertIndex = 0;
    for (let i = 0; i < buttons.length; i++) {
      const btn = buttons[i];
      const btnRect = btn.getBoundingClientRect();
      const btnCenter = btnRect.top + btnRect.height / 2;
      
      if (e.clientY < btnCenter) {
        insertIndex = i;
        break;
      }
      insertIndex = i + 1;
    }
    
    // Move placeholder
    const allButtons = Array.from(container.children).filter(child => 
      child.classList.contains('overlay-button') && child !== button
    );
    
    if (placeholder && allButtons.length > 0) {
      if (insertIndex >= allButtons.length) {
        container.appendChild(placeholder);
      } else {
        container.insertBefore(placeholder, allButtons[insertIndex]);
      }
    }
  }
  
  function handleMouseUp() {
    if (!isDragging) return;
    
    isDragging = false;
    
    // Remove dragging class
    button.classList.remove('dragging');
    button.style.opacity = '1';
    button.style.transform = 'rotate(0deg) scale(1)';
    button.style.zIndex = 'auto';
    
    // Move button to placeholder position
    if (placeholder && placeholder.parentNode) {
      placeholder.parentNode.insertBefore(button, placeholder);
      placeholder.remove();
    }
    
    // Update button order in settings
    updateButtonOrder();
    
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  }
}

// Update button order in settings
function updateButtonOrder() {
  if (!floatingMenu || !floatingMenu.buttonContainer) return;
  
  const buttons = Array.from(floatingMenu.buttonContainer.children)
    .filter(child => child.classList.contains('overlay-button'))
    .map(btn => btn.dataset.buttonType);
  
  settings.overlayButtons = buttons;
  
  // Save to background
  chrome.runtime.sendMessage({
    action: 'updateSettings',
    settings: { overlayButtons: buttons }
  });
}

// Download selected images
function downloadSelectedImages() {
  const imagesToDownload = Array.from(selectedImages);
  if (imagesToDownload.length === 0) {
    showNotification('No images selected to download');
    return;
  }
  
  showNotification(`Starting download of ${imagesToDownload.length} images...`);
  
  // Debug logging
  console.log('Downloading images:', imagesToDownload);
  
  chrome.runtime.sendMessage({
    action: 'downloadImages',
    images: imagesToDownload.map(url => ({ url, title: document.title }))
  }, (response) => {
    console.log('Download response:', response);
    if (response && response.success) {
      // Remove borders after download
      imagesToDownload.forEach(imageUrl => {
        const img = document.querySelector(`img[src="${imageUrl}"]`);
        if (img) {
          removeImageBorder(img);
        }
      });
      
      selectedImages.clear();
      updateSelectionCounter();
      showNotification(`Successfully downloaded ${response.downloaded || imagesToDownload.length} images to your browser's download folder`);
    } else {
      showNotification(`Failed to download images: ${response.error || 'Unknown error'}`);
    }
  });
}

// Create sidebar with enhanced features
function createSidebar() {
  if (sidebarElement) return;
  
  sidebarElement = document.createElement('div');
  sidebarElement.id = 'imagecapture-sidebar';
  sidebarElement.style.cssText = `
    position: fixed;
    top: 0;
    right: 0;
    width: 300px;
    height: 100vh;
    background: white;
    box-shadow: -2px 0 10px rgba(0, 0, 0, 0.3);
    z-index: 9999;
    display: flex;
    flex-direction: column;
    transition: width 0.3s ease;
    resize: horizontal;
    overflow: auto;
    min-width: 200px;
    max-width: 80vw;
  `;
  
  // Header
  const header = document.createElement('div');
  header.style.cssText = `
    background: #667eea;
    color: white;
    padding: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
  `;
  header.innerHTML = `
    <h3 style="margin: 0; font-size: 16px;">🖼️ ImageCapture Sidebar</h3>
    <button id="sidebar-close" style="background: #f44336; border: none; color: white; font-size: 18px; cursor: pointer; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">✕</button>
  `;
  
  // Controls
  const controls = document.createElement('div');
  controls.style.cssText = `
    padding: 12px;
    border-bottom: 1px solid #eee;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    flex-shrink: 0;
  `;
  
  const toggleBtn = document.createElement('button');
  toggleBtn.textContent = '🎯 Selection: OFF';
  toggleBtn.style.cssText = `
    background: #ff9800;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  toggleBtn.onclick = () => toggleSelectionMode();
  
  const selectAllBtn = document.createElement('button');
  selectAllBtn.textContent = '☑️ Select All';
  selectAllBtn.style.cssText = `
    background: #2196F3;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  selectAllBtn.onclick = () => toggleSelectAll();
  
  const refreshBtn = document.createElement('button');
  refreshBtn.textContent = '🔄 Refresh';
  refreshBtn.style.cssText = `
    background: #4CAF50;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  refreshBtn.onclick = () => refreshSidebar();
  
  const expandBtn = document.createElement('button');
  expandBtn.textContent = '📏 Expand';
  expandBtn.style.cssText = `
    background: #2196F3;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  expandBtn.onclick = () => toggleSidebarExpansion();
  
  const gridBtn = document.createElement('button');
  gridBtn.textContent = '🔲 Grid';
  gridBtn.style.cssText = `
    background: #9C27B0;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  gridBtn.onclick = () => toggleGridMode();
  
  const captureBtn = document.createElement('button');
  captureBtn.textContent = '📸 Capture All';
  captureBtn.style.cssText = `
    background: #4CAF50;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  captureBtn.onclick = () => captureAllImagesToSidebar();
  
  const downloadBtn = document.createElement('button');
  downloadBtn.textContent = '📥 Download Selected';
  downloadBtn.style.cssText = `
    background: #FF9800;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  downloadBtn.onclick = () => downloadSelectedImages();
  
  const isolationBtn = document.createElement('button');
  isolationBtn.textContent = '🖼️ Image Mode';
  isolationBtn.style.cssText = `
    background: #9C27B0;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  isolationBtn.onclick = () => toggleIsolationMode();
  
  const overlayToggleBtn = document.createElement('button');
  overlayToggleBtn.textContent = '👁️ Overlay Menu On/Off';
  overlayToggleBtn.style.cssText = `
    background: #607D8B;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  overlayToggleBtn.onclick = () => toggleOverlayMenu();
  
  const toolbarToggleBtn = document.createElement('button');
  toolbarToggleBtn.textContent = '⚡ Quick Toolbar';
  toolbarToggleBtn.style.cssText = `
    background: #FF5722;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  toolbarToggleBtn.onclick = () => toggleQuickToolbar();
  
  controls.appendChild(toggleBtn);
  controls.appendChild(selectAllBtn);
  controls.appendChild(refreshBtn);
  controls.appendChild(expandBtn);
  controls.appendChild(gridBtn);
  controls.appendChild(captureBtn);
  controls.appendChild(downloadBtn);
  controls.appendChild(isolationBtn);
  controls.appendChild(overlayToggleBtn);
  controls.appendChild(toolbarToggleBtn);
  
  // Counter
  const counter = document.createElement('div');
  counter.textContent = 'Selected: 0';
  counter.style.cssText = `
    padding: 8px 12px;
    background: #f5f5f5;
    border-bottom: 1px solid #eee;
    font-size: 12px;
    font-weight: 500;
    color: #333;
    flex-shrink: 0;
  `;
  
  // Content area
  const content = document.createElement('div');
  content.style.cssText = `
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    min-height: 0;
  `;
  
  sidebarElement.appendChild(header);
  sidebarElement.appendChild(controls);
  sidebarElement.appendChild(counter);
  sidebarElement.appendChild(content);
  
  // Store references
  sidebarElement.toggleBtn = toggleBtn;
  sidebarElement.selectAllBtn = selectAllBtn;
  sidebarElement.refreshBtn = refreshBtn;
  sidebarElement.expandBtn = expandBtn;
  sidebarElement.gridBtn = gridBtn;
  sidebarElement.overlayToggleBtn = overlayToggleBtn;
  sidebarElement.toolbarToggleBtn = toolbarToggleBtn;
  sidebarElement.counter = counter;
  sidebarElement.content = content;
  sidebarElement.isExpanded = false;
  sidebarElement.isGridMode = true;
  
  // Close button event
  header.querySelector('#sidebar-close').onclick = () => toggleSidebar();
  
  document.body.appendChild(sidebarElement);
}

// Refresh sidebar content
function refreshSidebar() {
  if (!sidebarElement) return;
  
  captureAllImagesToSidebar();
  showNotification('Sidebar refreshed');
}

// Toggle sidebar
function toggleSidebar() {
  if (sidebarVisible) {
    if (sidebarElement) {
      sidebarElement.remove();
      sidebarElement = null;
    }
    sidebarVisible = false;
  } else {
    createSidebar();
    sidebarVisible = true;
  }
}

// Toggle sidebar expansion
function toggleSidebarExpansion() {
  if (!sidebarElement) return;
  
  sidebarElement.isExpanded = !sidebarElement.isExpanded;
  
  if (sidebarElement.isExpanded) {
    sidebarElement.style.width = '66vw';
    sidebarElement.expandBtn.textContent = '📏 Collapse';
  } else {
    sidebarElement.style.width = '300px';
    sidebarElement.expandBtn.textContent = '📏 Expand';
  }
}

// Toggle grid mode
function toggleGridMode() {
  if (!sidebarElement) return;
  
  sidebarElement.isGridMode = !sidebarElement.isGridMode;
  
  if (sidebarElement.isGridMode) {
    sidebarElement.content.style.gridTemplateColumns = 'repeat(2, 1fr)';
    sidebarElement.gridBtn.textContent = '🔲 Grid';
  } else {
    sidebarElement.content.style.gridTemplateColumns = '1fr';
    sidebarElement.gridBtn.textContent = '📱 Single';
  }
}

// Toggle quick toolbar mode
function toggleQuickToolbar() {
  settings.quickToolbarMode = !settings.quickToolbarMode;
  
  if (floatingMenu) {
    if (settings.quickToolbarMode) {
      // Switch to toolbar mode
      floatingMenu.style.cssText = `
        position: fixed;
        left: ${floatingMenuPosition.x}px;
        top: ${floatingMenuPosition.y}px;
        background: rgba(0, 0, 0, 0.9);
        backdrop-filter: blur(10px);
        border-radius: 8px;
        padding: 8px;
        z-index: 10000;
        display: flex;
        flex-direction: row;
        gap: 4px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
        border: 1px solid rgba(255, 255, 255, 0.1);
        resize: both;
        overflow: auto;
        min-width: auto;
        max-width: 400px;
        width: auto;
        min-height: auto;
      `;
      
      // Update button container for horizontal layout
      if (floatingMenu.buttonContainer) {
        floatingMenu.buttonContainer.style.cssText = `
          display: flex;
          flex-direction: row;
          gap: 4px;
          margin-top: 0;
        `;
        
        // Update all buttons to compact size
        const buttons = floatingMenu.buttonContainer.querySelectorAll('.overlay-button');
        buttons.forEach(btn => {
          btn.style.cssText = `
            background: ${btn.style.background};
            color: white;
            border: none;
            padding: 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 10px;
            font-weight: 500;
            transition: all 0.2s ease;
            position: relative;
            user-select: none;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 16px;
            height: 16px;
            min-width: 16px;
            min-height: 16px;
          `;
          
          // Hide text, show only icon
          const textSpan = btn.querySelector('span');
          if (textSpan) {
            textSpan.style.display = 'none';
          }
          
          // Hide handle in toolbar mode
          const handle = btn.querySelector('.button-handle');
          if (handle) {
            handle.style.display = 'none';
          }
        });
      }
      
      // Hide counter in toolbar mode
      if (floatingMenu.counter) {
        floatingMenu.counter.style.display = 'none';
      }
      
      // Update sidebar button
      if (sidebarElement && sidebarElement.toolbarToggleBtn) {
        sidebarElement.toolbarToggleBtn.textContent = '📱 Full Menu';
        sidebarElement.toolbarToggleBtn.style.background = '#4CAF50';
      }
      
    } else {
      // Switch back to full menu mode
      floatingMenu.style.cssText = `
        position: fixed;
        left: ${floatingMenuPosition.x}px;
        top: ${floatingMenuPosition.y}px;
        background: rgba(0, 0, 0, 0.8);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        padding: 16px;
        z-index: 10000;
        display: flex;
        flex-direction: column;
        gap: 8px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
        min-width: 200px;
        max-width: 280px;
        width: 280px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        resize: both;
        overflow: auto;
      `;
      
      // Update button container for vertical layout
      if (floatingMenu.buttonContainer) {
        floatingMenu.buttonContainer.style.cssText = `
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-top: 20px;
        `;
        
        // Update all buttons to full size
        const buttons = floatingMenu.buttonContainer.querySelectorAll('.overlay-button');
        buttons.forEach(btn => {
          btn.style.cssText = `
            background: ${btn.style.background};
            color: white;
            border: none;
            padding: 10px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.2s ease;
            position: relative;
            user-select: none;
            display: flex;
            align-items: center;
            gap: 8px;
            width: auto;
            height: auto;
            min-width: auto;
            min-height: auto;
          `;
          
          // Show text
          const textSpan = btn.querySelector('span');
          if (textSpan) {
            textSpan.style.display = 'inline';
          }
          
          // Show handle
          const handle = btn.querySelector('.button-handle');
          if (handle) {
            handle.style.display = 'inline';
          }
        });
      }
      
      // Show counter
      if (floatingMenu.counter) {
        floatingMenu.counter.style.display = 'block';
      }
      
      // Update sidebar button
      if (sidebarElement && sidebarElement.toolbarToggleBtn) {
        sidebarElement.toolbarToggleBtn.textContent = '📱 Toolbar';
        sidebarElement.toolbarToggleBtn.style.background = '#2196F3';
      }
    }
    
    // Ensure menu is visible
    floatingMenu.style.display = 'flex';
    
    // Save settings
    chrome.runtime.sendMessage({
      action: 'updateSettings',
      settings: settings
    });
  }
}

// Capture all images to sidebar
function captureAllImagesToSidebar() {
  if (!sidebarElement) return;
  
  const images = document.querySelectorAll('img');
  sidebarElement.content.innerHTML = '';
  
  images.forEach(img => {
    if (shouldCaptureImage(img)) {
      const item = createSidebarImageItem(img);
      sidebarElement.content.appendChild(item);
    }
  });
}

// Check if image should be captured
function shouldCaptureImage(img) {
  const minWidth = settings.minImageWidth || 100;
  const preferredTypes = settings.preferredFileTypes || ['jpg', 'jpeg', 'png'];
  
  if (img.naturalWidth < minWidth) return false;
  
  const url = img.src.toLowerCase();
  const hasPreferredType = preferredTypes.some(type => url.includes('.' + type));
  if (!hasPreferredType) return false;
  
  if (img.offsetParent === null) return false;
  
  return true;
}

// Create sidebar image item
function createSidebarImageItem(img) {
  const item = document.createElement('div');
  item.style.cssText = `
    border: 1px solid #ddd;
    border-radius: 4px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s ease;
  `;
  
  const imgElement = document.createElement('img');
  imgElement.src = img.src;
  imgElement.style.cssText = `
    width: 100%;
    height: auto;
    display: block;
  `;
  
  item.appendChild(imgElement);
  
  item.onclick = () => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      item.style.borderColor = '#ddd';
    } else {
      selectedImages.add(img.src);
      item.style.borderColor = '#4CAF50';
    }
    updateSelectionCounter();
  };
  
  return item;
}

// Toggle isolation mode
function toggleIsolationMode() {
  isolationMode = !isolationMode;
  
  if (isolationMode) {
    const images = document.querySelectorAll('img');
    const container = document.createElement('div');
    container.id = 'imagecapture-isolation';
    container.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: #000;
      z-index: 10000;
      overflow: auto;
      padding: 20px;
    `;
    
    const header = document.createElement('div');
    header.style.cssText = `
      position: sticky;
      top: 0;
      background: rgba(0, 0, 0, 0.8);
      color: white;
      padding: 16px;
      margin: -20px -20px 20px -20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    `;
    
    const closeBtn = document.createElement('button');
    closeBtn.textContent = '✕ Close';
    closeBtn.style.cssText = `
      background: #f44336;
      color: white;
      border: none;
      padding: 8px 12px;
      border-radius: 4px;
      cursor: pointer;
      font-weight: bold;
      font-size: 14px;
    `;
    closeBtn.onclick = () => toggleIsolationMode();
    
    header.innerHTML = '<h2>🖼️ Image Isolation Mode</h2>';
    header.appendChild(closeBtn);
    
    const grid = document.createElement('div');
    grid.style.cssText = `
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
    `;
    
    images.forEach(img => {
      if (shouldCaptureImage(img)) {
        const item = createIsolationImageItem(img);
        grid.appendChild(item);
      }
    });
    
    container.appendChild(header);
    container.appendChild(grid);
    document.body.appendChild(container);
  } else {
    const container = document.getElementById('imagecapture-isolation');
    if (container) {
      container.remove();
    }
  }
}

// Create isolation image item
function createIsolationImageItem(img) {
  const item = document.createElement('div');
  item.style.cssText = `
    border: 2px solid #333;
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s ease;
    background: #222;
  `;
  
  const imgElement = document.createElement('img');
  imgElement.src = img.src;
  imgElement.style.cssText = `
    width: 100%;
    height: auto;
    display: block;
  `;
  
  item.appendChild(imgElement);
  
  item.onclick = () => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      item.style.borderColor = '#333';
    } else {
      selectedImages.add(img.src);
      item.style.borderColor = '#4CAF50';
    }
    updateSelectionCounter();
  };
  
  return item;
}

// Show notification
function showNotification(message) {
  if (settings.showNotifications) {
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: #333;
      color: white;
      padding: 12px 20px;
      border-radius: 6px;
      z-index: 10001;
      font-size: 14px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
      notification.remove();
    }, 3000);
  }
}

// Handle keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  
  switch (e.key.toLowerCase()) {
    case 's':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        toggleSelectionMode();
      }
      break;
    case 'i':
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        captureAllImagesToSidebar();
      }
      break;
    case 'q':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        // Quick capture logic
      }
      break;
    case 'd':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        downloadSelectedImages();
      }
      break;
    case 'escape':
      if (selectionMode) {
        selectionMode = false;
        document.body.style.cursor = 'default';
        showNotification('Selection mode OFF');
      }
      break;
  }
});

// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'toggleOverlay':
      overlayMenuVisible = !overlayMenuVisible;
      if (floatingMenu) {
        floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
      }
      break;
      
    case 'updateSettings':
      const oldUseOverlayIcons = settings.useOverlayIcons;
      const oldShowSelectionIndicator = settings.showSelectionIndicator;
      
      settings = { ...settings, ...request.settings };
      
      // If overlay icons setting changed, refresh all image indicators
      if (oldUseOverlayIcons !== settings.useOverlayIcons || 
          oldShowSelectionIndicator !== settings.showSelectionIndicator) {
        addImageIndicators();
      }
      break;
      
    case 'updateFloatingMenuPosition':
      floatingMenuPosition = request.position;
      if (floatingMenu) {
        // Use absolute positioning
        floatingMenu.style.left = `${floatingMenuPosition.x}px`;
        floatingMenu.style.top = `${floatingMenuPosition.y}px`;
        floatingMenu.style.right = 'auto';
        if (floatingMenuPosition.width && !settings.quickToolbarMode) {
          floatingMenu.style.minWidth = `${floatingMenuPosition.width}px`;
        }
      }
      break;
      
    case 'captureImages':
      captureSelectedImages();
      break;
      
    case 'downloadImages':
      downloadSelectedImages();
      break;
      
    case 'toggleSelectionMode':
      toggleSelectionMode();
      break;
      
    case 'selectAllImages':
      selectAllImages();
      break;
      
    case 'deselectAllImages':
      deselectAllImages();
      break;
      
    case 'toggleSidebar':
      toggleSidebar();
      break;
      
    case 'toggleIsolationMode':
      toggleIsolationMode();
      break;
      
    case 'toggleQuickToolbar':
      toggleQuickToolbar();
      break;
      
    case 'toggleOverlayMenu':
      toggleOverlayMenu();
      break;
      
    case 'toggleSelectAll':
      toggleSelectAll();
      break;
      
    case 'captureSelectedImages':
      captureSelectedImages();
      break;
      
    case 'downloadSelectedImages':
      downloadSelectedImages();
      break;
      
    case 'clearCapturedImages':
      chrome.runtime.sendMessage({
        action: 'clearCapturedImages'
      });
      showNotification('Collection cleared');
      break;
      
    case 'imagesCleared':
      showNotification('Collection cleared');
      break;
  }
  
  sendResponse({ success: true });
}); 
```

```javascript
// Content script for ImageCapture extension
let selectionMode = false;
let selectedImages = new Set();
let sidebarVisible = false;
let sidebarElement = null;
let floatingMenu = null;
let isolationMode = false;
let overlayMenuVisible = false;
let overlayHoverTimer = null;
let floatingMenuPosition = { x: 20, y: 20, width: 280, height: 'auto' };
let settings = {
  hoverSelectDelay: 500,
  hoverDeselectDelay: 300,
  autoCaptureHover: false, // Disabled hover selection
  showNotifications: true,
  showSelectionIndicator: true,
  telegramEnabled: true,
  showFloatingMenu: true,
  minImageWidth: 100,
  preferredFileTypes: ['jpg', 'jpeg', 'png'],
  overlayHoverDelay: 1000,
      overlayButtons: ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'],
  overlayDraggable: true,
  quickToolbarMode: false,
  useOverlayIcons: false // New setting for toggleable selection indicators
};

// Load global state from background script
chrome.runtime.sendMessage({action: 'getGlobalState'}, (response) => {
  if (response && response.globalState) {
    const globalState = response.globalState;
    settings = { ...settings, ...globalState.settings };
    overlayMenuVisible = globalState.overlayVisible;
    selectedImages = new Set(globalState.selectedImages || []);
    floatingMenuPosition = globalState.floatingMenuPosition || { x: 20, y: 20, width: 280, height: 'auto' };
  }
});

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  addImageIndicators();
  createFloatingMenu();
  
  // Monitor for dynamically added images
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'childList') {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            const images = node.querySelectorAll('img');
            if (images.length > 0) {
              addImageIndicators();
            }
          }
        });
      }
    });
  });
  
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
});

// Also initialize if DOM is already loaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeExtension);
} else {
  initializeExtension();
}

function initializeExtension() {
  addImageIndicators();
  if (settings.showFloatingMenu) {
    createFloatingMenu();
  }
  
  // Add window resize handler to keep menu within bounds
  window.addEventListener('resize', handleWindowResize);
}

// Handle window resize to keep floating menu within viewport
function handleWindowResize() {
  if (!floatingMenu) return;
  
  const rect = floatingMenu.getBoundingClientRect();
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  
  let needsUpdate = false;
  let newX = floatingMenuPosition.x;
  let newY = floatingMenuPosition.y;
  
  // Check if menu is outside viewport - use absolute positioning
  if (rect.right > viewportWidth) {
    newX = Math.max(20, viewportWidth - rect.width - 20);
    needsUpdate = true;
  }
  
  if (rect.bottom > viewportHeight) {
    newY = Math.max(20, viewportHeight - rect.height - 20);
    needsUpdate = true;
  }
  
  if (rect.left < 0) {
    newX = 20; // Keep menu at minimum left position
    needsUpdate = true;
  }
  
  if (rect.top < 0) {
    newY = Math.min(viewportHeight - rect.height - 20, 20);
    needsUpdate = true;
  }
  
  if (needsUpdate) {
    floatingMenuPosition.x = newX;
    floatingMenuPosition.y = newY;
    
    // Use absolute positioning instead of right-based
    floatingMenu.style.left = `${newX}px`;
    floatingMenu.style.top = `${newY}px`;
    floatingMenu.style.right = 'auto';
    
    // Save updated position
    chrome.runtime.sendMessage({
      action: 'setFloatingMenuPosition',
      position: floatingMenuPosition
    });
  }
}

// Add visual indicators to images with enhanced styling
function addImageIndicators() {
  const images = document.querySelectorAll('img');
  
  images.forEach(img => {
    if (img.dataset.imagecaptureInitialized) return;
    
    img.dataset.imagecaptureInitialized = 'true';
    img.style.cursor = 'pointer';
    
    // Only show borders/overlays when selection mode is active
    if (selectionMode) {
      // Enhanced border styling with increased thickness and reduced opacity
      if (selectedImages.has(img.src)) {
        if (settings.useOverlayIcons) {
          addSelectionOverlay(img);
        } else {
          img.style.border = '10px solid rgba(76, 175, 80, 0.75)';
          img.style.borderRadius = '8px';
          img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
          img.style.boxShadow = '0 0 20px rgba(76, 175, 80, 0.5), inset 0 0 20px rgba(76, 175, 80, 0.2)';
        }
      } else {
        if (settings.useOverlayIcons) {
          addCheckboxOverlay(img);
        } else {
          img.style.border = '10px solid rgba(255, 107, 107, 0.5625)';
          img.style.borderRadius = '8px';
          img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
          img.style.boxShadow = '0 0 20px rgba(255, 107, 107, 0.375), inset 0 0 20px rgba(255, 107, 107, 0.15)';
        }
      }
    } else {
      // Clear any existing borders/overlays when selection mode is off
      if (settings.useOverlayIcons) {
        removeSelectionOverlay(img);
      } else {
        img.style.border = 'none';
        img.style.boxShadow = 'none';
      }
    }
    
    // Click event
    img.addEventListener('click', (e) => {
      if (selectionMode) {
        e.preventDefault();
        e.stopPropagation();
        toggleImageSelection(img);
      }
    });
    
    // Mouse 3 (middle click) event
    img.addEventListener('auxclick', (e) => {
      if (e.button === 1) {
        e.preventDefault();
        e.stopPropagation();
        handleImageAuxClick(e);
      }
    });
  });
}

// Add selection overlay icon
function addSelectionOverlay(img) {
  // Remove any existing overlay
  removeSelectionOverlay(img);
  
  // Create overlay container
  const overlay = document.createElement('div');
  overlay.className = 'imagecapture-selection-overlay';
  overlay.style.cssText = `
    position: absolute;
    top: 10px;
    right: 10px;
    width: 30px;
    height: 30px;
    background: #4CAF50;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 18px;
    font-weight: bold;
    z-index: 1000;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  `;
  overlay.innerHTML = '✓';
  
  // Ensure img has relative positioning
  if (img.style.position !== 'relative' && img.style.position !== 'absolute') {
    img.style.position = 'relative';
  }
  
  img.appendChild(overlay);
}

// Add checkbox overlay for unselected images
function addCheckboxOverlay(img) {
  // Remove any existing overlay
  removeSelectionOverlay(img);
  
  // Create checkbox overlay container
  const overlay = document.createElement('div');
  overlay.className = 'imagecapture-checkbox-overlay';
  overlay.style.cssText = `
    position: absolute;
    top: 10px;
    right: 10px;
    width: 30px;
    height: 30px;
    background: rgba(255, 255, 255, 0.9);
    border: 2px solid #ccc;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #666;
    font-size: 16px;
    font-weight: bold;
    z-index: 1000;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    cursor: pointer;
  `;
  overlay.innerHTML = '';
  
  // Add click handler to the checkbox
  overlay.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    toggleImageSelection(img);
  });
  
  // Ensure img has relative positioning
  if (img.style.position !== 'relative' && img.style.position !== 'absolute') {
    img.style.position = 'relative';
  }
  
  img.appendChild(overlay);
}

// Remove selection overlay icon
function removeSelectionOverlay(img) {
  const overlay = img.querySelector('.imagecapture-selection-overlay, .imagecapture-checkbox-overlay');
  if (overlay) {
    overlay.remove();
  }
}

// Handle image aux click (Mouse 3)
function handleImageAuxClick(e) {
  const img = e.target;
  const imageUrl = img.src;
  
  if (selectedImages.has(imageUrl)) {
    selectedImages.delete(imageUrl);
    animateImageSelection(img, false);
  } else {
    selectedImages.add(imageUrl);
    animateImageSelection(img, true);
  }
  
  updateSelectionCounter();
}

// Animate image selection with enhanced visual feedback
function animateImageSelection(img, isSelected) {
  if (isSelected) {
    if (settings.useOverlayIcons) {
      addSelectionOverlay(img);
    } else {
      img.style.border = '10px solid rgba(76, 175, 80, 0.75)';
      img.style.boxShadow = `
        0 0 20px rgba(76, 175, 80, 0.5), 
        inset 0 0 20px rgba(76, 175, 80, 0.2),
        0 0 40px rgba(76, 175, 80, 0.3),
        0 0 60px rgba(76, 175, 80, 0.1)
      `;
    }
    img.style.transform = 'scale(1.02)';
    img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
    
    setTimeout(() => {
      img.style.transform = 'scale(1)';
    }, 200);
  } else {
    if (settings.useOverlayIcons) {
      addCheckboxOverlay(img);
    } else {
      img.style.border = '10px solid rgba(255, 107, 107, 0.5625)';
      img.style.boxShadow = `
        0 0 20px rgba(255, 107, 107, 0.375), 
        inset 0 0 20px rgba(255, 107, 107, 0.15),
        0 0 40px rgba(255, 107, 107, 0.25),
        0 0 60px rgba(255, 107, 107, 0.1)
      `;
    }
    img.style.transform = 'scale(1)';
    img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
  }
}

// Remove border after download
function removeImageBorder(img) {
  if (settings.useOverlayIcons) {
    removeSelectionOverlay(img);
  } else {
    img.style.border = 'none';
    img.style.boxShadow = 'none';
  }
  img.style.transform = 'scale(1)';
}

// Toggle image selection
function toggleImageSelection(img) {
  const imageUrl = img.src;
  
  if (selectedImages.has(imageUrl)) {
    selectedImages.delete(imageUrl);
    animateImageSelection(img, false);
  } else {
    selectedImages.add(imageUrl);
    animateImageSelection(img, true);
  }
  
  updateSelectionCounter();
}

// Select all images
function selectAllImages() {
  const images = document.querySelectorAll('img');
  images.forEach(img => {
    if (shouldCaptureImage(img)) {
      selectedImages.add(img.src);
      animateImageSelection(img, true);
    }
  });
  updateSelectionCounter();
  showNotification(`Selected ${selectedImages.size} images`);
}

// Deselect all images
function deselectAllImages() {
  const images = document.querySelectorAll('img');
  images.forEach(img => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      animateImageSelection(img, false);
    }
  });
  updateSelectionCounter();
  showNotification('Deselected all images');
}

// Toggle select all/deselect all
function toggleSelectAll() {
  const images = document.querySelectorAll('img');
  const capturableImages = Array.from(images).filter(img => shouldCaptureImage(img));
  const selectedCapturableImages = capturableImages.filter(img => selectedImages.has(img.src));
  
  if (selectedCapturableImages.length === capturableImages.length) {
    deselectAllImages();
  } else {
    selectAllImages();
  }
}

// Capture selected images
function captureSelectedImages() {
  const imagesToCapture = Array.from(selectedImages);
  if (imagesToCapture.length === 0) {
    showNotification('No images selected to capture');
    return;
  }
  
  imagesToCapture.forEach(imageUrl => {
    chrome.runtime.sendMessage({
      action: 'captureImage',
      url: imageUrl,
      title: document.title
    });
    
    // Remove border after capture
    const img = document.querySelector(`img[src="${imageUrl}"]`);
    if (img) {
      removeImageBorder(img);
    }
  });
  
  selectedImages.clear();
  updateSelectionCounter();
  showNotification(`Captured ${imagesToCapture.length} images`);
}

// Update selection counter
function updateSelectionCounter() {
  if (floatingMenu && floatingMenu.counter) {
    floatingMenu.counter.textContent = `Selected: ${selectedImages.size}`;
  }
  if (sidebarElement && sidebarElement.counter) {
    sidebarElement.counter.textContent = `Selected: ${selectedImages.size}`;
  }
}

// Toggle selection mode
function toggleSelectionMode() {
  selectionMode = !selectionMode;
  
  if (selectionMode) {
    document.body.style.cursor = 'crosshair';
    showNotification('Selection mode ON - Click images to select');
  } else {
    document.body.style.cursor = 'default';
    showNotification('Selection mode OFF');
  }
  
  // Refresh image indicators to show/hide borders based on selection mode
  addImageIndicators();
  
  // Update floating menu button
  if (floatingMenu && floatingMenu.toggleBtn) {
    floatingMenu.toggleBtn.textContent = selectionMode ? '🎯 Selection: ON' : '🎯 Selection: OFF';
    floatingMenu.toggleBtn.style.background = selectionMode ? '#4CAF50' : '#ff9800';
    floatingMenu.toggleBtn.style.borderColor = selectionMode ? '#4CAF50' : 'transparent';
  }
  
  // Update sidebar button if exists
  if (sidebarElement && sidebarElement.toggleBtn) {
    sidebarElement.toggleBtn.textContent = selectionMode ? '🎯 Selection: ON' : '🎯 Selection: OFF';
    sidebarElement.toggleBtn.style.background = selectionMode ? '#4CAF50' : '#ff9800';
  }
}

// Toggle overlay menu visibility with hover delay
function toggleOverlayMenu() {
  if (settings.overlayHoverDelay > 0) {
    if (overlayHoverTimer) {
      clearTimeout(overlayHoverTimer);
      overlayHoverTimer = null;
    }
    
    overlayHoverTimer = setTimeout(() => {
      overlayMenuVisible = !overlayMenuVisible;
      
      if (floatingMenu) {
        floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
      }
      
      // Save state to background
      chrome.runtime.sendMessage({
        action: 'setOverlayVisible',
        visible: overlayMenuVisible
      });
      
      showNotification(overlayMenuVisible ? 'Overlay menu shown' : 'Overlay menu hidden');
    }, settings.overlayHoverDelay);
  } else {
    overlayMenuVisible = !overlayMenuVisible;
    
    if (floatingMenu) {
      floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
    }
    
    chrome.runtime.sendMessage({
      action: 'setOverlayVisible',
      visible: overlayMenuVisible
    });
    
    showNotification(overlayMenuVisible ? 'Overlay menu shown' : 'Overlay menu hidden');
  }
}

// Create draggable floating menu with customizable buttons
function createFloatingMenu() {
  if (floatingMenu) return;
  
  floatingMenu = document.createElement('div');
  floatingMenu.id = 'imagecapture-floating-menu';
  floatingMenu.style.cssText = `
    position: fixed;
    left: ${floatingMenuPosition.x}px;
    top: ${floatingMenuPosition.y}px;
    background: rgba(0, 0, 0, 0.8);
    backdrop-filter: blur(10px);
    border-radius: 12px;
    padding: 16px;
    z-index: 10000;
    display: flex;
    flex-direction: column;
    gap: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    transition: all 0.3s ease;
    min-width: 200px;
    max-width: 280px;
    width: 280px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    resize: both;
    overflow: auto;
  `;
  
  // Add drag handle
  const dragHandle = document.createElement('div');
  dragHandle.innerHTML = '⋮⋮';
  dragHandle.style.cssText = `
    position: absolute;
    top: 8px;
    left: 8px;
    color: rgba(255, 255, 255, 0.6);
    cursor: move;
    font-size: 14px;
    font-weight: bold;
    user-select: none;
  `;
  
  // Add close button
  const closeBtn = document.createElement('button');
  closeBtn.innerHTML = '✕';
  closeBtn.style.cssText = `
    position: absolute;
    top: 8px;
    right: 8px;
    background: #f44336;
    color: white;
    border: none;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    cursor: pointer;
    font-size: 12px;
    font-weight: bold;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10001;
    transition: all 0.2s ease;
  `;
  closeBtn.onmouseenter = () => {
    closeBtn.style.background = '#d32f2f';
    closeBtn.style.transform = 'scale(1.1)';
  };
  closeBtn.onmouseleave = () => {
    closeBtn.style.background = '#f44336';
    closeBtn.style.transform = 'scale(1)';
  };
  closeBtn.onclick = () => {
    floatingMenu.remove();
    floatingMenu = null;
  };
  
  // Create button container
  const buttonContainer = document.createElement('div');
  buttonContainer.style.cssText = `
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 20px;
  `;
  
  // Create buttons based on settings
  const buttonConfigs = {
    overlay: {
      text: '👁️ Overlay',
      color: '#607D8B',
      action: () => toggleOverlayMenu()
    },
    selection: {
      text: '🎯 Selection: OFF',
      color: '#ff9800',
      action: () => toggleSelectionMode()
    },
    selectAll: {
      text: '☑️ Select All',
      color: '#2196F3',
      action: () => toggleSelectAll()
    },
    sidebar: {
      text: '📱 Sidebar',
      color: '#2196F3',
      action: () => toggleSidebar()
    },
    isolation: {
      text: '🖼️ Image Mode',
      color: '#9C27B0',
      action: () => toggleIsolationMode()
    },
    capture: {
      text: '📸 Capture',
      color: '#4CAF50',
      action: () => captureSelectedImages()
    },
    viewCollection: {
      text: '📋 View Collection',
      color: '#3F51B5',
      action: () => openCollectionView()
    },
    download: {
      text: '📥 Download',
      color: '#FF9800',
      action: () => downloadSelectedImages()
    },
    quickToolbar: {
      text: '⚡ Quick Toolbar',
      color: '#E91E63',
      action: () => toggleQuickToolbar()
    }
  };
  
  const buttons = {};
  const buttonOrder = [...settings.overlayButtons];
  
  function createButtonElement(buttonType) {
    if (!buttonConfigs[buttonType]) return null;
    
    const config = buttonConfigs[buttonType];
    const btn = document.createElement('div');
    btn.className = 'overlay-button';
    btn.dataset.buttonType = buttonType;
    btn.style.cssText = `
      background: ${config.color};
      color: white;
      border: none;
      padding: 10px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 500;
      transition: all 0.2s ease;
      position: relative;
      user-select: none;
      display: flex;
      align-items: center;
      gap: 8px;
    `;
    
    // Add drag handle for reordering
    const handle = document.createElement('div');
    handle.innerHTML = '⋮';
    handle.className = 'button-handle';
    handle.style.cssText = `
      color: rgba(255, 255, 255, 0.6);
      cursor: move;
      font-size: 10px;
      font-weight: bold;
      user-select: none;
      padding: 2px;
    `;
    
    const textSpan = document.createElement('span');
    textSpan.textContent = config.text;
    
    btn.appendChild(handle);
    btn.appendChild(textSpan);
    
    // Add drag functionality for reordering
    makeButtonDraggable(btn, handle, buttonContainer);
    
    btn.onclick = (e) => {
      if (e.target !== handle) {
        config.action();
      }
    };
    
    btn.onmouseenter = () => {
      if (!btn.classList.contains('dragging')) {
        btn.style.transform = 'translateY(-1px)';
        btn.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.2)';
      }
    };
    
    btn.onmouseleave = () => {
      if (!btn.classList.contains('dragging')) {
        btn.style.transform = 'translateY(0)';
        btn.style.boxShadow = 'none';
      }
    };
    
    return btn;
  }
  
  // Create and add buttons in order
  buttonOrder.forEach(buttonType => {
    const btn = createButtonElement(buttonType);
    if (btn) {
      buttonContainer.appendChild(btn);
      buttons[buttonType] = btn;
    }
  });
  
  const counter = document.createElement('div');
  counter.textContent = 'Selected: 0';
  counter.style.cssText = `
    color: white;
    font-size: 11px;
    text-align: center;
    margin-top: 8px;
    padding: 4px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
  `;
  
  floatingMenu.appendChild(dragHandle);
  floatingMenu.appendChild(closeBtn);
  floatingMenu.appendChild(buttonContainer);
  floatingMenu.appendChild(counter);
  
  // Store references
  floatingMenu.toggleBtn = buttons.selection;
  floatingMenu.selectAllBtn = buttons.selectAll;
  floatingMenu.sidebarBtn = buttons.sidebar;
  floatingMenu.isolationBtn = buttons.isolation;
  floatingMenu.captureBtn = buttons.capture;
  floatingMenu.downloadBtn = buttons.download;
  floatingMenu.counter = counter;
  floatingMenu.buttonContainer = buttonContainer;
  
  // Add drag functionality for moving the menu
  if (settings.overlayDraggable) {
    makeDraggable(floatingMenu, dragHandle);
  }
  
  // Add resize observer to track manual resizing
  const resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      if (entry.target === floatingMenu) {
        const rect = entry.target.getBoundingClientRect();
        
        // Only update width and height, preserve current x and y positions
        // This prevents the menu from "jumping" when resizing from the right edge
        // Apply max-width constraint to prevent full-screen stretching
        const maxWidth = settings.quickToolbarMode ? 400 : 280;
        const constrainedWidth = Math.min(rect.width, maxWidth);
        
        const newPosition = {
          x: floatingMenuPosition.x, // Preserve current x position
          y: floatingMenuPosition.y, // Preserve current y position
          width: constrainedWidth,
          height: rect.height
        };
        
        // Only update if the size actually changed to prevent unnecessary updates
        if (newPosition.width !== floatingMenuPosition.width || 
            newPosition.height !== floatingMenuPosition.height) {
          
          floatingMenuPosition = newPosition;
          
          // Temporarily disable transitions during resize to prevent stretching effect
          const originalTransition = floatingMenu.style.transition;
          floatingMenu.style.transition = 'none';
          
          // Apply the constrained width to the element
          floatingMenu.style.width = `${constrainedWidth}px`;
          
          // Don't update min-width dynamically - this causes stretching issues
          // The min-width should remain fixed at the initial value
          
          // Re-enable transitions after a brief delay
          setTimeout(() => {
            floatingMenu.style.transition = originalTransition;
          }, 50);
          
          chrome.runtime.sendMessage({
            action: 'setFloatingMenuPosition',
            position: newPosition
          });
        }
      }
    }
  });
  resizeObserver.observe(floatingMenu);
  
  // Set initial visibility - ensure it's visible if overlayMenuVisible is true
  floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
  
  // Apply toolbar mode if enabled
  if (settings.quickToolbarMode) {
    toggleQuickToolbar();
  }
  
  document.body.appendChild(floatingMenu);
}

// Make element draggable
function makeDraggable(element, handle) {
  let isDragging = false;
  let currentX;
  let currentY;
  let initialX;
  let initialY;
  let xOffset = 0;
  let yOffset = 0;
  
  handle.addEventListener('mousedown', dragStart);
  document.addEventListener('mousemove', drag);
  document.addEventListener('mouseup', dragEnd);
  
  function dragStart(e) {
    // Only allow dragging if the target is the handle or its children
    if (e.target === handle || handle.contains(e.target)) {
      initialX = e.clientX - xOffset;
      initialY = e.clientY - yOffset;
      isDragging = true;
      e.preventDefault(); // Prevent text selection
    }
  }
  
  function drag(e) {
    if (isDragging) {
      e.preventDefault();
      
      currentX = e.clientX - initialX;
      currentY = e.clientY - initialY;
      
      xOffset = currentX;
      yOffset = currentY;
      
      setTranslate(currentX, currentY, element);
    }
  }
  
  function setTranslate(xPos, yPos, el) {
    el.style.transform = `translate3d(${xPos}px, ${yPos}px, 0)`;
  }
  
  function dragEnd(e) {
    initialX = currentX;
    initialY = currentY;
    isDragging = false;
    
    // Save position to background script - use absolute positioning
    const rect = element.getBoundingClientRect();
    const newPosition = {
      x: rect.left,
      y: rect.top,
      width: rect.width,
      height: rect.height
    };
    
    floatingMenuPosition = newPosition;
    
    // Reset transform and apply absolute positioning
    element.style.transform = 'none';
    element.style.left = `${newPosition.x}px`;
    element.style.top = `${newPosition.y}px`;
    
    chrome.runtime.sendMessage({
      action: 'setFloatingMenuPosition',
      position: newPosition
    });
  }
}

// Make button draggable for reordering
function makeButtonDraggable(button, handle, container) {
  let isDragging = false;
  let dragStartY = 0;
  let originalY = 0;
  let placeholder = null;
  
  handle.addEventListener('mousedown', (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    isDragging = true;
    dragStartY = e.clientY;
    originalY = button.offsetTop;
    
    // Create placeholder
    placeholder = document.createElement('div');
    placeholder.style.cssText = `
      height: ${button.offsetHeight}px;
      background: rgba(255, 255, 255, 0.1);
      border: 2px dashed rgba(255, 255, 255, 0.3);
      border-radius: 6px;
      margin: 4px 0;
    `;
    
    // Add dragging class
    button.classList.add('dragging');
    button.style.opacity = '0.8';
    button.style.transform = 'rotate(2deg) scale(1.02)';
    button.style.zIndex = '1000';
    
    // Insert placeholder
    container.insertBefore(placeholder, button);
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  });
  
  function handleMouseMove(e) {
    if (!isDragging) return;
    
    const deltaY = e.clientY - dragStartY;
    const newY = originalY + deltaY;
    
    // Find the new position
    const buttons = Array.from(container.children).filter(child => 
      child.classList.contains('overlay-button') && child !== button
    );
    
    let insertIndex = 0;
    for (let i = 0; i < buttons.length; i++) {
      const btn = buttons[i];
      const btnRect = btn.getBoundingClientRect();
      const btnCenter = btnRect.top + btnRect.height / 2;
      
      if (e.clientY < btnCenter) {
        insertIndex = i;
        break;
      }
      insertIndex = i + 1;
    }
    
    // Move placeholder
    const allButtons = Array.from(container.children).filter(child => 
      child.classList.contains('overlay-button') && child !== button
    );
    
    if (placeholder && allButtons.length > 0) {
      if (insertIndex >= allButtons.length) {
        container.appendChild(placeholder);
      } else {
        container.insertBefore(placeholder, allButtons[insertIndex]);
      }
    }
  }
  
  function handleMouseUp() {
    if (!isDragging) return;
    
    isDragging = false;
    
    // Remove dragging class
    button.classList.remove('dragging');
    button.style.opacity = '1';
    button.style.transform = 'rotate(0deg) scale(1)';
    button.style.zIndex = 'auto';
    
    // Move button to placeholder position
    if (placeholder && placeholder.parentNode) {
      placeholder.parentNode.insertBefore(button, placeholder);
      placeholder.remove();
    }
    
    // Update button order in settings
    updateButtonOrder();
    
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  }
}

// Update button order in settings
function updateButtonOrder() {
  if (!floatingMenu || !floatingMenu.buttonContainer) return;
  
  const buttons = Array.from(floatingMenu.buttonContainer.children)
    .filter(child => child.classList.contains('overlay-button'))
    .map(btn => btn.dataset.buttonType);
  
  settings.overlayButtons = buttons;
  
  // Save to background
  chrome.runtime.sendMessage({
    action: 'updateSettings',
    settings: { overlayButtons: buttons }
  });
}

// Download selected images
function downloadSelectedImages() {
  const imagesToDownload = Array.from(selectedImages);
  if (imagesToDownload.length === 0) {
    showNotification('No images selected to download');
    return;
  }
  
  showNotification(`Starting download of ${imagesToDownload.length} images...`);
  
  // Debug logging
  console.log('Downloading images:', imagesToDownload);
  
  chrome.runtime.sendMessage({
    action: 'downloadImages',
    images: imagesToDownload.map(url => ({ url, title: document.title }))
  }, (response) => {
    console.log('Download response:', response);
    if (response && response.success) {
      // Remove borders after download
      imagesToDownload.forEach(imageUrl => {
        const img = document.querySelector(`img[src="${imageUrl}"]`);
        if (img) {
          removeImageBorder(img);
        }
      });
      
      selectedImages.clear();
      updateSelectionCounter();
      showNotification(`Successfully downloaded ${response.downloaded || imagesToDownload.length} images to your browser's download folder`);
    } else {
      showNotification(`Failed to download images: ${response.error || 'Unknown error'}`);
    }
  });
}

function openCollectionView() {
  chrome.runtime.sendMessage({ action: 'viewCollection' }, (response) => {
    if (!response || !response.success) {
      showNotification(response && response.error ? response.error : 'Unable to open collection');
    }
  });
}

// Create sidebar with enhanced features
function createSidebar() {
  if (sidebarElement) return;
  
  sidebarElement = document.createElement('div');
  sidebarElement.id = 'imagecapture-sidebar';
  sidebarElement.style.cssText = `
    position: fixed;
    top: 0;
    right: 0;
    width: 300px;
    height: 100vh;
    background: white;
    box-shadow: -2px 0 10px rgba(0, 0, 0, 0.3);
    z-index: 9999;
    display: flex;
    flex-direction: column;
    transition: width 0.3s ease;
    resize: horizontal;
    overflow: auto;
    min-width: 200px;
    max-width: 80vw;
  `;
  
  // Header
  const header = document.createElement('div');
  header.style.cssText = `
    background: #667eea;
    color: white;
    padding: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
  `;
  header.innerHTML = `
    <h3 style="margin: 0; font-size: 16px;">🖼️ ImageCapture Sidebar</h3>
    <button id="sidebar-close" style="background: #f44336; border: none; color: white; font-size: 18px; cursor: pointer; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">✕</button>
  `;
  
  // Controls
  const controls = document.createElement('div');
  controls.style.cssText = `
    padding: 12px;
    border-bottom: 1px solid #eee;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    flex-shrink: 0;
  `;
  
  const toggleBtn = document.createElement('button');
  toggleBtn.textContent = '🎯 Selection: OFF';
  toggleBtn.style.cssText = `
    background: #ff9800;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  toggleBtn.onclick = () => toggleSelectionMode();
  
  const selectAllBtn = document.createElement('button');
  selectAllBtn.textContent = '☑️ Select All';
  selectAllBtn.style.cssText = `
    background: #2196F3;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  selectAllBtn.onclick = () => toggleSelectAll();
  
  const refreshBtn = document.createElement('button');
  refreshBtn.textContent = '🔄 Refresh';
  refreshBtn.style.cssText = `
    background: #4CAF50;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  refreshBtn.onclick = () => refreshSidebar();
  
  const expandBtn = document.createElement('button');
  expandBtn.textContent = '📏 Expand';
  expandBtn.style.cssText = `
    background: #2196F3;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  expandBtn.onclick = () => toggleSidebarExpansion();
  
  const gridBtn = document.createElement('button');
  gridBtn.textContent = '🔲 Grid';
  gridBtn.style.cssText = `
    background: #9C27B0;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  gridBtn.onclick = () => toggleGridMode();
  
  const captureBtn = document.createElement('button');
  captureBtn.textContent = '📸 Capture All';
  captureBtn.style.cssText = `
    background: #4CAF50;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  captureBtn.onclick = () => captureAllImagesToSidebar();
  
  const downloadBtn = document.createElement('button');
  downloadBtn.textContent = '📥 Download Selected';
  downloadBtn.style.cssText = `
    background: #FF9800;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  downloadBtn.onclick = () => downloadSelectedImages();
  
  const isolationBtn = document.createElement('button');
  isolationBtn.textContent = '🖼️ Image Mode';
  isolationBtn.style.cssText = `
    background: #9C27B0;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  isolationBtn.onclick = () => toggleIsolationMode();
  
  const overlayToggleBtn = document.createElement('button');
  overlayToggleBtn.textContent = '👁️ Overlay Menu On/Off';
  overlayToggleBtn.style.cssText = `
    background: #607D8B;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  overlayToggleBtn.onclick = () => toggleOverlayMenu();
  
  const toolbarToggleBtn = document.createElement('button');
  toolbarToggleBtn.textContent = '⚡ Quick Toolbar';
  toolbarToggleBtn.style.cssText = `
    background: #FF5722;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  toolbarToggleBtn.onclick = () => toggleQuickToolbar();
  
  controls.appendChild(toggleBtn);
  controls.appendChild(selectAllBtn);
  controls.appendChild(refreshBtn);
  controls.appendChild(expandBtn);
  controls.appendChild(gridBtn);
  controls.appendChild(captureBtn);
  controls.appendChild(downloadBtn);
  controls.appendChild(isolationBtn);
  controls.appendChild(overlayToggleBtn);
  controls.appendChild(toolbarToggleBtn);
  
  // Counter
  const counter = document.createElement('div');
  counter.textContent = 'Selected: 0';
  counter.style.cssText = `
    padding: 8px 12px;
    background: #f5f5f5;
    border-bottom: 1px solid #eee;
    font-size: 12px;
    font-weight: 500;
    color: #333;
    flex-shrink: 0;
  `;
  
  // Content area
  const content = document.createElement('div');
  content.style.cssText = `
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    min-height: 0;
  `;
  
  sidebarElement.appendChild(header);
  sidebarElement.appendChild(controls);
  sidebarElement.appendChild(counter);
  sidebarElement.appendChild(content);
  
  // Store references
  sidebarElement.toggleBtn = toggleBtn;
  sidebarElement.selectAllBtn = selectAllBtn;
  sidebarElement.refreshBtn = refreshBtn;
  sidebarElement.expandBtn = expandBtn;
  sidebarElement.gridBtn = gridBtn;
  sidebarElement.overlayToggleBtn = overlayToggleBtn;
  sidebarElement.toolbarToggleBtn = toolbarToggleBtn;
  sidebarElement.counter = counter;
  sidebarElement.content = content;
  sidebarElement.isExpanded = false;
  sidebarElement.isGridMode = true;
  
  // Close button event
  header.querySelector('#sidebar-close').onclick = () => toggleSidebar();
  
  document.body.appendChild(sidebarElement);
}

// Refresh sidebar content
function refreshSidebar() {
  if (!sidebarElement) return;
  
  captureAllImagesToSidebar();
  showNotification('Sidebar refreshed');
}

// Toggle sidebar
function toggleSidebar() {
  if (sidebarVisible) {
    if (sidebarElement) {
      sidebarElement.remove();
      sidebarElement = null;
    }
    sidebarVisible = false;
  } else {
    createSidebar();
    sidebarVisible = true;
  }
}

// Toggle sidebar expansion
function toggleSidebarExpansion() {
  if (!sidebarElement) return;
  
  sidebarElement.isExpanded = !sidebarElement.isExpanded;
  
  if (sidebarElement.isExpanded) {
    sidebarElement.style.width = '66vw';
    sidebarElement.expandBtn.textContent = '📏 Collapse';
  } else {
    sidebarElement.style.width = '300px';
    sidebarElement.expandBtn.textContent = '📏 Expand';
  }
}

// Toggle grid mode
function toggleGridMode() {
  if (!sidebarElement) return;
  
  sidebarElement.isGridMode = !sidebarElement.isGridMode;
  
  if (sidebarElement.isGridMode) {
    sidebarElement.content.style.gridTemplateColumns = 'repeat(2, 1fr)';
    sidebarElement.gridBtn.textContent = '🔲 Grid';
  } else {
    sidebarElement.content.style.gridTemplateColumns = '1fr';
    sidebarElement.gridBtn.textContent = '📱 Single';
  }
}

// Toggle quick toolbar mode
function toggleQuickToolbar() {
  settings.quickToolbarMode = !settings.quickToolbarMode;
  
  if (floatingMenu) {
    if (settings.quickToolbarMode) {
      // Switch to toolbar mode
      floatingMenu.style.cssText = `
        position: fixed;
        left: ${floatingMenuPosition.x}px;
        top: ${floatingMenuPosition.y}px;
        background: rgba(0, 0, 0, 0.9);
        backdrop-filter: blur(10px);
        border-radius: 8px;
        padding: 8px;
        z-index: 10000;
        display: flex;
        flex-direction: row;
        gap: 4px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
        border: 1px solid rgba(255, 255, 255, 0.1);
        resize: both;
        overflow: auto;
        min-width: auto;
        max-width: 400px;
        width: auto;
        min-height: auto;
      `;
      
      // Update button container for horizontal layout
      if (floatingMenu.buttonContainer) {
        floatingMenu.buttonContainer.style.cssText = `
          display: flex;
          flex-direction: row;
          gap: 4px;
          margin-top: 0;
        `;
        
        // Update all buttons to compact size
        const buttons = floatingMenu.buttonContainer.querySelectorAll('.overlay-button');
        buttons.forEach(btn => {
          btn.style.cssText = `
            background: ${btn.style.background};
            color: white;
            border: none;
            padding: 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 10px;
            font-weight: 500;
            transition: all 0.2s ease;
            position: relative;
            user-select: none;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 16px;
            height: 16px;
            min-width: 16px;
            min-height: 16px;
          `;
          
          // Hide text, show only icon
          const textSpan = btn.querySelector('span');
          if (textSpan) {
            textSpan.style.display = 'none';
          }
          
          // Hide handle in toolbar mode
          const handle = btn.querySelector('.button-handle');
          if (handle) {
            handle.style.display = 'none';
          }
        });
      }
      
      // Hide counter in toolbar mode
      if (floatingMenu.counter) {
        floatingMenu.counter.style.display = 'none';
      }
      
      // Update sidebar button
      if (sidebarElement && sidebarElement.toolbarToggleBtn) {
        sidebarElement.toolbarToggleBtn.textContent = '📱 Full Menu';
        sidebarElement.toolbarToggleBtn.style.background = '#4CAF50';
      }
      
    } else {
      // Switch back to full menu mode
      floatingMenu.style.cssText = `
        position: fixed;
        left: ${floatingMenuPosition.x}px;
        top: ${floatingMenuPosition.y}px;
        background: rgba(0, 0, 0, 0.8);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        padding: 16px;
        z-index: 10000;
        display: flex;
        flex-direction: column;
        gap: 8px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
        min-width: 200px;
        max-width: 280px;
        width: 280px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        resize: both;
        overflow: auto;
      `;
      
      // Update button container for vertical layout
      if (floatingMenu.buttonContainer) {
        floatingMenu.buttonContainer.style.cssText = `
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-top: 20px;
        `;
        
        // Update all buttons to full size
        const buttons = floatingMenu.buttonContainer.querySelectorAll('.overlay-button');
        buttons.forEach(btn => {
          btn.style.cssText = `
            background: ${btn.style.background};
            color: white;
            border: none;
            padding: 10px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.2s ease;
            position: relative;
            user-select: none;
            display: flex;
            align-items: center;
            gap: 8px;
            width: auto;
            height: auto;
            min-width: auto;
            min-height: auto;
          `;
          
          // Show text
          const textSpan = btn.querySelector('span');
          if (textSpan) {
            textSpan.style.display = 'inline';
          }
          
          // Show handle
          const handle = btn.querySelector('.button-handle');
          if (handle) {
            handle.style.display = 'inline';
          }
        });
      }
      
      // Show counter
      if (floatingMenu.counter) {
        floatingMenu.counter.style.display = 'block';
      }
      
      // Update sidebar button
      if (sidebarElement && sidebarElement.toolbarToggleBtn) {
        sidebarElement.toolbarToggleBtn.textContent = '📱 Toolbar';
        sidebarElement.toolbarToggleBtn.style.background = '#2196F3';
      }
    }
    
    // Ensure menu is visible
    floatingMenu.style.display = 'flex';
    
    // Save settings
    chrome.runtime.sendMessage({
      action: 'updateSettings',
      settings: settings
    });
  }
}

// Capture all images to sidebar
function captureAllImagesToSidebar() {
  if (!sidebarElement) return;
  
  const images = document.querySelectorAll('img');
  sidebarElement.content.innerHTML = '';
  
  images.forEach(img => {
    if (shouldCaptureImage(img)) {
      const item = createSidebarImageItem(img);
      sidebarElement.content.appendChild(item);
    }
  });
}

// Check if image should be captured
function shouldCaptureImage(img) {
  const minWidth = settings.minImageWidth || 100;
  const preferredTypes = settings.preferredFileTypes || ['jpg', 'jpeg', 'png'];
  
  if (img.naturalWidth < minWidth) return false;
  
  const url = img.src.toLowerCase();
  const hasPreferredType = preferredTypes.some(type => url.includes('.' + type));
  if (!hasPreferredType) return false;
  
  if (img.offsetParent === null) return false;
  
  return true;
}

// Create sidebar image item
function createSidebarImageItem(img) {
  const item = document.createElement('div');
  item.style.cssText = `
    border: 1px solid #ddd;
    border-radius: 4px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s ease;
  `;
  
  const imgElement = document.createElement('img');
  imgElement.src = img.src;
  imgElement.style.cssText = `
    width: 100%;
    height: auto;
    display: block;
  `;
  
  item.appendChild(imgElement);
  
  item.onclick = () => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      item.style.borderColor = '#ddd';
    } else {
      selectedImages.add(img.src);
      item.style.borderColor = '#4CAF50';
    }
    updateSelectionCounter();
  };
  
  return item;
}

// Toggle isolation mode
function toggleIsolationMode() {
  isolationMode = !isolationMode;
  
  if (isolationMode) {
    const images = document.querySelectorAll('img');
    const container = document.createElement('div');
    container.id = 'imagecapture-isolation';
    container.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: #000;
      z-index: 10000;
      overflow: auto;
      padding: 20px;
    `;
    
    const header = document.createElement('div');
    header.style.cssText = `
      position: sticky;
      top: 0;
      background: rgba(0, 0, 0, 0.8);
      color: white;
      padding: 16px;
      margin: -20px -20px 20px -20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    `;
    
    const closeBtn = document.createElement('button');
    closeBtn.textContent = '✕ Close';
    closeBtn.style.cssText = `
      background: #f44336;
      color: white;
      border: none;
      padding: 8px 12px;
      border-radius: 4px;
      cursor: pointer;
      font-weight: bold;
      font-size: 14px;
    `;
    closeBtn.onclick = () => toggleIsolationMode();
    
    header.innerHTML = '<h2>🖼️ Image Isolation Mode</h2>';
    header.appendChild(closeBtn);
    
    const grid = document.createElement('div');
    grid.style.cssText = `
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
    `;
    
    images.forEach(img => {
      if (shouldCaptureImage(img)) {
        const item = createIsolationImageItem(img);
        grid.appendChild(item);
      }
    });
    
    container.appendChild(header);
    container.appendChild(grid);
    document.body.appendChild(container);
  } else {
    const container = document.getElementById('imagecapture-isolation');
    if (container) {
      container.remove();
    }
  }
}

// Create isolation image item
function createIsolationImageItem(img) {
  const item = document.createElement('div');
  item.style.cssText = `
    border: 2px solid #333;
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s ease;
    background: #222;
  `;
  
  const imgElement = document.createElement('img');
  imgElement.src = img.src;
  imgElement.style.cssText = `
    width: 100%;
    height: auto;
    display: block;
  `;
  
  item.appendChild(imgElement);
  
  item.onclick = () => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      item.style.borderColor = '#333';
    } else {
      selectedImages.add(img.src);
      item.style.borderColor = '#4CAF50';
    }
    updateSelectionCounter();
  };
  
  return item;
}

// Show notification
function showNotification(message) {
  if (settings.showNotifications) {
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: #333;
      color: white;
      padding: 12px 20px;
      border-radius: 6px;
      z-index: 10001;
      font-size: 14px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
      notification.remove();
    }, 3000);
  }
}

// Handle keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  
  switch (e.key.toLowerCase()) {
    case 's':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        toggleSelectionMode();
      }
      break;
    case 'i':
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        captureAllImagesToSidebar();
      }
      break;
    case 'q':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        // Quick capture logic
      }
      break;
    case 'd':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        downloadSelectedImages();
      }
      break;
    case 'escape':
      if (selectionMode) {
        selectionMode = false;
        document.body.style.cursor = 'default';
        showNotification('Selection mode OFF');
      }
      break;
  }
});

// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'toggleOverlay':
      overlayMenuVisible = !overlayMenuVisible;
      if (floatingMenu) {
        floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
      }
      break;
      
    case 'updateSettings':
      const oldUseOverlayIcons = settings.useOverlayIcons;
      const oldShowSelectionIndicator = settings.showSelectionIndicator;
      
      settings = { ...settings, ...request.settings };
      
      // If overlay icons setting changed, refresh all image indicators
      if (oldUseOverlayIcons !== settings.useOverlayIcons || 
          oldShowSelectionIndicator !== settings.showSelectionIndicator) {
        addImageIndicators();
      }
      break;
      
    case 'updateFloatingMenuPosition':
      floatingMenuPosition = request.position;
      if (floatingMenu) {
        // Use absolute positioning
        floatingMenu.style.left = `${floatingMenuPosition.x}px`;
        floatingMenu.style.top = `${floatingMenuPosition.y}px`;
        floatingMenu.style.right = 'auto';
        if (floatingMenuPosition.width && !settings.quickToolbarMode) {
          floatingMenu.style.minWidth = `${floatingMenuPosition.width}px`;
        }
      }
      break;
      
    case 'captureImages':
      captureSelectedImages();
      break;
      
    case 'downloadImages':
      downloadSelectedImages();
      break;
      
    case 'toggleSelectionMode':
      toggleSelectionMode();
      break;
      
    case 'selectAllImages':
      selectAllImages();
      break;
      
    case 'deselectAllImages':
      deselectAllImages();
      break;
      
    case 'toggleSidebar':
      toggleSidebar();
      break;
      
    case 'toggleIsolationMode':
      toggleIsolationMode();
      break;
      
    case 'toggleQuickToolbar':
      toggleQuickToolbar();
      break;
      
    case 'toggleOverlayMenu':
      toggleOverlayMenu();
      break;
      
    case 'toggleSelectAll':
      toggleSelectAll();
      break;
      
    case 'captureSelectedImages':
      captureSelectedImages();
      break;
      
    case 'downloadSelectedImages':
      downloadSelectedImages();
      break;
      
    case 'clearCapturedImages':
      chrome.runtime.sendMessage({
        action: 'clearCapturedImages'
      });
      showNotification('Collection cleared');
      break;
      
    case 'imagesCleared':
      showNotification('Collection cleared');
      break;
  }
  
  sendResponse({ success: true });
}); 
```

```javascript
// Content script for ImageCapture extension
let selectionMode = false;
let selectedImages = new Set();
let sidebarVisible = false;
let sidebarElement = null;
let floatingMenu = null;
let isolationMode = false;
let overlayMenuVisible = false;
let overlayHoverTimer = null;
let floatingMenuPosition = { x: 20, y: 20, width: 280, height: 'auto' };
let settings = {
  hoverSelectDelay: 500,
  hoverDeselectDelay: 300,
  autoCaptureHover: false, // Disabled hover selection
  showNotifications: true,
  showSelectionIndicator: true,
  telegramEnabled: true,
  showFloatingMenu: true,
  minImageWidth: 100,
  preferredFileTypes: ['jpg', 'jpeg', 'png'],
  overlayHoverDelay: 1000,
      overlayButtons: ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'],
  overlayDraggable: true,
  quickToolbarMode: false,
  useOverlayIcons: false // New setting for toggleable selection indicators
};

// Load global state from background script
chrome.runtime.sendMessage({action: 'getGlobalState'}, (response) => {
  if (response && response.globalState) {
    const globalState = response.globalState;
    settings = { ...settings, ...globalState.settings };
    overlayMenuVisible = globalState.overlayVisible;
    selectedImages = new Set(globalState.selectedImages || []);
    floatingMenuPosition = globalState.floatingMenuPosition || { x: 20, y: 20, width: 280, height: 'auto' };
  }
});

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  addImageIndicators();
  createFloatingMenu();
  
  // Monitor for dynamically added images
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'childList') {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            const images = node.querySelectorAll('img');
            if (images.length > 0) {
              addImageIndicators();
            }
          }
        });
      }
    });
  });
  
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
});

// Also initialize if DOM is already loaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeExtension);
} else {
  initializeExtension();
}

function initializeExtension() {
  addImageIndicators();
  if (settings.showFloatingMenu) {
    createFloatingMenu();
  }
  
  // Add window resize handler to keep menu within bounds
  window.addEventListener('resize', handleWindowResize);
}

// Handle window resize to keep floating menu within viewport
function handleWindowResize() {
  if (!floatingMenu) return;
  
  const rect = floatingMenu.getBoundingClientRect();
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  
  let needsUpdate = false;
  let newX = floatingMenuPosition.x;
  let newY = floatingMenuPosition.y;
  
  // Check if menu is outside viewport - use absolute positioning
  if (rect.right > viewportWidth) {
    newX = Math.max(20, viewportWidth - rect.width - 20);
    needsUpdate = true;
  }
  
  if (rect.bottom > viewportHeight) {
    newY = Math.max(20, viewportHeight - rect.height - 20);
    needsUpdate = true;
  }
  
  if (rect.left < 0) {
    newX = 20; // Keep menu at minimum left position
    needsUpdate = true;
  }
  
  if (rect.top < 0) {
    newY = Math.min(viewportHeight - rect.height - 20, 20);
    needsUpdate = true;
  }
  
  if (needsUpdate) {
    floatingMenuPosition.x = newX;
    floatingMenuPosition.y = newY;
    
    // Use absolute positioning instead of right-based
    floatingMenu.style.left = `${newX}px`;
    floatingMenu.style.top = `${newY}px`;
    floatingMenu.style.right = 'auto';
    
    // Save updated position
    chrome.runtime.sendMessage({
      action: 'setFloatingMenuPosition',
      position: floatingMenuPosition
    });
  }
}

// Add visual indicators to images with enhanced styling
function addImageIndicators() {
  const images = document.querySelectorAll('img');
  
  images.forEach(img => {
    if (img.dataset.imagecaptureInitialized) return;
    
    img.dataset.imagecaptureInitialized = 'true';
    img.style.cursor = 'pointer';
    
    // Only show borders/overlays when selection mode is active
    if (selectionMode) {
      // Enhanced border styling with increased thickness and reduced opacity
      if (selectedImages.has(img.src)) {
        if (settings.useOverlayIcons) {
          addSelectionOverlay(img);
        } else {
          img.style.border = '10px solid rgba(76, 175, 80, 0.75)';
          img.style.borderRadius = '8px';
          img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
          img.style.boxShadow = '0 0 20px rgba(76, 175, 80, 0.5), inset 0 0 20px rgba(76, 175, 80, 0.2)';
        }
      } else {
        if (settings.useOverlayIcons) {
          addCheckboxOverlay(img);
        } else {
          img.style.border = '10px solid rgba(255, 107, 107, 0.5625)';
          img.style.borderRadius = '8px';
          img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
          img.style.boxShadow = '0 0 20px rgba(255, 107, 107, 0.375), inset 0 0 20px rgba(255, 107, 107, 0.15)';
        }
      }
    } else {
      // Clear any existing borders/overlays when selection mode is off
      if (settings.useOverlayIcons) {
        removeSelectionOverlay(img);
      } else {
        img.style.border = 'none';
        img.style.boxShadow = 'none';
      }
    }
    
    // Click event
    img.addEventListener('click', (e) => {
      if (selectionMode) {
        e.preventDefault();
        e.stopPropagation();
        toggleImageSelection(img);
      }
    });
    
    // Mouse 3 (middle click) event
    img.addEventListener('auxclick', (e) => {
      if (e.button === 1) {
        e.preventDefault();
        e.stopPropagation();
        handleImageAuxClick(e);
      }
    });
  });
}

// Add selection overlay icon
function addSelectionOverlay(img) {
  // Remove any existing overlay
  removeSelectionOverlay(img);
  
  // Create overlay container
  const overlay = document.createElement('div');
  overlay.className = 'imagecapture-selection-overlay';
  overlay.style.cssText = `
    position: absolute;
    top: 10px;
    right: 10px;
    width: 30px;
    height: 30px;
    background: #4CAF50;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 18px;
    font-weight: bold;
    z-index: 1000;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  `;
  overlay.innerHTML = '✓';
  
  // Ensure img has relative positioning
  if (img.style.position !== 'relative' && img.style.position !== 'absolute') {
    img.style.position = 'relative';
  }
  
  img.appendChild(overlay);
}

// Add checkbox overlay for unselected images
function addCheckboxOverlay(img) {
  // Remove any existing overlay
  removeSelectionOverlay(img);
  
  // Create checkbox overlay container
  const overlay = document.createElement('div');
  overlay.className = 'imagecapture-checkbox-overlay';
  overlay.style.cssText = `
    position: absolute;
    top: 10px;
    right: 10px;
    width: 30px;
    height: 30px;
    background: rgba(255, 255, 255, 0.9);
    border: 2px solid #ccc;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #666;
    font-size: 16px;
    font-weight: bold;
    z-index: 1000;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    cursor: pointer;
  `;
  overlay.innerHTML = '';
  
  // Add click handler to the checkbox
  overlay.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    toggleImageSelection(img);
  });
  
  // Ensure img has relative positioning
  if (img.style.position !== 'relative' && img.style.position !== 'absolute') {
    img.style.position = 'relative';
  }
  
  img.appendChild(overlay);
}

// Remove selection overlay icon
function removeSelectionOverlay(img) {
  const overlay = img.querySelector('.imagecapture-selection-overlay, .imagecapture-checkbox-overlay');
  if (overlay) {
    overlay.remove();
  }
}

// Handle image aux click (Mouse 3)
function handleImageAuxClick(e) {
  const img = e.target;
  const imageUrl = img.src;
  
  if (selectedImages.has(imageUrl)) {
    selectedImages.delete(imageUrl);
    animateImageSelection(img, false);
  } else {
    selectedImages.add(imageUrl);
    animateImageSelection(img, true);
  }
  
  updateSelectionCounter();
}

// Animate image selection with enhanced visual feedback
function animateImageSelection(img, isSelected) {
  if (isSelected) {
    if (settings.useOverlayIcons) {
      addSelectionOverlay(img);
    } else {
      img.style.border = '10px solid rgba(76, 175, 80, 0.75)';
      img.style.boxShadow = `
        0 0 20px rgba(76, 175, 80, 0.5), 
        inset 0 0 20px rgba(76, 175, 80, 0.2),
        0 0 40px rgba(76, 175, 80, 0.3),
        0 0 60px rgba(76, 175, 80, 0.1)
      `;
    }
    img.style.transform = 'scale(1.02)';
    img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
    
    setTimeout(() => {
      img.style.transform = 'scale(1)';
    }, 200);
  } else {
    if (settings.useOverlayIcons) {
      addCheckboxOverlay(img);
    } else {
      img.style.border = '10px solid rgba(255, 107, 107, 0.5625)';
      img.style.boxShadow = `
        0 0 20px rgba(255, 107, 107, 0.375), 
        inset 0 0 20px rgba(255, 107, 107, 0.15),
        0 0 40px rgba(255, 107, 107, 0.25),
        0 0 60px rgba(255, 107, 107, 0.1)
      `;
    }
    img.style.transform = 'scale(1)';
    img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
  }
}

// Remove border after download
function removeImageBorder(img) {
  if (settings.useOverlayIcons) {
    removeSelectionOverlay(img);
  } else {
    img.style.border = 'none';
    img.style.boxShadow = 'none';
  }
  img.style.transform = 'scale(1)';
}

// Toggle image selection
function toggleImageSelection(img) {
  const imageUrl = img.src;
  
  if (selectedImages.has(imageUrl)) {
    selectedImages.delete(imageUrl);
    animateImageSelection(img, false);
  } else {
    selectedImages.add(imageUrl);
    animateImageSelection(img, true);
  }
  
  updateSelectionCounter();
}

// Select all images
function selectAllImages() {
  const images = document.querySelectorAll('img');
  images.forEach(img => {
    if (shouldCaptureImage(img)) {
      selectedImages.add(img.src);
      animateImageSelection(img, true);
    }
  });
  updateSelectionCounter();
  showNotification(`Selected ${selectedImages.size} images`);
}

// Deselect all images
function deselectAllImages() {
  const images = document.querySelectorAll('img');
  images.forEach(img => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      animateImageSelection(img, false);
    }
  });
  updateSelectionCounter();
  showNotification('Deselected all images');
}

// Toggle select all/deselect all
function toggleSelectAll() {
  const images = document.querySelectorAll('img');
  const capturableImages = Array.from(images).filter(img => shouldCaptureImage(img));
  const selectedCapturableImages = capturableImages.filter(img => selectedImages.has(img.src));
  
  if (selectedCapturableImages.length === capturableImages.length) {
    deselectAllImages();
  } else {
    selectAllImages();
  }
}

// Capture selected images
function captureSelectedImages() {
  const imagesToCapture = Array.from(selectedImages);
  if (imagesToCapture.length === 0) {
    showNotification('No images selected to capture');
    return;
  }
  
  imagesToCapture.forEach(imageUrl => {
    chrome.runtime.sendMessage({
      action: 'captureImage',
      url: imageUrl,
      title: document.title
    });
    
    // Remove border after capture
    const img = document.querySelector(`img[src="${imageUrl}"]`);
    if (img) {
      removeImageBorder(img);
    }
  });
  
  selectedImages.clear();
  updateSelectionCounter();
  showNotification(`Captured ${imagesToCapture.length} images`);
}

// Update selection counter
function updateSelectionCounter() {
  if (floatingMenu && floatingMenu.counter) {
    floatingMenu.counter.textContent = `Selected: ${selectedImages.size}`;
  }
  if (sidebarElement && sidebarElement.counter) {
    sidebarElement.counter.textContent = `Selected: ${selectedImages.size}`;
  }
}

// Toggle selection mode
function toggleSelectionMode() {
  selectionMode = !selectionMode;
  
  if (selectionMode) {
    document.body.style.cursor = 'crosshair';
    showNotification('Selection mode ON - Click images to select');
  } else {
    document.body.style.cursor = 'default';
    showNotification('Selection mode OFF');
  }
  
  // Refresh image indicators to show/hide borders based on selection mode
  addImageIndicators();
  
  // Update floating menu button
  if (floatingMenu && floatingMenu.toggleBtn) {
    floatingMenu.toggleBtn.textContent = selectionMode ? '🎯 Selection: ON' : '🎯 Selection: OFF';
    floatingMenu.toggleBtn.style.background = selectionMode ? '#4CAF50' : '#ff9800';
    floatingMenu.toggleBtn.style.borderColor = selectionMode ? '#4CAF50' : 'transparent';
  }
  
  // Update sidebar button if exists
  if (sidebarElement && sidebarElement.toggleBtn) {
    sidebarElement.toggleBtn.textContent = selectionMode ? '🎯 Selection: ON' : '🎯 Selection: OFF';
    sidebarElement.toggleBtn.style.background = selectionMode ? '#4CAF50' : '#ff9800';
  }
}

// Toggle overlay menu visibility with hover delay
function toggleOverlayMenu() {
  if (settings.overlayHoverDelay > 0) {
    if (overlayHoverTimer) {
      clearTimeout(overlayHoverTimer);
      overlayHoverTimer = null;
    }
    
    overlayHoverTimer = setTimeout(() => {
      overlayMenuVisible = !overlayMenuVisible;
      
      if (floatingMenu) {
        floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
      }
      
      // Save state to background
      chrome.runtime.sendMessage({
        action: 'setOverlayVisible',
        visible: overlayMenuVisible
      });
      
      showNotification(overlayMenuVisible ? 'Overlay menu shown' : 'Overlay menu hidden');
    }, settings.overlayHoverDelay);
  } else {
    overlayMenuVisible = !overlayMenuVisible;
    
    if (floatingMenu) {
      floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
    }
    
    chrome.runtime.sendMessage({
      action: 'setOverlayVisible',
      visible: overlayMenuVisible
    });
    
    showNotification(overlayMenuVisible ? 'Overlay menu shown' : 'Overlay menu hidden');
  }
}

// Create draggable floating menu with customizable buttons
function createFloatingMenu() {
  if (floatingMenu) return;
  
  floatingMenu = document.createElement('div');
  floatingMenu.id = 'imagecapture-floating-menu';
  floatingMenu.style.cssText = `
    position: fixed;
    left: ${floatingMenuPosition.x}px;
    top: ${floatingMenuPosition.y}px;
    background: rgba(0, 0, 0, 0.8);
    backdrop-filter: blur(10px);
    border-radius: 12px;
    padding: 16px;
    z-index: 10000;
    display: flex;
    flex-direction: column;
    gap: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    transition: all 0.3s ease;
    min-width: 200px;
    max-width: 280px;
    width: 280px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    resize: both;
    overflow: auto;
  `;
  
  // Add drag handle
  const dragHandle = document.createElement('div');
  dragHandle.innerHTML = '⋮⋮';
  dragHandle.style.cssText = `
    position: absolute;
    top: 8px;
    left: 8px;
    color: rgba(255, 255, 255, 0.6);
    cursor: move;
    font-size: 14px;
    font-weight: bold;
    user-select: none;
  `;
  
  // Add close button
  const closeBtn = document.createElement('button');
  closeBtn.innerHTML = '✕';
  closeBtn.style.cssText = `
    position: absolute;
    top: 8px;
    right: 8px;
    background: #f44336;
    color: white;
    border: none;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    cursor: pointer;
    font-size: 12px;
    font-weight: bold;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10001;
    transition: all 0.2s ease;
  `;
  closeBtn.onmouseenter = () => {
    closeBtn.style.background = '#d32f2f';
    closeBtn.style.transform = 'scale(1.1)';
  };
  closeBtn.onmouseleave = () => {
    closeBtn.style.background = '#f44336';
    closeBtn.style.transform = 'scale(1)';
  };
  closeBtn.onclick = () => {
    floatingMenu.remove();
    floatingMenu = null;
  };
  
  // Create button container
  const buttonContainer = document.createElement('div');
  buttonContainer.style.cssText = `
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 20px;
  `;
  
  // Create buttons based on settings
  const buttonConfigs = {
    overlay: {
      text: '👁️ Overlay',
      color: '#607D8B',
      action: () => toggleOverlayMenu()
    },
    selection: {
      text: '🎯 Selection: OFF',
      color: '#ff9800',
      action: () => toggleSelectionMode()
    },
    selectAll: {
      text: '☑️ Select All',
      color: '#2196F3',
      action: () => toggleSelectAll()
    },
    sidebar: {
      text: '📱 Sidebar',
      color: '#2196F3',
      action: () => toggleSidebar()
    },
    isolation: {
      text: '🖼️ Image Mode',
      color: '#9C27B0',
      action: () => toggleIsolationMode()
    },
    capture: {
      text: '📸 Capture',
      color: '#4CAF50',
      action: () => captureSelectedImages()
    },
    viewCollection: {
      text: '📋 View Collection',
      color: '#3F51B5',
      action: () => openCollectionView()
    },
    download: {
      text: '📥 Download',
      color: '#FF9800',
      action: () => downloadSelectedImages()
    },
    quickToolbar: {
      text: '⚡ Quick Toolbar',
      color: '#E91E63',
      action: () => toggleQuickToolbar()
    }
  };
  
  const buttons = {};
  const buttonOrder = [...settings.overlayButtons];
  
  function createButtonElement(buttonType) {
    if (!buttonConfigs[buttonType]) return null;
    
    const config = buttonConfigs[buttonType];
    const btn = document.createElement('div');
    btn.className = 'overlay-button';
    btn.dataset.buttonType = buttonType;
    btn.style.cssText = `
      background: ${config.color};
      color: white;
      border: none;
      padding: 10px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 500;
      transition: all 0.2s ease;
      position: relative;
      user-select: none;
      display: flex;
      align-items: center;
      gap: 8px;
    `;
    
    // Add drag handle for reordering
    const handle = document.createElement('div');
    handle.innerHTML = '⋮';
    handle.className = 'button-handle';
    handle.style.cssText = `
      color: rgba(255, 255, 255, 0.6);
      cursor: move;
      font-size: 10px;
      font-weight: bold;
      user-select: none;
      padding: 2px;
    `;
    
    const textSpan = document.createElement('span');
    textSpan.textContent = config.text;
    
    btn.appendChild(handle);
    btn.appendChild(textSpan);
    
    // Add drag functionality for reordering
    makeButtonDraggable(btn, handle, buttonContainer);
    
    btn.onclick = (e) => {
      if (e.target !== handle) {
        config.action();
      }
    };
    
    btn.onmouseenter = () => {
      if (!btn.classList.contains('dragging')) {
        btn.style.transform = 'translateY(-1px)';
        btn.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.2)';
      }
    };
    
    btn.onmouseleave = () => {
      if (!btn.classList.contains('dragging')) {
        btn.style.transform = 'translateY(0)';
        btn.style.boxShadow = 'none';
      }
    };
    
    return btn;
  }
  
  // Create and add buttons in order
  buttonOrder.forEach(buttonType => {
    const btn = createButtonElement(buttonType);
    if (btn) {
      buttonContainer.appendChild(btn);
      buttons[buttonType] = btn;
    }
  });
  
  const counter = document.createElement('div');
  counter.textContent = 'Selected: 0';
  counter.style.cssText = `
    color: white;
    font-size: 11px;
    text-align: center;
    margin-top: 8px;
    padding: 4px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
  `;
  
  floatingMenu.appendChild(dragHandle);
  floatingMenu.appendChild(closeBtn);
  floatingMenu.appendChild(buttonContainer);
  floatingMenu.appendChild(counter);
  
  // Store references
  floatingMenu.toggleBtn = buttons.selection;
  floatingMenu.selectAllBtn = buttons.selectAll;
  floatingMenu.sidebarBtn = buttons.sidebar;
  floatingMenu.isolationBtn = buttons.isolation;
  floatingMenu.captureBtn = buttons.capture;
  floatingMenu.downloadBtn = buttons.download;
  floatingMenu.counter = counter;
  floatingMenu.buttonContainer = buttonContainer;
  
  // Add drag functionality for moving the menu
  if (settings.overlayDraggable) {
    makeDraggable(floatingMenu, dragHandle);
  }
  
  // Add resize observer to track manual resizing
  const resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      if (entry.target === floatingMenu) {
        const rect = entry.target.getBoundingClientRect();
        
        // Only update width and height, preserve current x and y positions
        // This prevents the menu from "jumping" when resizing from the right edge
        // Apply max-width constraint to prevent full-screen stretching
        const maxWidth = settings.quickToolbarMode ? 400 : 280;
        const constrainedWidth = Math.min(rect.width, maxWidth);
        
        const newPosition = {
          x: floatingMenuPosition.x, // Preserve current x position
          y: floatingMenuPosition.y, // Preserve current y position
          width: constrainedWidth,
          height: rect.height
        };
        
        // Only update if the size actually changed to prevent unnecessary updates
        if (newPosition.width !== floatingMenuPosition.width || 
            newPosition.height !== floatingMenuPosition.height) {
          
          floatingMenuPosition = newPosition;
          
          // Temporarily disable transitions during resize to prevent stretching effect
          const originalTransition = floatingMenu.style.transition;
          floatingMenu.style.transition = 'none';
          
          // Apply the constrained width to the element
          floatingMenu.style.width = `${constrainedWidth}px`;
          
          // Don't update min-width dynamically - this causes stretching issues
          // The min-width should remain fixed at the initial value
          
          // Re-enable transitions after a brief delay
          setTimeout(() => {
            floatingMenu.style.transition = originalTransition;
          }, 50);
          
          chrome.runtime.sendMessage({
            action: 'setFloatingMenuPosition',
            position: newPosition
          });
        }
      }
    }
  });
  resizeObserver.observe(floatingMenu);
  
  // Set initial visibility - ensure it's visible if overlayMenuVisible is true
  floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
  
  // Apply toolbar mode if enabled
  if (settings.quickToolbarMode) {
    toggleQuickToolbar();
  }
  
  document.body.appendChild(floatingMenu);
}

// Make element draggable
function makeDraggable(element, handle) {
  let isDragging = false;
  let currentX;
  let currentY;
  let initialX;
  let initialY;
  let xOffset = 0;
  let yOffset = 0;
  
  handle.addEventListener('mousedown', dragStart);
  document.addEventListener('mousemove', drag);
  document.addEventListener('mouseup', dragEnd);
  
  function dragStart(e) {
    // Only allow dragging if the target is the handle or its children
    if (e.target === handle || handle.contains(e.target)) {
      initialX = e.clientX - xOffset;
      initialY = e.clientY - yOffset;
      isDragging = true;
      e.preventDefault(); // Prevent text selection
    }
  }
  
  function drag(e) {
    if (isDragging) {
      e.preventDefault();
      
      currentX = e.clientX - initialX;
      currentY = e.clientY - initialY;
      
      xOffset = currentX;
      yOffset = currentY;
      
      setTranslate(currentX, currentY, element);
    }
  }
  
  function setTranslate(xPos, yPos, el) {
    el.style.transform = `translate3d(${xPos}px, ${yPos}px, 0)`;
  }
  
  function dragEnd(e) {
    initialX = currentX;
    initialY = currentY;
    isDragging = false;
    
    // Save position to background script - use absolute positioning
    const rect = element.getBoundingClientRect();
    const newPosition = {
      x: rect.left,
      y: rect.top,
      width: rect.width,
      height: rect.height
    };
    
    floatingMenuPosition = newPosition;
    
    // Reset transform and apply absolute positioning
    element.style.transform = 'none';
    element.style.left = `${newPosition.x}px`;
    element.style.top = `${newPosition.y}px`;
    
    chrome.runtime.sendMessage({
      action: 'setFloatingMenuPosition',
      position: newPosition
    });
  }
}

// Make button draggable for reordering
function makeButtonDraggable(button, handle, container) {
  let isDragging = false;
  let dragStartY = 0;
  let originalY = 0;
  let placeholder = null;
  
  handle.addEventListener('mousedown', (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    isDragging = true;
    dragStartY = e.clientY;
    originalY = button.offsetTop;
    
    // Create placeholder
    placeholder = document.createElement('div');
    placeholder.style.cssText = `
      height: ${button.offsetHeight}px;
      background: rgba(255, 255, 255, 0.1);
      border: 2px dashed rgba(255, 255, 255, 0.3);
      border-radius: 6px;
      margin: 4px 0;
    `;
    
    // Add dragging class
    button.classList.add('dragging');
    button.style.opacity = '0.8';
    button.style.transform = 'rotate(2deg) scale(1.02)';
    button.style.zIndex = '1000';
    
    // Insert placeholder
    container.insertBefore(placeholder, button);
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  });
  
  function handleMouseMove(e) {
    if (!isDragging) return;
    
    const deltaY = e.clientY - dragStartY;
    const newY = originalY + deltaY;
    
    // Find the new position
    const buttons = Array.from(container.children).filter(child => 
      child.classList.contains('overlay-button') && child !== button
    );
    
    let insertIndex = 0;
    for (let i = 0; i < buttons.length; i++) {
      const btn = buttons[i];
      const btnRect = btn.getBoundingClientRect();
      const btnCenter = btnRect.top + btnRect.height / 2;
      
      if (e.clientY < btnCenter) {
        insertIndex = i;
        break;
      }
      insertIndex = i + 1;
    }
    
    // Move placeholder
    const allButtons = Array.from(container.children).filter(child => 
      child.classList.contains('overlay-button') && child !== button
    );
    
    if (placeholder && allButtons.length > 0) {
      if (insertIndex >= allButtons.length) {
        container.appendChild(placeholder);
      } else {
        container.insertBefore(placeholder, allButtons[insertIndex]);
      }
    }
  }
  
  function handleMouseUp() {
    if (!isDragging) return;
    
    isDragging = false;
    
    // Remove dragging class
    button.classList.remove('dragging');
    button.style.opacity = '1';
    button.style.transform = 'rotate(0deg) scale(1)';
    button.style.zIndex = 'auto';
    
    // Move button to placeholder position
    if (placeholder && placeholder.parentNode) {
      placeholder.parentNode.insertBefore(button, placeholder);
      placeholder.remove();
    }
    
    // Update button order in settings
    updateButtonOrder();
    
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  }
}

// Update button order in settings
function updateButtonOrder() {
  if (!floatingMenu || !floatingMenu.buttonContainer) return;
  
  const buttons = Array.from(floatingMenu.buttonContainer.children)
    .filter(child => child.classList.contains('overlay-button'))
    .map(btn => btn.dataset.buttonType);
  
  settings.overlayButtons = buttons;
  
  // Save to background
  chrome.runtime.sendMessage({
    action: 'updateSettings',
    settings: { overlayButtons: buttons }
  });
}

// Download selected images
function downloadSelectedImages() {
  const imagesToDownload = Array.from(selectedImages);
  if (imagesToDownload.length === 0) {
    showNotification('No images selected to download');
    return;
  }
  
  showNotification(`Starting download of ${imagesToDownload.length} images...`);
  
  // Debug logging
  console.log('Downloading images:', imagesToDownload);
  
  chrome.runtime.sendMessage({
    action: 'downloadImages',
    images: imagesToDownload.map(url => ({ url, title: document.title }))
  }, (response) => {
    console.log('Download response:', response);
    if (response && response.success) {
      // Remove borders after download
      imagesToDownload.forEach(imageUrl => {
        const img = document.querySelector(`img[src="${imageUrl}"]`);
        if (img) {
          removeImageBorder(img);
        }
      });
      
      selectedImages.clear();
      updateSelectionCounter();
      showNotification(`Successfully downloaded ${response.downloaded || imagesToDownload.length} images to your browser's download folder`);
    } else {
      showNotification(`Failed to download images: ${response.error || 'Unknown error'}`);
    }
  });
}

function openCollectionView() {
  chrome.runtime.sendMessage({ action: 'viewCollection' }, (response) => {
    if (!response || !response.success) {
      showNotification(response && response.error ? response.error : 'Unable to open collection');
    }
  });
}

// Create sidebar with enhanced features
function createSidebar() {
  if (sidebarElement) return;
  
  sidebarElement = document.createElement('div');
  sidebarElement.id = 'imagecapture-sidebar';
  sidebarElement.style.cssText = `
    position: fixed;
    top: 0;
    right: 0;
    width: 300px;
    height: 100vh;
    background: white;
    box-shadow: -2px 0 10px rgba(0, 0, 0, 0.3);
    z-index: 9999;
    display: flex;
    flex-direction: column;
    transition: width 0.3s ease;
    resize: horizontal;
    overflow: auto;
    min-width: 200px;
    max-width: 80vw;
  `;
  
  // Header
  const header = document.createElement('div');
  header.style.cssText = `
    background: #667eea;
    color: white;
    padding: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
  `;
  header.innerHTML = `
    <h3 style="margin: 0; font-size: 16px;">🖼️ ImageCapture Sidebar</h3>
    <button id="sidebar-close" style="background: #f44336; border: none; color: white; font-size: 18px; cursor: pointer; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">✕</button>
  `;
  
  // Controls
  const controls = document.createElement('div');
  controls.style.cssText = `
    padding: 12px;
    border-bottom: 1px solid #eee;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    flex-shrink: 0;
  `;
  
  const toggleBtn = document.createElement('button');
  toggleBtn.textContent = '🎯 Selection: OFF';
  toggleBtn.style.cssText = `
    background: #ff9800;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  toggleBtn.onclick = () => toggleSelectionMode();
  
  const selectAllBtn = document.createElement('button');
  selectAllBtn.textContent = '☑️ Select All';
  selectAllBtn.style.cssText = `
    background: #2196F3;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  selectAllBtn.onclick = () => toggleSelectAll();
  
  const refreshBtn = document.createElement('button');
  refreshBtn.textContent = '🔄 Refresh';
  refreshBtn.style.cssText = `
    background: #4CAF50;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  refreshBtn.onclick = () => refreshSidebar();
  
  const expandBtn = document.createElement('button');
  expandBtn.textContent = '📏 Expand';
  expandBtn.style.cssText = `
    background: #2196F3;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  expandBtn.onclick = () => toggleSidebarExpansion();
  
  const gridBtn = document.createElement('button');
  gridBtn.textContent = '🔲 Grid';
  gridBtn.style.cssText = `
    background: #9C27B0;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  gridBtn.onclick = () => toggleGridMode();
  
  const captureBtn = document.createElement('button');
  captureBtn.textContent = '📸 Capture All';
  captureBtn.style.cssText = `
    background: #4CAF50;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  captureBtn.onclick = () => captureAllImagesToSidebar();
  
  const viewCollectionBtn = document.createElement('button');
  viewCollectionBtn.textContent = '📋 View Collection';
  viewCollectionBtn.style.cssText = `
    background: #3F51B5;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  viewCollectionBtn.onclick = () => openCollectionView();
  
  const downloadBtn = document.createElement('button');
  downloadBtn.textContent = '📥 Download Selected';
  downloadBtn.style.cssText = `
    background: #FF9800;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  downloadBtn.onclick = () => downloadSelectedImages();
  
  const isolationBtn = document.createElement('button');
  isolationBtn.textContent = '🖼️ Image Mode';
  isolationBtn.style.cssText = `
    background: #9C27B0;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  isolationBtn.onclick = () => toggleIsolationMode();
  
  const overlayToggleBtn = document.createElement('button');
  overlayToggleBtn.textContent = '👁️ Overlay Menu On/Off';
  overlayToggleBtn.style.cssText = `
    background: #607D8B;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  overlayToggleBtn.onclick = () => toggleOverlayMenu();
  
  const toolbarToggleBtn = document.createElement('button');
  toolbarToggleBtn.textContent = '⚡ Quick Toolbar';
  toolbarToggleBtn.style.cssText = `
    background: #FF5722;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  toolbarToggleBtn.onclick = () => toggleQuickToolbar();
  
  controls.appendChild(toggleBtn);
  controls.appendChild(selectAllBtn);
  controls.appendChild(refreshBtn);
  controls.appendChild(expandBtn);
  controls.appendChild(gridBtn);
  controls.appendChild(captureBtn);
  controls.appendChild(viewCollectionBtn);
  controls.appendChild(downloadBtn);
  controls.appendChild(isolationBtn);
  controls.appendChild(overlayToggleBtn);
  controls.appendChild(toolbarToggleBtn);
  
  // Counter
  const counter = document.createElement('div');
  counter.textContent = 'Selected: 0';
  counter.style.cssText = `
    padding: 8px 12px;
    background: #f5f5f5;
    border-bottom: 1px solid #eee;
    font-size: 12px;
    font-weight: 500;
    color: #333;
    flex-shrink: 0;
  `;
  
  // Content area
  const content = document.createElement('div');
  content.style.cssText = `
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    min-height: 0;
  `;
  
  sidebarElement.appendChild(header);
  sidebarElement.appendChild(controls);
  sidebarElement.appendChild(counter);
  sidebarElement.appendChild(content);
  
  // Store references
  sidebarElement.toggleBtn = toggleBtn;
  sidebarElement.selectAllBtn = selectAllBtn;
  sidebarElement.refreshBtn = refreshBtn;
  sidebarElement.expandBtn = expandBtn;
  sidebarElement.gridBtn = gridBtn;
  sidebarElement.overlayToggleBtn = overlayToggleBtn;
  sidebarElement.toolbarToggleBtn = toolbarToggleBtn;
  sidebarElement.counter = counter;
  sidebarElement.content = content;
  sidebarElement.isExpanded = false;
  sidebarElement.isGridMode = true;
  
  // Close button event
  header.querySelector('#sidebar-close').onclick = () => toggleSidebar();
  
  document.body.appendChild(sidebarElement);
}

// Refresh sidebar content
function refreshSidebar() {
  if (!sidebarElement) return;
  
  captureAllImagesToSidebar();
  showNotification('Sidebar refreshed');
}

// Toggle sidebar
function toggleSidebar() {
  if (sidebarVisible) {
    if (sidebarElement) {
      sidebarElement.remove();
      sidebarElement = null;
    }
    sidebarVisible = false;
  } else {
    createSidebar();
    sidebarVisible = true;
  }
}

// Toggle sidebar expansion
function toggleSidebarExpansion() {
  if (!sidebarElement) return;
  
  sidebarElement.isExpanded = !sidebarElement.isExpanded;
  
  if (sidebarElement.isExpanded) {
    sidebarElement.style.width = '66vw';
    sidebarElement.expandBtn.textContent = '📏 Collapse';
  } else {
    sidebarElement.style.width = '300px';
    sidebarElement.expandBtn.textContent = '📏 Expand';
  }
}

// Toggle grid mode
function toggleGridMode() {
  if (!sidebarElement) return;
  
  sidebarElement.isGridMode = !sidebarElement.isGridMode;
  
  if (sidebarElement.isGridMode) {
    sidebarElement.content.style.gridTemplateColumns = 'repeat(2, 1fr)';
    sidebarElement.gridBtn.textContent = '🔲 Grid';
  } else {
    sidebarElement.content.style.gridTemplateColumns = '1fr';
    sidebarElement.gridBtn.textContent = '📱 Single';
  }
}

// Toggle quick toolbar mode
function toggleQuickToolbar() {
  settings.quickToolbarMode = !settings.quickToolbarMode;
  
  if (floatingMenu) {
    if (settings.quickToolbarMode) {
      // Switch to toolbar mode
      floatingMenu.style.cssText = `
        position: fixed;
        left: ${floatingMenuPosition.x}px;
        top: ${floatingMenuPosition.y}px;
        background: rgba(0, 0, 0, 0.9);
        backdrop-filter: blur(10px);
        border-radius: 8px;
        padding: 8px;
        z-index: 10000;
        display: flex;
        flex-direction: row;
        gap: 4px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
        border: 1px solid rgba(255, 255, 255, 0.1);
        resize: both;
        overflow: auto;
        min-width: auto;
        max-width: 400px;
        width: auto;
        min-height: auto;
      `;
      
      // Update button container for horizontal layout
      if (floatingMenu.buttonContainer) {
        floatingMenu.buttonContainer.style.cssText = `
          display: flex;
          flex-direction: row;
          gap: 4px;
          margin-top: 0;
        `;
        
        // Update all buttons to compact size
        const buttons = floatingMenu.buttonContainer.querySelectorAll('.overlay-button');
        buttons.forEach(btn => {
          btn.style.cssText = `
            background: ${btn.style.background};
            color: white;
            border: none;
            padding: 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 10px;
            font-weight: 500;
            transition: all 0.2s ease;
            position: relative;
            user-select: none;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 16px;
            height: 16px;
            min-width: 16px;
            min-height: 16px;
          `;
          
          // Hide text, show only icon
          const textSpan = btn.querySelector('span');
          if (textSpan) {
            textSpan.style.display = 'none';
          }
          
          // Hide handle in toolbar mode
          const handle = btn.querySelector('.button-handle');
          if (handle) {
            handle.style.display = 'none';
          }
        });
      }
      
      // Hide counter in toolbar mode
      if (floatingMenu.counter) {
        floatingMenu.counter.style.display = 'none';
      }
      
      // Update sidebar button
      if (sidebarElement && sidebarElement.toolbarToggleBtn) {
        sidebarElement.toolbarToggleBtn.textContent = '📱 Full Menu';
        sidebarElement.toolbarToggleBtn.style.background = '#4CAF50';
      }
      
    } else {
      // Switch back to full menu mode
      floatingMenu.style.cssText = `
        position: fixed;
        left: ${floatingMenuPosition.x}px;
        top: ${floatingMenuPosition.y}px;
        background: rgba(0, 0, 0, 0.8);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        padding: 16px;
        z-index: 10000;
        display: flex;
        flex-direction: column;
        gap: 8px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
        min-width: 200px;
        max-width: 280px;
        width: 280px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        resize: both;
        overflow: auto;
      `;
      
      // Update button container for vertical layout
      if (floatingMenu.buttonContainer) {
        floatingMenu.buttonContainer.style.cssText = `
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-top: 20px;
        `;
        
        // Update all buttons to full size
        const buttons = floatingMenu.buttonContainer.querySelectorAll('.overlay-button');
        buttons.forEach(btn => {
          btn.style.cssText = `
            background: ${btn.style.background};
            color: white;
            border: none;
            padding: 10px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.2s ease;
            position: relative;
            user-select: none;
            display: flex;
            align-items: center;
            gap: 8px;
            width: auto;
            height: auto;
            min-width: auto;
            min-height: auto;
          `;
          
          // Show text
          const textSpan = btn.querySelector('span');
          if (textSpan) {
            textSpan.style.display = 'inline';
          }
          
          // Show handle
          const handle = btn.querySelector('.button-handle');
          if (handle) {
            handle.style.display = 'inline';
          }
        });
      }
      
      // Show counter
      if (floatingMenu.counter) {
        floatingMenu.counter.style.display = 'block';
      }
      
      // Update sidebar button
      if (sidebarElement && sidebarElement.toolbarToggleBtn) {
        sidebarElement.toolbarToggleBtn.textContent = '📱 Toolbar';
        sidebarElement.toolbarToggleBtn.style.background = '#2196F3';
      }
    }
    
    // Ensure menu is visible
    floatingMenu.style.display = 'flex';
    
    // Save settings
    chrome.runtime.sendMessage({
      action: 'updateSettings',
      settings: settings
    });
  }
}

// Capture all images to sidebar
function captureAllImagesToSidebar() {
  if (!sidebarElement) return;
  
  const images = document.querySelectorAll('img');
  sidebarElement.content.innerHTML = '';
  
  images.forEach(img => {
    if (shouldCaptureImage(img)) {
      const item = createSidebarImageItem(img);
      sidebarElement.content.appendChild(item);
    }
  });
}

// Check if image should be captured
function shouldCaptureImage(img) {
  const minWidth = settings.minImageWidth || 100;
  const preferredTypes = settings.preferredFileTypes || ['jpg', 'jpeg', 'png'];
  
  if (img.naturalWidth < minWidth) return false;
  
  const url = img.src.toLowerCase();
  const hasPreferredType = preferredTypes.some(type => url.includes('.' + type));
  if (!hasPreferredType) return false;
  
  if (img.offsetParent === null) return false;
  
  return true;
}

// Create sidebar image item
function createSidebarImageItem(img) {
  const item = document.createElement('div');
  item.style.cssText = `
    border: 1px solid #ddd;
    border-radius: 4px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s ease;
  `;
  
  const imgElement = document.createElement('img');
  imgElement.src = img.src;
  imgElement.style.cssText = `
    width: 100%;
    height: auto;
    display: block;
  `;
  
  item.appendChild(imgElement);
  
  item.onclick = () => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      item.style.borderColor = '#ddd';
    } else {
      selectedImages.add(img.src);
      item.style.borderColor = '#4CAF50';
    }
    updateSelectionCounter();
  };
  
  return item;
}

// Toggle isolation mode
function toggleIsolationMode() {
  isolationMode = !isolationMode;
  
  if (isolationMode) {
    const images = document.querySelectorAll('img');
    const container = document.createElement('div');
    container.id = 'imagecapture-isolation';
    container.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: #000;
      z-index: 10000;
      overflow: auto;
      padding: 20px;
    `;
    
    const header = document.createElement('div');
    header.style.cssText = `
      position: sticky;
      top: 0;
      background: rgba(0, 0, 0, 0.8);
      color: white;
      padding: 16px;
      margin: -20px -20px 20px -20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    `;
    
    const closeBtn = document.createElement('button');
    closeBtn.textContent = '✕ Close';
    closeBtn.style.cssText = `
      background: #f44336;
      color: white;
      border: none;
      padding: 8px 12px;
      border-radius: 4px;
      cursor: pointer;
      font-weight: bold;
      font-size: 14px;
    `;
    closeBtn.onclick = () => toggleIsolationMode();
    
    header.innerHTML = '<h2>🖼️ Image Isolation Mode</h2>';
    header.appendChild(closeBtn);
    
    const grid = document.createElement('div');
    grid.style.cssText = `
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
    `;
    
    images.forEach(img => {
      if (shouldCaptureImage(img)) {
        const item = createIsolationImageItem(img);
        grid.appendChild(item);
      }
    });
    
    container.appendChild(header);
    container.appendChild(grid);
    document.body.appendChild(container);
  } else {
    const container = document.getElementById('imagecapture-isolation');
    if (container) {
      container.remove();
    }
  }
}

// Create isolation image item
function createIsolationImageItem(img) {
  const item = document.createElement('div');
  item.style.cssText = `
    border: 2px solid #333;
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s ease;
    background: #222;
  `;
  
  const imgElement = document.createElement('img');
  imgElement.src = img.src;
  imgElement.style.cssText = `
    width: 100%;
    height: auto;
    display: block;
  `;
  
  item.appendChild(imgElement);
  
  item.onclick = () => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      item.style.borderColor = '#333';
    } else {
      selectedImages.add(img.src);
      item.style.borderColor = '#4CAF50';
    }
    updateSelectionCounter();
  };
  
  return item;
}

// Show notification
function showNotification(message) {
  if (settings.showNotifications) {
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: #333;
      color: white;
      padding: 12px 20px;
      border-radius: 6px;
      z-index: 10001;
      font-size: 14px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
      notification.remove();
    }, 3000);
  }
}

// Handle keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  
  switch (e.key.toLowerCase()) {
    case 's':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        toggleSelectionMode();
      }
      break;
    case 'i':
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        captureAllImagesToSidebar();
      }
      break;
    case 'q':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        // Quick capture logic
      }
      break;
    case 'd':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        downloadSelectedImages();
      }
      break;
    case 'escape':
      if (selectionMode) {
        selectionMode = false;
        document.body.style.cursor = 'default';
        showNotification('Selection mode OFF');
      }
      break;
  }
});

// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'toggleOverlay':
      overlayMenuVisible = !overlayMenuVisible;
      if (floatingMenu) {
        floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
      }
      break;
      
    case 'updateSettings':
      const oldUseOverlayIcons = settings.useOverlayIcons;
      const oldShowSelectionIndicator = settings.showSelectionIndicator;
      
      settings = { ...settings, ...request.settings };
      
      // If overlay icons setting changed, refresh all image indicators
      if (oldUseOverlayIcons !== settings.useOverlayIcons || 
          oldShowSelectionIndicator !== settings.showSelectionIndicator) {
        addImageIndicators();
      }
      break;
      
    case 'updateFloatingMenuPosition':
      floatingMenuPosition = request.position;
      if (floatingMenu) {
        // Use absolute positioning
        floatingMenu.style.left = `${floatingMenuPosition.x}px`;
        floatingMenu.style.top = `${floatingMenuPosition.y}px`;
        floatingMenu.style.right = 'auto';
        if (floatingMenuPosition.width && !settings.quickToolbarMode) {
          floatingMenu.style.minWidth = `${floatingMenuPosition.width}px`;
        }
      }
      break;
      
    case 'captureImages':
      captureSelectedImages();
      break;
      
    case 'downloadImages':
      downloadSelectedImages();
      break;
      
    case 'toggleSelectionMode':
      toggleSelectionMode();
      break;
      
    case 'selectAllImages':
      selectAllImages();
      break;
      
    case 'deselectAllImages':
      deselectAllImages();
      break;
      
    case 'toggleSidebar':
      toggleSidebar();
      break;
      
    case 'toggleIsolationMode':
      toggleIsolationMode();
      break;
      
    case 'toggleQuickToolbar':
      toggleQuickToolbar();
      break;
      
    case 'toggleOverlayMenu':
      toggleOverlayMenu();
      break;
      
    case 'toggleSelectAll':
      toggleSelectAll();
      break;
      
    case 'captureSelectedImages':
      captureSelectedImages();
      break;
      
    case 'downloadSelectedImages':
      downloadSelectedImages();
      break;
      
    case 'clearCapturedImages':
      chrome.runtime.sendMessage({
        action: 'clearCapturedImages'
      });
      showNotification('Collection cleared');
      break;
      
    case 'imagesCleared':
      showNotification('Collection cleared');
      break;
  }
  
  sendResponse({ success: true });
}); 
```

```javascript
// Content script for ImageCapture extension
let selectionMode = false;
let selectedImages = new Set();
let sidebarVisible = false;
let sidebarElement = null;
let floatingMenu = null;
let isolationMode = false;
let overlayMenuVisible = false;
let overlayHoverTimer = null;
let floatingMenuPosition = { x: 20, y: 20, width: 280, height: 'auto' };
let settings = {
  hoverSelectDelay: 500,
  hoverDeselectDelay: 300,
  autoCaptureHover: false, // Disabled hover selection
  showNotifications: true,
  showSelectionIndicator: true,
  telegramEnabled: true,
  showFloatingMenu: true,
  minImageWidth: 100,
  preferredFileTypes: ['jpg', 'jpeg', 'png'],
  overlayHoverDelay: 1000,
      overlayButtons: ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'],
  overlayDraggable: true,
  quickToolbarMode: false,
  useOverlayIcons: false // New setting for toggleable selection indicators
};

// Load global state from background script
chrome.runtime.sendMessage({action: 'getGlobalState'}, (response) => {
  if (response && response.globalState) {
    const globalState = response.globalState;
    settings = { ...settings, ...globalState.settings };
    overlayMenuVisible = globalState.overlayVisible;
    selectedImages = new Set(globalState.selectedImages || []);
    floatingMenuPosition = globalState.floatingMenuPosition || { x: 20, y: 20, width: 280, height: 'auto' };
  }
});

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  addImageIndicators();
  createFloatingMenu();
  
  // Monitor for dynamically added images
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'childList') {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            const images = node.querySelectorAll('img');
            if (images.length > 0) {
              addImageIndicators();
            }
          }
        });
      }
    });
  });
  
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
});

// Also initialize if DOM is already loaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeExtension);
} else {
  initializeExtension();
}

function initializeExtension() {
  addImageIndicators();
  if (settings.showFloatingMenu) {
    createFloatingMenu();
  }
  
  // Add window resize handler to keep menu within bounds
  window.addEventListener('resize', handleWindowResize);
}

// Handle window resize to keep floating menu within viewport
function handleWindowResize() {
  if (!floatingMenu) return;
  
  const rect = floatingMenu.getBoundingClientRect();
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  
  let needsUpdate = false;
  let newX = floatingMenuPosition.x;
  let newY = floatingMenuPosition.y;
  
  // Check if menu is outside viewport - use absolute positioning
  if (rect.right > viewportWidth) {
    newX = Math.max(20, viewportWidth - rect.width - 20);
    needsUpdate = true;
  }
  
  if (rect.bottom > viewportHeight) {
    newY = Math.max(20, viewportHeight - rect.height - 20);
    needsUpdate = true;
  }
  
  if (rect.left < 0) {
    newX = 20; // Keep menu at minimum left position
    needsUpdate = true;
  }
  
  if (rect.top < 0) {
    newY = Math.min(viewportHeight - rect.height - 20, 20);
    needsUpdate = true;
  }
  
  if (needsUpdate) {
    floatingMenuPosition.x = newX;
    floatingMenuPosition.y = newY;
    
    // Use absolute positioning instead of right-based
    floatingMenu.style.left = `${newX}px`;
    floatingMenu.style.top = `${newY}px`;
    floatingMenu.style.right = 'auto';
    
    // Save updated position
    chrome.runtime.sendMessage({
      action: 'setFloatingMenuPosition',
      position: floatingMenuPosition
    });
  }
}

// Add visual indicators to images with enhanced styling
function addImageIndicators() {
  const images = document.querySelectorAll('img');
  
  images.forEach(img => {
    if (img.dataset.imagecaptureInitialized) return;
    
    img.dataset.imagecaptureInitialized = 'true';
    img.style.cursor = 'pointer';
    
    // Only show borders/overlays when selection mode is active
    if (selectionMode) {
      // Enhanced border styling with increased thickness and reduced opacity
      if (selectedImages.has(img.src)) {
        if (settings.useOverlayIcons) {
          addSelectionOverlay(img);
        } else {
          img.style.border = '10px solid rgba(76, 175, 80, 0.75)';
          img.style.borderRadius = '8px';
          img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
          img.style.boxShadow = '0 0 20px rgba(76, 175, 80, 0.5), inset 0 0 20px rgba(76, 175, 80, 0.2)';
        }
      } else {
        if (settings.useOverlayIcons) {
          addCheckboxOverlay(img);
        } else {
          img.style.border = '10px solid rgba(255, 107, 107, 0.5625)';
          img.style.borderRadius = '8px';
          img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
          img.style.boxShadow = '0 0 20px rgba(255, 107, 107, 0.375), inset 0 0 20px rgba(255, 107, 107, 0.15)';
        }
      }
    } else {
      // Clear any existing borders/overlays when selection mode is off
      if (settings.useOverlayIcons) {
        removeSelectionOverlay(img);
      } else {
        img.style.border = 'none';
        img.style.boxShadow = 'none';
      }
    }
    
    // Click event
    img.addEventListener('click', (e) => {
      if (selectionMode) {
        e.preventDefault();
        e.stopPropagation();
        toggleImageSelection(img);
      }
    });
    
    // Mouse 3 (middle click) event
    img.addEventListener('auxclick', (e) => {
      if (e.button === 1) {
        e.preventDefault();
        e.stopPropagation();
        handleImageAuxClick(e);
      }
    });
  });
}

// Add selection overlay icon
function addSelectionOverlay(img) {
  // Remove any existing overlay
  removeSelectionOverlay(img);
  
  // Create overlay container
  const overlay = document.createElement('div');
  overlay.className = 'imagecapture-selection-overlay';
  overlay.style.cssText = `
    position: absolute;
    top: 10px;
    right: 10px;
    width: 30px;
    height: 30px;
    background: #4CAF50;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 18px;
    font-weight: bold;
    z-index: 1000;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  `;
  overlay.innerHTML = '✓';
  
  // Ensure img has relative positioning
  if (img.style.position !== 'relative' && img.style.position !== 'absolute') {
    img.style.position = 'relative';
  }
  
  img.appendChild(overlay);
}

// Add checkbox overlay for unselected images
function addCheckboxOverlay(img) {
  // Remove any existing overlay
  removeSelectionOverlay(img);
  
  // Create checkbox overlay container
  const overlay = document.createElement('div');
  overlay.className = 'imagecapture-checkbox-overlay';
  overlay.style.cssText = `
    position: absolute;
    top: 10px;
    right: 10px;
    width: 30px;
    height: 30px;
    background: rgba(255, 255, 255, 0.9);
    border: 2px solid #ccc;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #666;
    font-size: 16px;
    font-weight: bold;
    z-index: 1000;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    cursor: pointer;
  `;
  overlay.innerHTML = '';
  
  // Add click handler to the checkbox
  overlay.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    toggleImageSelection(img);
  });
  
  // Ensure img has relative positioning
  if (img.style.position !== 'relative' && img.style.position !== 'absolute') {
    img.style.position = 'relative';
  }
  
  img.appendChild(overlay);
}

// Remove selection overlay icon
function removeSelectionOverlay(img) {
  const overlay = img.querySelector('.imagecapture-selection-overlay, .imagecapture-checkbox-overlay');
  if (overlay) {
    overlay.remove();
  }
}

// Handle image aux click (Mouse 3)
function handleImageAuxClick(e) {
  const img = e.target;
  const imageUrl = img.src;
  
  if (selectedImages.has(imageUrl)) {
    selectedImages.delete(imageUrl);
    animateImageSelection(img, false);
  } else {
    selectedImages.add(imageUrl);
    animateImageSelection(img, true);
  }
  
  updateSelectionCounter();
}

// Animate image selection with enhanced visual feedback
function animateImageSelection(img, isSelected) {
  if (isSelected) {
    if (settings.useOverlayIcons) {
      addSelectionOverlay(img);
    } else {
      img.style.border = '10px solid rgba(76, 175, 80, 0.75)';
      img.style.boxShadow = `
        0 0 20px rgba(76, 175, 80, 0.5), 
        inset 0 0 20px rgba(76, 175, 80, 0.2),
        0 0 40px rgba(76, 175, 80, 0.3),
        0 0 60px rgba(76, 175, 80, 0.1)
      `;
    }
    img.style.transform = 'scale(1.02)';
    img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
    
    setTimeout(() => {
      img.style.transform = 'scale(1)';
    }, 200);
  } else {
    if (settings.useOverlayIcons) {
      addCheckboxOverlay(img);
    } else {
      img.style.border = '10px solid rgba(255, 107, 107, 0.5625)';
      img.style.boxShadow = `
        0 0 20px rgba(255, 107, 107, 0.375), 
        inset 0 0 20px rgba(255, 107, 107, 0.15),
        0 0 40px rgba(255, 107, 107, 0.25),
        0 0 60px rgba(255, 107, 107, 0.1)
      `;
    }
    img.style.transform = 'scale(1)';
    img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
  }
}

// Remove border after download
function removeImageBorder(img) {
  if (settings.useOverlayIcons) {
    removeSelectionOverlay(img);
  } else {
    img.style.border = 'none';
    img.style.boxShadow = 'none';
  }
  img.style.transform = 'scale(1)';
}

// Toggle image selection
function toggleImageSelection(img) {
  const imageUrl = img.src;
  
  if (selectedImages.has(imageUrl)) {
    selectedImages.delete(imageUrl);
    animateImageSelection(img, false);
  } else {
    selectedImages.add(imageUrl);
    animateImageSelection(img, true);
  }
  
  updateSelectionCounter();
}

// Select all images
function selectAllImages() {
  const images = document.querySelectorAll('img');
  images.forEach(img => {
    if (shouldCaptureImage(img)) {
      selectedImages.add(img.src);
      animateImageSelection(img, true);
    }
  });
  updateSelectionCounter();
  showNotification(`Selected ${selectedImages.size} images`);
}

// Deselect all images
function deselectAllImages() {
  const images = document.querySelectorAll('img');
  images.forEach(img => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      animateImageSelection(img, false);
    }
  });
  updateSelectionCounter();
  showNotification('Deselected all images');
}

// Toggle select all/deselect all
function toggleSelectAll() {
  const images = document.querySelectorAll('img');
  const capturableImages = Array.from(images).filter(img => shouldCaptureImage(img));
  const selectedCapturableImages = capturableImages.filter(img => selectedImages.has(img.src));
  
  if (selectedCapturableImages.length === capturableImages.length) {
    deselectAllImages();
  } else {
    selectAllImages();
  }
}

// Capture selected images
function captureSelectedImages() {
  const imagesToCapture = Array.from(selectedImages);
  if (imagesToCapture.length === 0) {
    showNotification('No images selected to capture');
    return;
  }
  
  imagesToCapture.forEach(imageUrl => {
    chrome.runtime.sendMessage({
      action: 'captureImage',
      url: imageUrl,
      title: document.title
    });
    
    // Remove border after capture
    const img = document.querySelector(`img[src="${imageUrl}"]`);
    if (img) {
      removeImageBorder(img);
    }
  });
  
  selectedImages.clear();
  updateSelectionCounter();
  showNotification(`Captured ${imagesToCapture.length} images`);
}

// Update selection counter
function updateSelectionCounter() {
  if (floatingMenu && floatingMenu.counter) {
    floatingMenu.counter.textContent = `Selected: ${selectedImages.size}`;
  }
  if (sidebarElement && sidebarElement.counter) {
    sidebarElement.counter.textContent = `Selected: ${selectedImages.size}`;
  }
}

// Toggle selection mode
function toggleSelectionMode() {
  selectionMode = !selectionMode;
  
  if (selectionMode) {
    document.body.style.cursor = 'crosshair';
    showNotification('Selection mode ON - Click images to select');
  } else {
    document.body.style.cursor = 'default';
    showNotification('Selection mode OFF');
  }
  
  // Refresh image indicators to show/hide borders based on selection mode
  addImageIndicators();
  
  // Update floating menu button
  if (floatingMenu && floatingMenu.toggleBtn) {
    floatingMenu.toggleBtn.textContent = selectionMode ? '🎯 Selection: ON' : '🎯 Selection: OFF';
    floatingMenu.toggleBtn.style.background = selectionMode ? '#4CAF50' : '#ff9800';
    floatingMenu.toggleBtn.style.borderColor = selectionMode ? '#4CAF50' : 'transparent';
  }
  
  // Update sidebar button if exists
  if (sidebarElement && sidebarElement.toggleBtn) {
    sidebarElement.toggleBtn.textContent = selectionMode ? '🎯 Selection: ON' : '🎯 Selection: OFF';
    sidebarElement.toggleBtn.style.background = selectionMode ? '#4CAF50' : '#ff9800';
  }
}

// Toggle overlay menu visibility with hover delay
function toggleOverlayMenu() {
  if (settings.overlayHoverDelay > 0) {
    if (overlayHoverTimer) {
      clearTimeout(overlayHoverTimer);
      overlayHoverTimer = null;
    }
    
    overlayHoverTimer = setTimeout(() => {
      overlayMenuVisible = !overlayMenuVisible;
      
      if (floatingMenu) {
        floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
      }
      
      // Save state to background
      chrome.runtime.sendMessage({
        action: 'setOverlayVisible',
        visible: overlayMenuVisible
      });
      
      showNotification(overlayMenuVisible ? 'Overlay menu shown' : 'Overlay menu hidden');
    }, settings.overlayHoverDelay);
  } else {
    overlayMenuVisible = !overlayMenuVisible;
    
    if (floatingMenu) {
      floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
    }
    
    chrome.runtime.sendMessage({
      action: 'setOverlayVisible',
      visible: overlayMenuVisible
    });
    
    showNotification(overlayMenuVisible ? 'Overlay menu shown' : 'Overlay menu hidden');
  }
}

// Create draggable floating menu with customizable buttons
function createFloatingMenu() {
  if (floatingMenu) return;
  
  floatingMenu = document.createElement('div');
  floatingMenu.id = 'imagecapture-floating-menu';
  floatingMenu.style.cssText = `
    position: fixed;
    left: ${floatingMenuPosition.x}px;
    top: ${floatingMenuPosition.y}px;
    background: rgba(0, 0, 0, 0.8);
    backdrop-filter: blur(10px);
    border-radius: 12px;
    padding: 16px;
    z-index: 10000;
    display: flex;
    flex-direction: column;
    gap: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    transition: all 0.3s ease;
    min-width: 200px;
    max-width: 280px;
    width: 280px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    resize: both;
    overflow: auto;
  `;
  
  // Add drag handle
  const dragHandle = document.createElement('div');
  dragHandle.innerHTML = '⋮⋮';
  dragHandle.style.cssText = `
    position: absolute;
    top: 8px;
    left: 8px;
    color: rgba(255, 255, 255, 0.6);
    cursor: move;
    font-size: 14px;
    font-weight: bold;
    user-select: none;
  `;
  
  // Add close button
  const closeBtn = document.createElement('button');
  closeBtn.innerHTML = '✕';
  closeBtn.style.cssText = `
    position: absolute;
    top: 8px;
    right: 8px;
    background: #f44336;
    color: white;
    border: none;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    cursor: pointer;
    font-size: 12px;
    font-weight: bold;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10001;
    transition: all 0.2s ease;
  `;
  closeBtn.onmouseenter = () => {
    closeBtn.style.background = '#d32f2f';
    closeBtn.style.transform = 'scale(1.1)';
  };
  closeBtn.onmouseleave = () => {
    closeBtn.style.background = '#f44336';
    closeBtn.style.transform = 'scale(1)';
  };
  closeBtn.onclick = () => {
    floatingMenu.remove();
    floatingMenu = null;
  };
  
  // Create button container
  const buttonContainer = document.createElement('div');
  buttonContainer.style.cssText = `
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 20px;
  `;
  
  // Create buttons based on settings
  const buttonConfigs = {
    overlay: {
      text: '👁️ Overlay',
      color: '#607D8B',
      action: () => toggleOverlayMenu()
    },
    selection: {
      text: '🎯 Selection: OFF',
      color: '#ff9800',
      action: () => toggleSelectionMode()
    },
    selectAll: {
      text: '☑️ Select All',
      color: '#2196F3',
      action: () => toggleSelectAll()
    },
    sidebar: {
      text: '📱 Sidebar',
      color: '#2196F3',
      action: () => toggleSidebar()
    },
    isolation: {
      text: '🖼️ Image Mode',
      color: '#9C27B0',
      action: () => toggleIsolationMode()
    },
    capture: {
      text: '📸 Capture',
      color: '#4CAF50',
      action: () => captureSelectedImages()
    },
    viewCollection: {
      text: '📋 View Collection',
      color: '#3F51B5',
      action: () => openCollectionView()
    },
    download: {
      text: '📥 Download',
      color: '#FF9800',
      action: () => downloadSelectedImages()
    },
    quickToolbar: {
      text: '⚡ Quick Toolbar',
      color: '#E91E63',
      action: () => toggleQuickToolbar()
    }
  };
  
  const buttons = {};
  const buttonOrder = [...settings.overlayButtons];
  
  function createButtonElement(buttonType) {
    if (!buttonConfigs[buttonType]) return null;
    
    const config = buttonConfigs[buttonType];
    const btn = document.createElement('div');
    btn.className = 'overlay-button';
    btn.dataset.buttonType = buttonType;
    btn.style.cssText = `
      background: ${config.color};
      color: white;
      border: none;
      padding: 10px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 500;
      transition: all 0.2s ease;
      position: relative;
      user-select: none;
      display: flex;
      align-items: center;
      gap: 8px;
    `;
    
    // Add drag handle for reordering
    const handle = document.createElement('div');
    handle.innerHTML = '⋮';
    handle.className = 'button-handle';
    handle.style.cssText = `
      color: rgba(255, 255, 255, 0.6);
      cursor: move;
      font-size: 10px;
      font-weight: bold;
      user-select: none;
      padding: 2px;
    `;
    
    const textSpan = document.createElement('span');
    textSpan.textContent = config.text;
    
    btn.appendChild(handle);
    btn.appendChild(textSpan);
    
    // Add drag functionality for reordering
    makeButtonDraggable(btn, handle, buttonContainer);
    
    btn.onclick = (e) => {
      if (e.target !== handle) {
        config.action();
      }
    };
    
    btn.onmouseenter = () => {
      if (!btn.classList.contains('dragging')) {
        btn.style.transform = 'translateY(-1px)';
        btn.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.2)';
      }
    };
    
    btn.onmouseleave = () => {
      if (!btn.classList.contains('dragging')) {
        btn.style.transform = 'translateY(0)';
        btn.style.boxShadow = 'none';
      }
    };
    
    return btn;
  }
  
  // Create and add buttons in order
  buttonOrder.forEach(buttonType => {
    const btn = createButtonElement(buttonType);
    if (btn) {
      buttonContainer.appendChild(btn);
      buttons[buttonType] = btn;
    }
  });
  
  const counter = document.createElement('div');
  counter.textContent = 'Selected: 0';
  counter.style.cssText = `
    color: white;
    font-size: 11px;
    text-align: center;
    margin-top: 8px;
    padding: 4px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
  `;
  
  floatingMenu.appendChild(dragHandle);
  floatingMenu.appendChild(closeBtn);
  floatingMenu.appendChild(buttonContainer);
  floatingMenu.appendChild(counter);
  
  // Store references
  floatingMenu.toggleBtn = buttons.selection;
  floatingMenu.selectAllBtn = buttons.selectAll;
  floatingMenu.sidebarBtn = buttons.sidebar;
  floatingMenu.isolationBtn = buttons.isolation;
  floatingMenu.captureBtn = buttons.capture;
  floatingMenu.downloadBtn = buttons.download;
  floatingMenu.counter = counter;
  floatingMenu.buttonContainer = buttonContainer;
  
  // Add drag functionality for moving the menu
  if (settings.overlayDraggable) {
    makeDraggable(floatingMenu, dragHandle);
  }
  
  // Add resize observer to track manual resizing
  const resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      if (entry.target === floatingMenu) {
        const rect = entry.target.getBoundingClientRect();
        
        // Only update width and height, preserve current x and y positions
        // This prevents the menu from "jumping" when resizing from the right edge
        // Apply max-width constraint to prevent full-screen stretching
        const maxWidth = settings.quickToolbarMode ? 400 : 280;
        const constrainedWidth = Math.min(rect.width, maxWidth);
        
        const newPosition = {
          x: floatingMenuPosition.x, // Preserve current x position
          y: floatingMenuPosition.y, // Preserve current y position
          width: constrainedWidth,
          height: rect.height
        };
        
        // Only update if the size actually changed to prevent unnecessary updates
        if (newPosition.width !== floatingMenuPosition.width || 
            newPosition.height !== floatingMenuPosition.height) {
          
          floatingMenuPosition = newPosition;
          
          // Temporarily disable transitions during resize to prevent stretching effect
          const originalTransition = floatingMenu.style.transition;
          floatingMenu.style.transition = 'none';
          
          // Apply the constrained width to the element
          floatingMenu.style.width = `${constrainedWidth}px`;
          
          // Don't update min-width dynamically - this causes stretching issues
          // The min-width should remain fixed at the initial value
          
          // Re-enable transitions after a brief delay
          setTimeout(() => {
            floatingMenu.style.transition = originalTransition;
          }, 50);
          
          chrome.runtime.sendMessage({
            action: 'setFloatingMenuPosition',
            position: newPosition
          });
        }
      }
    }
  });
  resizeObserver.observe(floatingMenu);
  
  // Set initial visibility - ensure it's visible if overlayMenuVisible is true
  floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
  
  // Apply toolbar mode if enabled
  if (settings.quickToolbarMode) {
    toggleQuickToolbar();
  }
  
  document.body.appendChild(floatingMenu);
}

// Make element draggable
function makeDraggable(element, handle) {
  let isDragging = false;
  let currentX;
  let currentY;
  let initialX;
  let initialY;
  let xOffset = 0;
  let yOffset = 0;
  
  handle.addEventListener('mousedown', dragStart);
  document.addEventListener('mousemove', drag);
  document.addEventListener('mouseup', dragEnd);
  
  function dragStart(e) {
    // Only allow dragging if the target is the handle or its children
    if (e.target === handle || handle.contains(e.target)) {
      initialX = e.clientX - xOffset;
      initialY = e.clientY - yOffset;
      isDragging = true;
      e.preventDefault(); // Prevent text selection
    }
  }
  
  function drag(e) {
    if (isDragging) {
      e.preventDefault();
      
      currentX = e.clientX - initialX;
      currentY = e.clientY - initialY;
      
      xOffset = currentX;
      yOffset = currentY;
      
      setTranslate(currentX, currentY, element);
    }
  }
  
  function setTranslate(xPos, yPos, el) {
    el.style.transform = `translate3d(${xPos}px, ${yPos}px, 0)`;
  }
  
  function dragEnd(e) {
    initialX = currentX;
    initialY = currentY;
    isDragging = false;
    
    // Save position to background script - use absolute positioning
    const rect = element.getBoundingClientRect();
    const newPosition = {
      x: rect.left,
      y: rect.top,
      width: rect.width,
      height: rect.height
    };
    
    floatingMenuPosition = newPosition;
    
    // Reset transform and apply absolute positioning
    element.style.transform = 'none';
    element.style.left = `${newPosition.x}px`;
    element.style.top = `${newPosition.y}px`;
    
    chrome.runtime.sendMessage({
      action: 'setFloatingMenuPosition',
      position: newPosition
    });
  }
}

// Make button draggable for reordering
function makeButtonDraggable(button, handle, container) {
  let isDragging = false;
  let dragStartY = 0;
  let originalY = 0;
  let placeholder = null;
  
  handle.addEventListener('mousedown', (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    isDragging = true;
    dragStartY = e.clientY;
    originalY = button.offsetTop;
    
    // Create placeholder
    placeholder = document.createElement('div');
    placeholder.style.cssText = `
      height: ${button.offsetHeight}px;
      background: rgba(255, 255, 255, 0.1);
      border: 2px dashed rgba(255, 255, 255, 0.3);
      border-radius: 6px;
      margin: 4px 0;
    `;
    
    // Add dragging class
    button.classList.add('dragging');
    button.style.opacity = '0.8';
    button.style.transform = 'rotate(2deg) scale(1.02)';
    button.style.zIndex = '1000';
    
    // Insert placeholder
    container.insertBefore(placeholder, button);
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  });
  
  function handleMouseMove(e) {
    if (!isDragging) return;
    
    const deltaY = e.clientY - dragStartY;
    const newY = originalY + deltaY;
    
    // Find the new position
    const buttons = Array.from(container.children).filter(child => 
      child.classList.contains('overlay-button') && child !== button
    );
    
    let insertIndex = 0;
    for (let i = 0; i < buttons.length; i++) {
      const btn = buttons[i];
      const btnRect = btn.getBoundingClientRect();
      const btnCenter = btnRect.top + btnRect.height / 2;
      
      if (e.clientY < btnCenter) {
        insertIndex = i;
        break;
      }
      insertIndex = i + 1;
    }
    
    // Move placeholder
    const allButtons = Array.from(container.children).filter(child => 
      child.classList.contains('overlay-button') && child !== button
    );
    
    if (placeholder && allButtons.length > 0) {
      if (insertIndex >= allButtons.length) {
        container.appendChild(placeholder);
      } else {
        container.insertBefore(placeholder, allButtons[insertIndex]);
      }
    }
  }
  
  function handleMouseUp() {
    if (!isDragging) return;
    
    isDragging = false;
    
    // Remove dragging class
    button.classList.remove('dragging');
    button.style.opacity = '1';
    button.style.transform = 'rotate(0deg) scale(1)';
    button.style.zIndex = 'auto';
    
    // Move button to placeholder position
    if (placeholder && placeholder.parentNode) {
      placeholder.parentNode.insertBefore(button, placeholder);
      placeholder.remove();
    }
    
    // Update button order in settings
    updateButtonOrder();
    
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  }
}

// Update button order in settings
function updateButtonOrder() {
  if (!floatingMenu || !floatingMenu.buttonContainer) return;
  
  const buttons = Array.from(floatingMenu.buttonContainer.children)
    .filter(child => child.classList.contains('overlay-button'))
    .map(btn => btn.dataset.buttonType);
  
  settings.overlayButtons = buttons;
  
  // Save to background
  chrome.runtime.sendMessage({
    action: 'updateSettings',
    settings: { overlayButtons: buttons }
  });
}

// Download selected images
function downloadSelectedImages() {
  const imagesToDownload = Array.from(selectedImages);
  if (imagesToDownload.length === 0) {
    showNotification('No images selected to download');
    return;
  }
  
  showNotification(`Starting download of ${imagesToDownload.length} images...`);
  
  // Debug logging
  console.log('Downloading images:', imagesToDownload);
  
  chrome.runtime.sendMessage({
    action: 'downloadImages',
    images: imagesToDownload.map(url => ({ url, title: document.title }))
  }, (response) => {
    console.log('Download response:', response);
    if (response && response.success) {
      // Remove borders after download
      imagesToDownload.forEach(imageUrl => {
        const img = document.querySelector(`img[src="${imageUrl}"]`);
        if (img) {
          removeImageBorder(img);
        }
      });
      
      selectedImages.clear();
      updateSelectionCounter();
      showNotification(`Successfully downloaded ${response.downloaded || imagesToDownload.length} images to your browser's download folder`);
    } else {
      showNotification(`Failed to download images: ${response.error || 'Unknown error'}`);
    }
  });
}

function openCollectionView() {
  chrome.runtime.sendMessage({ action: 'viewCollection' }, (response) => {
    if (!response || !response.success) {
      showNotification(response && response.error ? response.error : 'Unable to open collection');
    }
  });
}

// Create sidebar with enhanced features
function createSidebar() {
  if (sidebarElement) return;
  
  sidebarElement = document.createElement('div');
  sidebarElement.id = 'imagecapture-sidebar';
  sidebarElement.style.cssText = `
    position: fixed;
    top: 0;
    right: 0;
    width: 300px;
    height: 100vh;
    background: white;
    box-shadow: -2px 0 10px rgba(0, 0, 0, 0.3);
    z-index: 9999;
    display: flex;
    flex-direction: column;
    transition: width 0.3s ease;
    resize: horizontal;
    overflow: auto;
    min-width: 200px;
    max-width: 80vw;
  `;
  
  // Header
  const header = document.createElement('div');
  header.style.cssText = `
    background: #667eea;
    color: white;
    padding: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
  `;
  header.innerHTML = `
    <h3 style="margin: 0; font-size: 16px;">🖼️ ImageCapture Sidebar</h3>
    <button id="sidebar-close" style="background: #f44336; border: none; color: white; font-size: 18px; cursor: pointer; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">✕</button>
  `;
  
  // Controls
  const controls = document.createElement('div');
  controls.style.cssText = `
    padding: 12px;
    border-bottom: 1px solid #eee;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    flex-shrink: 0;
  `;
  
  const toggleBtn = document.createElement('button');
  toggleBtn.textContent = '🎯 Selection: OFF';
  toggleBtn.style.cssText = `
    background: #ff9800;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  toggleBtn.onclick = () => toggleSelectionMode();
  
  const selectAllBtn = document.createElement('button');
  selectAllBtn.textContent = '☑️ Select All';
  selectAllBtn.style.cssText = `
    background: #2196F3;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  selectAllBtn.onclick = () => toggleSelectAll();
  
  const refreshBtn = document.createElement('button');
  refreshBtn.textContent = '🔄 Refresh';
  refreshBtn.style.cssText = `
    background: #4CAF50;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  refreshBtn.onclick = () => refreshSidebar();
  
  const expandBtn = document.createElement('button');
  expandBtn.textContent = '📏 Expand';
  expandBtn.style.cssText = `
    background: #2196F3;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  expandBtn.onclick = () => toggleSidebarExpansion();
  
  const gridBtn = document.createElement('button');
  gridBtn.textContent = '🔲 Grid';
  gridBtn.style.cssText = `
    background: #9C27B0;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  gridBtn.onclick = () => toggleGridMode();
  
  const captureBtn = document.createElement('button');
  captureBtn.textContent = '📸 Capture All';
  captureBtn.style.cssText = `
    background: #4CAF50;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  captureBtn.onclick = () => captureAllImagesToSidebar();
  
  const viewCollectionBtn = document.createElement('button');
  viewCollectionBtn.textContent = '📋 View Collection';
  viewCollectionBtn.style.cssText = `
    background: #3F51B5;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  viewCollectionBtn.onclick = () => openCollectionView();
  
  const downloadBtn = document.createElement('button');
  downloadBtn.textContent = '📥 Download Selected';
  downloadBtn.style.cssText = `
    background: #FF9800;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  downloadBtn.onclick = () => downloadSelectedImages();
  
  const isolationBtn = document.createElement('button');
  isolationBtn.textContent = '🖼️ Image Mode';
  isolationBtn.style.cssText = `
    background: #9C27B0;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  isolationBtn.onclick = () => toggleIsolationMode();
  
  const overlayToggleBtn = document.createElement('button');
  overlayToggleBtn.textContent = '👁️ Overlay Menu On/Off';
  overlayToggleBtn.style.cssText = `
    background: #607D8B;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  overlayToggleBtn.onclick = () => toggleOverlayMenu();
  
  const toolbarToggleBtn = document.createElement('button');
  toolbarToggleBtn.textContent = '⚡ Quick Toolbar';
  toolbarToggleBtn.style.cssText = `
    background: #FF5722;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  toolbarToggleBtn.onclick = () => toggleQuickToolbar();
  
  controls.appendChild(toggleBtn);
  controls.appendChild(selectAllBtn);
  controls.appendChild(refreshBtn);
  controls.appendChild(expandBtn);
  controls.appendChild(gridBtn);
  controls.appendChild(captureBtn);
  controls.appendChild(viewCollectionBtn);
  controls.appendChild(downloadBtn);
  controls.appendChild(isolationBtn);
  controls.appendChild(overlayToggleBtn);
  controls.appendChild(toolbarToggleBtn);
  
  // Counter
  const counter = document.createElement('div');
  counter.textContent = 'Selected: 0';
  counter.style.cssText = `
    padding: 8px 12px;
    background: #f5f5f5;
    border-bottom: 1px solid #eee;
    font-size: 12px;
    font-weight: 500;
    color: #333;
    flex-shrink: 0;
  `;
  
  // Content area
  const content = document.createElement('div');
  content.style.cssText = `
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    min-height: 0;
  `;
  
  sidebarElement.appendChild(header);
  sidebarElement.appendChild(controls);
  sidebarElement.appendChild(counter);
  sidebarElement.appendChild(content);
  
  // Store references
  sidebarElement.toggleBtn = toggleBtn;
  sidebarElement.selectAllBtn = selectAllBtn;
  sidebarElement.refreshBtn = refreshBtn;
  sidebarElement.expandBtn = expandBtn;
  sidebarElement.gridBtn = gridBtn;
  sidebarElement.viewCollectionBtn = viewCollectionBtn;
  sidebarElement.overlayToggleBtn = overlayToggleBtn;
  sidebarElement.toolbarToggleBtn = toolbarToggleBtn;
  sidebarElement.counter = counter;
  sidebarElement.content = content;
  sidebarElement.isExpanded = false;
  sidebarElement.isGridMode = true;
  
  // Close button event
  header.querySelector('#sidebar-close').onclick = () => toggleSidebar();
  
  document.body.appendChild(sidebarElement);
}

// Refresh sidebar content
function refreshSidebar() {
  if (!sidebarElement) return;
  
  captureAllImagesToSidebar();
  showNotification('Sidebar refreshed');
}

// Toggle sidebar
function toggleSidebar() {
  if (sidebarVisible) {
    if (sidebarElement) {
      sidebarElement.remove();
      sidebarElement = null;
    }
    sidebarVisible = false;
  } else {
    createSidebar();
    sidebarVisible = true;
  }
}

// Toggle sidebar expansion
function toggleSidebarExpansion() {
  if (!sidebarElement) return;
  
  sidebarElement.isExpanded = !sidebarElement.isExpanded;
  
  if (sidebarElement.isExpanded) {
    sidebarElement.style.width = '66vw';
    sidebarElement.expandBtn.textContent = '📏 Collapse';
  } else {
    sidebarElement.style.width = '300px';
    sidebarElement.expandBtn.textContent = '📏 Expand';
  }
}

// Toggle grid mode
function toggleGridMode() {
  if (!sidebarElement) return;
  
  sidebarElement.isGridMode = !sidebarElement.isGridMode;
  
  if (sidebarElement.isGridMode) {
    sidebarElement.content.style.gridTemplateColumns = 'repeat(2, 1fr)';
    sidebarElement.gridBtn.textContent = '🔲 Grid';
  } else {
    sidebarElement.content.style.gridTemplateColumns = '1fr';
    sidebarElement.gridBtn.textContent = '📱 Single';
  }
}

// Toggle quick toolbar mode
function toggleQuickToolbar() {
  settings.quickToolbarMode = !settings.quickToolbarMode;
  
  if (floatingMenu) {
    if (settings.quickToolbarMode) {
      // Switch to toolbar mode
      floatingMenu.style.cssText = `
        position: fixed;
        left: ${floatingMenuPosition.x}px;
        top: ${floatingMenuPosition.y}px;
        background: rgba(0, 0, 0, 0.9);
        backdrop-filter: blur(10px);
        border-radius: 8px;
        padding: 8px;
        z-index: 10000;
        display: flex;
        flex-direction: row;
        gap: 4px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
        border: 1px solid rgba(255, 255, 255, 0.1);
        resize: both;
        overflow: auto;
        min-width: auto;
        max-width: 400px;
        width: auto;
        min-height: auto;
      `;
      
      // Update button container for horizontal layout
      if (floatingMenu.buttonContainer) {
        floatingMenu.buttonContainer.style.cssText = `
          display: flex;
          flex-direction: row;
          gap: 4px;
          margin-top: 0;
        `;
        
        // Update all buttons to compact size
        const buttons = floatingMenu.buttonContainer.querySelectorAll('.overlay-button');
        buttons.forEach(btn => {
          btn.style.cssText = `
            background: ${btn.style.background};
            color: white;
            border: none;
            padding: 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 10px;
            font-weight: 500;
            transition: all 0.2s ease;
            position: relative;
            user-select: none;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 16px;
            height: 16px;
            min-width: 16px;
            min-height: 16px;
          `;
          
          // Hide text, show only icon
          const textSpan = btn.querySelector('span');
          if (textSpan) {
            textSpan.style.display = 'none';
          }
          
          // Hide handle in toolbar mode
          const handle = btn.querySelector('.button-handle');
          if (handle) {
            handle.style.display = 'none';
          }
        });
      }
      
      // Hide counter in toolbar mode
      if (floatingMenu.counter) {
        floatingMenu.counter.style.display = 'none';
      }
      
      // Update sidebar button
      if (sidebarElement && sidebarElement.toolbarToggleBtn) {
        sidebarElement.toolbarToggleBtn.textContent = '📱 Full Menu';
        sidebarElement.toolbarToggleBtn.style.background = '#4CAF50';
      }
      
    } else {
      // Switch back to full menu mode
      floatingMenu.style.cssText = `
        position: fixed;
        left: ${floatingMenuPosition.x}px;
        top: ${floatingMenuPosition.y}px;
        background: rgba(0, 0, 0, 0.8);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        padding: 16px;
        z-index: 10000;
        display: flex;
        flex-direction: column;
        gap: 8px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
        min-width: 200px;
        max-width: 280px;
        width: 280px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        resize: both;
        overflow: auto;
      `;
      
      // Update button container for vertical layout
      if (floatingMenu.buttonContainer) {
        floatingMenu.buttonContainer.style.cssText = `
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-top: 20px;
        `;
        
        // Update all buttons to full size
        const buttons = floatingMenu.buttonContainer.querySelectorAll('.overlay-button');
        buttons.forEach(btn => {
          btn.style.cssText = `
            background: ${btn.style.background};
            color: white;
            border: none;
            padding: 10px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.2s ease;
            position: relative;
            user-select: none;
            display: flex;
            align-items: center;
            gap: 8px;
            width: auto;
            height: auto;
            min-width: auto;
            min-height: auto;
          `;
          
          // Show text
          const textSpan = btn.querySelector('span');
          if (textSpan) {
            textSpan.style.display = 'inline';
          }
          
          // Show handle
          const handle = btn.querySelector('.button-handle');
          if (handle) {
            handle.style.display = 'inline';
          }
        });
      }
      
      // Show counter
      if (floatingMenu.counter) {
        floatingMenu.counter.style.display = 'block';
      }
      
      // Update sidebar button
      if (sidebarElement && sidebarElement.toolbarToggleBtn) {
        sidebarElement.toolbarToggleBtn.textContent = '📱 Toolbar';
        sidebarElement.toolbarToggleBtn.style.background = '#2196F3';
      }
    }
    
    // Ensure menu is visible
    floatingMenu.style.display = 'flex';
    
    // Save settings
    chrome.runtime.sendMessage({
      action: 'updateSettings',
      settings: settings
    });
  }
}

// Capture all images to sidebar
function captureAllImagesToSidebar() {
  if (!sidebarElement) return;
  
  const images = document.querySelectorAll('img');
  sidebarElement.content.innerHTML = '';
  
  images.forEach(img => {
    if (shouldCaptureImage(img)) {
      const item = createSidebarImageItem(img);
      sidebarElement.content.appendChild(item);
    }
  });
}

// Check if image should be captured
function shouldCaptureImage(img) {
  const minWidth = settings.minImageWidth || 100;
  const preferredTypes = settings.preferredFileTypes || ['jpg', 'jpeg', 'png'];
  
  if (img.naturalWidth < minWidth) return false;
  
  const url = img.src.toLowerCase();
  const hasPreferredType = preferredTypes.some(type => url.includes('.' + type));
  if (!hasPreferredType) return false;
  
  if (img.offsetParent === null) return false;
  
  return true;
}

// Create sidebar image item
function createSidebarImageItem(img) {
  const item = document.createElement('div');
  item.style.cssText = `
    border: 1px solid #ddd;
    border-radius: 4px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s ease;
  `;
  
  const imgElement = document.createElement('img');
  imgElement.src = img.src;
  imgElement.style.cssText = `
    width: 100%;
    height: auto;
    display: block;
  `;
  
  item.appendChild(imgElement);
  
  item.onclick = () => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      item.style.borderColor = '#ddd';
    } else {
      selectedImages.add(img.src);
      item.style.borderColor = '#4CAF50';
    }
    updateSelectionCounter();
  };
  
  return item;
}

// Toggle isolation mode
function toggleIsolationMode() {
  isolationMode = !isolationMode;
  
  if (isolationMode) {
    const images = document.querySelectorAll('img');
    const container = document.createElement('div');
    container.id = 'imagecapture-isolation';
    container.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: #000;
      z-index: 10000;
      overflow: auto;
      padding: 20px;
    `;
    
    const header = document.createElement('div');
    header.style.cssText = `
      position: sticky;
      top: 0;
      background: rgba(0, 0, 0, 0.8);
      color: white;
      padding: 16px;
      margin: -20px -20px 20px -20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    `;
    
    const closeBtn = document.createElement('button');
    closeBtn.textContent = '✕ Close';
    closeBtn.style.cssText = `
      background: #f44336;
      color: white;
      border: none;
      padding: 8px 12px;
      border-radius: 4px;
      cursor: pointer;
      font-weight: bold;
      font-size: 14px;
    `;
    closeBtn.onclick = () => toggleIsolationMode();
    
    header.innerHTML = '<h2>🖼️ Image Isolation Mode</h2>';
    header.appendChild(closeBtn);
    
    const grid = document.createElement('div');
    grid.style.cssText = `
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
    `;
    
    images.forEach(img => {
      if (shouldCaptureImage(img)) {
        const item = createIsolationImageItem(img);
        grid.appendChild(item);
      }
    });
    
    container.appendChild(header);
    container.appendChild(grid);
    document.body.appendChild(container);
  } else {
    const container = document.getElementById('imagecapture-isolation');
    if (container) {
      container.remove();
    }
  }
}

// Create isolation image item
function createIsolationImageItem(img) {
  const item = document.createElement('div');
  item.style.cssText = `
    border: 2px solid #333;
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s ease;
    background: #222;
  `;
  
  const imgElement = document.createElement('img');
  imgElement.src = img.src;
  imgElement.style.cssText = `
    width: 100%;
    height: auto;
    display: block;
  `;
  
  item.appendChild(imgElement);
  
  item.onclick = () => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      item.style.borderColor = '#333';
    } else {
      selectedImages.add(img.src);
      item.style.borderColor = '#4CAF50';
    }
    updateSelectionCounter();
  };
  
  return item;
}

// Show notification
function showNotification(message) {
  if (settings.showNotifications) {
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: #333;
      color: white;
      padding: 12px 20px;
      border-radius: 6px;
      z-index: 10001;
      font-size: 14px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
      notification.remove();
    }, 3000);
  }
}

// Handle keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  
  switch (e.key.toLowerCase()) {
    case 's':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        toggleSelectionMode();
      }
      break;
    case 'i':
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        captureAllImagesToSidebar();
      }
      break;
    case 'q':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        // Quick capture logic
      }
      break;
    case 'd':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        downloadSelectedImages();
      }
      break;
    case 'escape':
      if (selectionMode) {
        selectionMode = false;
        document.body.style.cursor = 'default';
        showNotification('Selection mode OFF');
      }
      break;
  }
});

// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'toggleOverlay':
      overlayMenuVisible = !overlayMenuVisible;
      if (floatingMenu) {
        floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
      }
      break;
      
    case 'updateSettings':
      const oldUseOverlayIcons = settings.useOverlayIcons;
      const oldShowSelectionIndicator = settings.showSelectionIndicator;
      
      settings = { ...settings, ...request.settings };
      
      // If overlay icons setting changed, refresh all image indicators
      if (oldUseOverlayIcons !== settings.useOverlayIcons || 
          oldShowSelectionIndicator !== settings.showSelectionIndicator) {
        addImageIndicators();
      }
      break;
      
    case 'updateFloatingMenuPosition':
      floatingMenuPosition = request.position;
      if (floatingMenu) {
        // Use absolute positioning
        floatingMenu.style.left = `${floatingMenuPosition.x}px`;
        floatingMenu.style.top = `${floatingMenuPosition.y}px`;
        floatingMenu.style.right = 'auto';
        if (floatingMenuPosition.width && !settings.quickToolbarMode) {
          floatingMenu.style.minWidth = `${floatingMenuPosition.width}px`;
        }
      }
      break;
      
    case 'captureImages':
      captureSelectedImages();
      break;
      
    case 'downloadImages':
      downloadSelectedImages();
      break;
      
    case 'toggleSelectionMode':
      toggleSelectionMode();
      break;
      
    case 'selectAllImages':
      selectAllImages();
      break;
      
    case 'deselectAllImages':
      deselectAllImages();
      break;
      
    case 'toggleSidebar':
      toggleSidebar();
      break;
      
    case 'toggleIsolationMode':
      toggleIsolationMode();
      break;
      
    case 'toggleQuickToolbar':
      toggleQuickToolbar();
      break;
      
    case 'toggleOverlayMenu':
      toggleOverlayMenu();
      break;
      
    case 'toggleSelectAll':
      toggleSelectAll();
      break;
      
    case 'captureSelectedImages':
      captureSelectedImages();
      break;
      
    case 'downloadSelectedImages':
      downloadSelectedImages();
      break;
      
    case 'clearCapturedImages':
      chrome.runtime.sendMessage({
        action: 'clearCapturedImages'
      });
      showNotification('Collection cleared');
      break;
      
    case 'imagesCleared':
      showNotification('Collection cleared');
      break;
  }
  
  sendResponse({ success: true });
}); 
```

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ImageCapture</title>
    <style>
        body {
            width: 350px;
            min-height: 500px;
            margin: 0;
            padding: 16px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .header {
            text-align: center;
            margin-bottom: 20px;
        }
        
        .header h1 {
            margin: 0;
            font-size: 18px;
            font-weight: 600;
        }
        
        .stats {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
            backdrop-filter: blur(10px);
        }
        
        .stat-item {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        
        .stat-item:last-child {
            margin-bottom: 0;
        }
        
        .stat-label {
            font-size: 14px;
            opacity: 0.9;
        }
        
        .stat-value {
            font-size: 14px;
            font-weight: 600;
        }
        
        .actions {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 16px;
        }
        
        .btn {
            background: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 6px;
            padding: 12px 16px;
            color: white;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            text-align: center;
            text-decoration: none;
        }
        
        .btn:hover {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-1px);
        }
        
        .btn:active {
            transform: translateY(0);
        }
        
        .btn.primary {
            background: #4CAF50;
            border-color: #4CAF50;
        }
        
        .btn.primary:hover {
            background: #45a049;
        }
        
        .btn.danger {
            background: #f44336;
            border-color: #f44336;
        }
        
        .btn.danger:hover {
            background: #da190b;
        }
        
        .btn.warning {
            background: #ff9800;
            border-color: #ff9800;
        }
        
        .btn.warning:hover {
            background: #f57c00;
        }
        
        .btn.telegram {
            background: #0088cc;
            border-color: #0088cc;
        }
        
        .btn.telegram:hover {
            background: #006699;
        }
        
        .btn.success {
            background: #4CAF50;
            border-color: #4CAF50;
        }
        
        .btn.success:hover {
            background: #45a049;
        }
        
        .hotkeys {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
            backdrop-filter: blur(10px);
        }
        
        .hotkeys h3 {
            margin: 0 0 12px 0;
            font-size: 14px;
            font-weight: 600;
        }
        
        .hotkey-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            font-size: 12px;
        }
        
        .hotkey-item:last-child {
            margin-bottom: 0;
        }
        
        .hotkey-input {
            background: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 4px;
            padding: 4px 8px;
            color: white;
            font-size: 11px;
            font-family: monospace;
            width: 60px;
            text-align: center;
        }
        
        .hotkey-input:focus {
            outline: none;
            border-color: #4CAF50;
        }
        
        .setting-input {
            background: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 4px;
            padding: 4px 8px;
            color: white;
            font-size: 11px;
            width: 80px;
            text-align: center;
        }
        
        .setting-input:focus {
            outline: none;
            border-color: #4CAF50;
        }
        
        .shortcuts {
            margin-top: 16px;
            padding: 12px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 6px;
            font-size: 12px;
            opacity: 0.8;
        }
        
        .shortcut {
            margin-bottom: 4px;
        }
        
        .shortcut:last-child {
            margin-bottom: 0;
        }
        
        .key {
            background: rgba(255, 255, 255, 0.2);
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
            font-size: 11px;
        }
        
        .tabs {
            display: flex;
            margin-bottom: 16px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 6px;
            padding: 4px;
        }
        
        .tab {
            flex: 1;
            padding: 8px 12px;
            text-align: center;
            cursor: pointer;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        
        .tab.active {
            background: rgba(255, 255, 255, 0.2);
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .action-row {
            display: flex;
            gap: 8px;
        }
        
        .action-row .btn {
            flex: 1;
        }
        
        .toggle-btn {
            position: relative;
            overflow: hidden;
        }
        
        .toggle-btn.active {
            background: #4CAF50 !important;
            border-color: #4CAF50 !important;
        }
        
        .toggle-btn.active:hover {
            background: #45a049 !important;
        }
        
        .toggle-btn:not(.active) {
            background: #ff9800 !important;
            border-color: #ff9800 !important;
        }
        
        .toggle-btn:not(.active):hover {
            background: #f57c00 !important;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🖼️ ImageCapture</h1>
    </div>
    
    <div class="tabs">
        <div class="tab active" data-tab="main">Main</div>
        <div class="tab" data-tab="hotkeys">Hotkeys</div>
        <div class="tab" data-tab="settings">Settings</div>
    </div>
    
    <!-- Main Tab -->
    <div class="tab-content active" id="main-tab">
        <div class="stats">
            <div class="stat-item">
                <span class="stat-label">Images Captured:</span>
                <span class="stat-value" id="capturedCount">0</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Storage Used:</span>
                <span class="stat-value" id="storageUsed">0 KB</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Last Capture:</span>
                <span class="stat-value" id="lastCapture">Never</span>
            </div>
        </div>
        
        <div class="actions">
            <div class="action-row">
                <button class="btn primary" id="downloadAll">📥 Download All</button>
                <button class="btn telegram" id="sendToTelegram">📤 Send to Telegram</button>
            </div>
            <button class="btn" id="viewCollection">📋 View Collection</button>
            <button class="btn toggle-btn" id="toggleSelection">🎯 Selection Mode: OFF</button>
            <button class="btn" id="toggleSelectAll">☑️ Select All</button>
            <button class="btn" id="toggleSidebar">📱 Toggle Sidebar</button>
            <button class="btn" id="toggleOverlayMenu">👁️ Overlay Menu On/Off</button>
            <button class="btn" id="clearCollection">🗑️ Clear Collection</button>
        </div>
        
        <div class="shortcuts">
            <div class="shortcut">
                <span class="key">S</span> - Toggle selection mode
            </div>
            <div class="shortcut">
                <span class="key">Ctrl/Cmd + I</span> - Capture all visible images
            </div>
            <div class="shortcut">
                <span class="key">Q</span> - Quick capture single image
            </div>
            <div class="shortcut">
                <span class="key">D</span> - Download selected images
            </div>
            <div class="shortcut">
                <span class="key">Mouse3</span> - Middle click (configurable)
            </div>
            <div class="shortcut">
                <span class="key">Escape</span> - Exit selection mode
            </div>
        </div>
    </div>
    
    <!-- Hotkeys Tab -->
    <div class="tab-content" id="hotkeys-tab">
        <div class="hotkeys">
            <h3>Customize Hotkeys</h3>
            <div class="hotkey-item">
                <span>Toggle Selection:</span>
                <input type="text" class="hotkey-input" id="toggleSelectionKey" placeholder="S" maxlength="1">
            </div>
            <div class="hotkey-item">
                <span>Capture All:</span>
                <input type="text" class="hotkey-input" id="captureAllKey" placeholder="I" maxlength="1">
            </div>
            <div class="hotkey-item">
                <span>Quick Capture:</span>
                <input type="text" class="hotkey-input" id="quickCaptureKey" placeholder="Q" maxlength="1">
            </div>
            <div class="hotkey-item">
                <span>Download Selected:</span>
                <input type="text" class="hotkey-input" id="downloadSelectedKey" placeholder="D" maxlength="1">
            </div>
            <div class="hotkey-item">
                <span>Toggle Sidebar:</span>
                <input type="text" class="hotkey-input" id="toggleSidebarKey" placeholder="B" maxlength="1">
            </div>
            <div class="hotkey-item">
                <span>Mouse3 Action:</span>
                <select class="hotkey-input" id="mouse3Action">
                    <option value="quickCapture">Quick Capture</option>
                    <option value="toggleSelection">Toggle Selection</option>
                    <option value="none">None</option>
                </select>
            </div>
            <button class="btn primary" id="saveHotkeys" style="margin-top: 12px;">Save Hotkeys</button>
        </div>
        
        <div class="shortcuts">
            <div class="shortcut">
                <strong>Note:</strong> Hotkeys work when not typing in input fields
            </div>
            <div class="shortcut">
                Use single letters (A-Z) for best compatibility
            </div>
        </div>
    </div>
    
    <!-- Settings Tab -->
    <div class="tab-content" id="settings-tab">
        <div class="hotkeys">
            <h3>Settings</h3>
            <div class="hotkey-item">
                <span>Auto-capture on hover:</span>
                <input type="checkbox" id="autoCaptureHover">
            </div>
            <div class="hotkey-item">
                <span>Show notifications:</span>
                <input type="checkbox" id="showNotifications" checked>
            </div>
            <div class="hotkey-item">
                <span>Selection mode indicator:</span>
                <input type="checkbox" id="showSelectionIndicator" checked>
            </div>
            <div class="hotkey-item">
                <span>Telegram integration:</span>
                <input type="checkbox" id="telegramEnabled" checked>
            </div>
            <div class="hotkey-item">
                <span>Show floating menu:</span>
                <input type="checkbox" id="showFloatingMenu" checked>
            </div>
            <div class="hotkey-item">
                <span>Overlay hover delay (ms):</span>
                <input type="number" class="setting-input" id="overlayHoverDelay" value="1000" min="0" max="5000">
            </div>
            <div class="hotkey-item">
                <span>Hover select delay (ms):</span>
                <input type="number" class="setting-input" id="hoverSelectDelay" value="500" min="100" max="2000">
            </div>
            <div class="hotkey-item">
                <span>Hover deselect delay (ms):</span>
                <input type="number" class="setting-input" id="hoverDeselectDelay" value="300" min="100" max="2000">
            </div>
            <div class="hotkey-item">
                <span>Minimum image width (px):</span>
                <input type="number" class="setting-input" id="minImageWidth" value="100" min="10" max="1000">
            </div>
            <div class="hotkey-item">
                <span>Preferred file types:</span>
                <select class="setting-input" id="preferredFileTypes" multiple>
                    <option value="jpg" selected>JPG</option>
                    <option value="jpeg" selected>JPEG</option>
                    <option value="png" selected>PNG</option>
                    <option value="gif">GIF</option>
                    <option value="webp">WebP</option>
                </select>
            </div>
            
            <div class="setting-group">
              <label for="overlayDraggable">Overlay Draggable:</label>
              <input type="checkbox" id="overlayDraggable" checked>
            </div>
            
            <div class="setting-group">
              <label for="quickToolbarMode">Quick Toolbar Mode:</label>
              <input type="checkbox" id="quickToolbarMode">
              <small>Compact 16x16 button toolbar</small>
            </div>
            
            <div class="setting-group">
              <label for="useOverlayIcons">Use Overlay Icons:</label>
              <input type="checkbox" id="useOverlayIcons">
              <small>Show checkmark icons instead of borders</small>
            </div>
            
            <h4>Overlay Menu Buttons:</h4>
            <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                    <label style="display: flex; align-items: center; gap: 4px; font-size: 11px;">
                        <input type="checkbox" id="btn-overlay" checked> Overlay
                    </label>
                    <label style="display: flex; align-items: center; gap: 4px; font-size: 11px;">
                        <input type="checkbox" id="btn-selection" checked> Selection
                    </label>
                    <label style="display: flex; align-items: center; gap: 4px; font-size: 11px;">
                        <input type="checkbox" id="btn-selectAll" checked> Select All
                    </label>
                    <label style="display: flex; align-items: center; gap: 4px; font-size: 11px;">
                        <input type="checkbox" id="btn-sidebar" checked> Sidebar
                    </label>
                    <label style="display: flex; align-items: center; gap: 4px; font-size: 11px;">
                        <input type="checkbox" id="btn-isolation" checked> Image Mode
                    </label>
                    <label style="display: flex; align-items: center; gap: 4px; font-size: 11px;">
                        <input type="checkbox" id="btn-capture" checked> Capture
                    </label>
                    <label style="display: flex; align-items: center; gap: 4px; font-size: 11px;">
                        <input type="checkbox" id="btn-viewCollection" checked> View Collection
                    </label>
                    <label style="display: flex; align-items: center; gap: 4px; font-size: 11px;">
                        <input type="checkbox" id="btn-download" checked> Download
                    </label>
                    <label style="display: flex; align-items: center; gap: 4px; font-size: 11px;">
                        <input type="checkbox" id="btn-quickToolbar" checked> Quick Toolbar
                    </label>
                </div>
            <button class="btn primary" id="saveSettings" style="margin-top: 12px;">Save Settings</button>
        </div>
        
        <div class="shortcuts">
            <div class="shortcut">
                <strong>Hover Selection:</strong> Enable auto-capture on hover for rapid selection
            </div>
            <div class="shortcut">
                <strong>Delays:</strong> Adjust timing for hover select/deselect behavior
            </div>
            <div class="shortcut">
                <strong>Image Filters:</strong> Set minimum width and preferred file types
            </div>
        </div>
    </div>
    
    <script src="popup.js"></script>
</body>
</html> 
```

```javascript
// Popup script for ImageCapture extension
document.addEventListener('DOMContentLoaded', function() {
  // Tab switching
  const tabs = document.querySelectorAll('.tab');
  const tabContents = document.querySelectorAll('.tab-content');
  
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.getAttribute('data-tab');
      
      // Update active tab
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      
      // Show target content
      tabContents.forEach(content => {
        if (content.id === `${target}-tab`) {
          content.classList.add('active');
        } else {
          content.classList.remove('active');
        }
      });
    });
  });
  
  // Load hotkeys
  loadHotkeys();
  
  // Load settings
  loadSettings();
  
  // Load collection stats
  loadCollectionStats();
  
  // Add event listeners for save buttons
  document.getElementById('saveHotkeys').addEventListener('click', saveHotkeys);
  document.getElementById('saveSettings').addEventListener('click', saveSettings);
  
  // Event listeners
  document.getElementById('toggleSelection').addEventListener('click', () => {
    const button = document.getElementById('toggleSelection');
    const currentText = button.textContent;
    const isCurrentlyOn = currentText.includes('ON');
    
    // Update button text immediately for better UX
    button.textContent = isCurrentlyOn ? '🎯 Selection Mode: OFF' : '🎯 Selection Mode: ON';
    button.style.background = isCurrentlyOn ? '#ff9800' : '#4CAF50';
    
    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
      chrome.tabs.sendMessage(tabs[0].id, {action: 'toggleSelectionMode'});
    });
  });
  
  document.getElementById('toggleSelectAll').addEventListener('click', () => {
    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
      chrome.tabs.sendMessage(tabs[0].id, {action: 'toggleSelectAll'});
    });
  });
  
  document.getElementById('toggleOverlayMenu').addEventListener('click', () => {
    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
      chrome.tabs.sendMessage(tabs[0].id, {action: 'toggleOverlayMenu'});
    });
  });
  
  document.getElementById('downloadAll').addEventListener('click', () => {
    chrome.runtime.sendMessage({action: 'downloadImages'}, (response) => {
      if (response && response.success) {
        alert('Images downloaded successfully!');
      } else {
        alert('No images to download or download failed!');
      }
    });
  });
  
  document.getElementById('clearCollection').addEventListener('click', () => {
    if (confirm('Are you sure you want to clear all captured images?')) {
      chrome.runtime.sendMessage({action: 'clearCapturedImages'}, (response) => {
        if (response && response.success) {
          alert('Collection cleared!');
          loadCollectionStats();
        }
      });
    }
  });
  
  document.getElementById('toggleSidebar').addEventListener('click', () => {
    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
      chrome.tabs.sendMessage(tabs[0].id, {action: 'toggleSidebar'});
    });
  });
  
  document.getElementById('viewCollection').addEventListener('click', () => {
    chrome.runtime.sendMessage({action: 'viewCollection'}, (response) => {
      if (!response || !response.success) {
        alert(response && response.error ? response.error : 'Unable to open collection');
      }
    });
  });
  
  // Send to Telegram button
  document.getElementById('sendToTelegram').addEventListener('click', () => {
    // Show processing indicator
    const btn = document.getElementById('sendToTelegram');
    const originalText = btn.textContent;
    btn.textContent = '📤 Sending...';
    btn.disabled = true;
    
    // Send to backend
    chrome.runtime.sendMessage({action: 'sendToTelegram'}, (response) => {
      if (response && response.success) {
        alert(`✅ Successfully sent ${response.data.successful}/${response.data.total_images} images to Telegram!`);
      } else {
        alert(`❌ Failed to send images: ${response.error || 'Unknown error'}`);
      }
      
      btn.textContent = originalText;
      btn.disabled = false;
    });
  });
});

// Load hotkeys from storage
function loadHotkeys() {
  chrome.storage.local.get(['hotkeys'], (result) => {
    const hotkeys = result.hotkeys || {
      toggleSelection: 'S',
      captureAll: 'I',
      quickCapture: 'Q',
      downloadSelected: 'D',
      toggleSidebar: 'B',
      mouse3Action: 'quickCapture'
    };
    
    document.getElementById('toggleSelectionKey').value = hotkeys.toggleSelection || 'S';
    document.getElementById('captureAllKey').value = hotkeys.captureAll || 'I';
    document.getElementById('quickCaptureKey').value = hotkeys.quickCapture || 'Q';
    document.getElementById('downloadSelectedKey').value = hotkeys.downloadSelected || 'D';
    document.getElementById('toggleSidebarKey').value = hotkeys.toggleSidebar || 'B';
    document.getElementById('mouse3Action').value = hotkeys.mouse3Action || 'quickCapture';
  });
}

// Load settings from storage
function loadSettings() {
  chrome.runtime.sendMessage({action: 'getGlobalState'}, (response) => {
    if (response && response.globalState) {
      const globalState = response.globalState;
      const settings = globalState.settings || {};
      
      // Load basic settings
      document.getElementById('hoverSelectDelay').value = settings.hoverSelectDelay || 500;
      document.getElementById('hoverDeselectDelay').value = settings.hoverDeselectDelay || 300;
      document.getElementById('autoCaptureHover').checked = settings.autoCaptureHover !== false;
      document.getElementById('showNotifications').checked = settings.showNotifications !== false;
      document.getElementById('showSelectionIndicator').checked = settings.showSelectionIndicator !== false;
      document.getElementById('telegramEnabled').checked = settings.telegramEnabled !== false;
      document.getElementById('showFloatingMenu').checked = settings.showFloatingMenu !== false;
      document.getElementById('minImageWidth').value = settings.minImageWidth || 100;
      document.getElementById('overlayHoverDelay').value = settings.overlayHoverDelay || 1000;
      document.getElementById('overlayDraggable').checked = settings.overlayDraggable !== false;
      document.getElementById('quickToolbarMode').checked = settings.quickToolbarMode || false;
      document.getElementById('useOverlayIcons').checked = settings.useOverlayIcons || false;
      
      // Load overlay buttons
      const overlayButtons = settings.overlayButtons || ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'];
      document.getElementById('btn-overlay').checked = overlayButtons.includes('overlay');
      document.getElementById('btn-selection').checked = overlayButtons.includes('selection');
      document.getElementById('btn-selectAll').checked = overlayButtons.includes('selectAll');
      document.getElementById('btn-sidebar').checked = overlayButtons.includes('sidebar');
      document.getElementById('btn-isolation').checked = overlayButtons.includes('isolation');
      document.getElementById('btn-capture').checked = overlayButtons.includes('capture');
      document.getElementById('btn-viewCollection').checked = overlayButtons.includes('viewCollection');
      document.getElementById('btn-download').checked = overlayButtons.includes('download');
      document.getElementById('btn-quickToolbar').checked = overlayButtons.includes('quickToolbar');
    }
  });
}

// Save hotkeys to storage
function saveHotkeys() {
  const hotkeys = {
    toggleSelection: document.getElementById('toggleSelectionKey').value.toUpperCase(),
    captureAll: document.getElementById('captureAllKey').value.toUpperCase(),
    quickCapture: document.getElementById('quickCaptureKey').value.toUpperCase(),
    downloadSelected: document.getElementById('downloadSelectedKey').value.toUpperCase(),
    toggleSidebar: document.getElementById('toggleSidebarKey').value.toUpperCase(),
    mouse3Action: document.getElementById('mouse3Action').value
  };
  
  chrome.storage.local.set({hotkeys: hotkeys}, () => {
    alert('Hotkeys saved successfully!');
  });
}

// Save settings to storage
function saveSettings() {
  // Get overlay buttons configuration
  const overlayButtons = [];
  const buttonTypes = ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'];
  buttonTypes.forEach(buttonType => {
    const checkbox = document.getElementById(`btn-${buttonType}`);
    if (checkbox && checkbox.checked) {
      overlayButtons.push(buttonType);
    }
  });
  
  const settings = {
    hoverSelectDelay: parseInt(document.getElementById('hoverSelectDelay').value),
    hoverDeselectDelay: parseInt(document.getElementById('hoverDeselectDelay').value),
    autoCaptureHover: document.getElementById('autoCaptureHover').checked,
    showNotifications: document.getElementById('showNotifications').checked,
    showSelectionIndicator: document.getElementById('showSelectionIndicator').checked,
    telegramEnabled: document.getElementById('telegramEnabled').checked,
    showFloatingMenu: document.getElementById('showFloatingMenu').checked,
    overlayHoverDelay: parseInt(document.getElementById('overlayHoverDelay').value),
    overlayDraggable: document.getElementById('overlayDraggable').checked,
    minImageWidth: parseInt(document.getElementById('minImageWidth').value),
    preferredFileTypes: Array.from(document.getElementById('preferredFileTypes').selectedOptions).map(option => option.value),
    overlayButtons: overlayButtons,
    quickToolbarMode: document.getElementById('quickToolbarMode').checked,
    useOverlayIcons: document.getElementById('useOverlayIcons').checked
  };
  
  chrome.runtime.sendMessage({action: 'setSettings', settings: settings}, (response) => {
    if (response && response.success) {
      alert('Settings saved successfully!');
      
      // Update content script settings
      chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
        chrome.tabs.sendMessage(tabs[0].id, {action: 'updateSettings', settings: settings});
      });
    }
  });
}

// Load collection statistics
function loadCollectionStats() {
  chrome.runtime.sendMessage({action: 'getCapturedImages'}, (response) => {
    const images = response.images || [];
    const capturedCount = document.getElementById('capturedCount');
    const storageUsed = document.getElementById('storageUsed');
    const lastCapture = document.getElementById('lastCapture');
    
    capturedCount.textContent = images.length;
    
    // Calculate storage size (rough estimate)
    const storageSize = images.length * 100; // Assume 100 bytes per image entry
    storageUsed.textContent = formatBytes(storageSize);
    
    if (images.length > 0) {
      const lastImage = images[images.length - 1];
      const date = new Date(lastImage.timestamp);
      lastCapture.textContent = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    } else {
      lastCapture.textContent = 'Never';
    }
  });
}

// Format bytes to human readable format
function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

```

```javascript
// Background script for ImageCapture extension
let globalState = {
  overlayVisible: false,
  floatingMenuPosition: {
    x: 20,
    y: 20,
    width: 200,
    height: 'auto'
  },
  settings: {
    hoverSelectDelay: 500,
    hoverDeselectDelay: 300,
    autoCaptureHover: false, // Disabled hover selection
    showNotifications: true,
    showSelectionIndicator: true,
    telegramEnabled: true,
    showFloatingMenu: true,
    minImageWidth: 100,
    preferredFileTypes: ['jpg', 'jpeg', 'png'],
    overlayHoverDelay: 1000,
    overlayButtons: ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'],
    overlayDraggable: true,
    quickToolbarMode: false,
    useOverlayIcons: false // New setting for toggleable selection indicators
  },
  capturedImages: [],
  selectedImages: []
};

// Initialize state from storage
chrome.storage.local.get(['globalState', 'capturedImages'], (result) => {
  if (result.globalState) {
    globalState = { ...globalState, ...result.globalState };
  }
  if (result.capturedImages) {
    globalState.capturedImages = result.capturedImages;
  }
  saveGlobalState();
});

// Save global state to storage
function saveGlobalState() {
  chrome.storage.local.set({
    globalState: globalState,
    capturedImages: globalState.capturedImages
  });
}

// Handle messages from content scripts and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'getSettings':
      sendResponse({ settings: globalState.settings });
      break;
      
    case 'setSettings':
      globalState.settings = { ...globalState.settings, ...request.settings };
      saveGlobalState();
      // Broadcast settings update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateSettings', settings: globalState.settings }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'getGlobalState':
      sendResponse({ globalState: globalState });
      break;
      
    case 'setOverlayVisible':
      globalState.overlayVisible = request.visible;
      saveGlobalState();
      // Broadcast overlay visibility update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateOverlayVisibility', visible: request.visible }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'setFloatingMenuPosition':
      globalState.floatingMenuPosition = { ...globalState.floatingMenuPosition, ...request.position };
      saveGlobalState();
      // Broadcast position update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateFloatingMenuPosition', position: globalState.floatingMenuPosition }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'updateSettings':
      globalState.settings = { ...globalState.settings, ...request.settings };
      saveGlobalState();
      // Broadcast settings update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateSettings', settings: globalState.settings }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'captureImage':
      const imageData = {
        url: request.url,
        timestamp: Date.now(),
        domain: new URL(request.url).hostname,
        title: request.title || 'Captured Image'
      };
      
      if (!globalState.capturedImages.find(img => img.url === request.url)) {
        globalState.capturedImages.push(imageData);
        saveGlobalState();
        
        // Broadcast new image to all tabs
        chrome.tabs.query({}, (tabs) => {
          tabs.forEach(tab => {
            chrome.tabs.sendMessage(tab.id, { action: 'newImageCaptured', image: imageData }).catch(() => {});
          });
        });
      }
      sendResponse({ success: true });
      break;
      
    case 'getCapturedImages':
      sendResponse({ images: globalState.capturedImages });
      break;
      
    case 'clearCapturedImages':
      globalState.capturedImages = [];
      saveGlobalState();
      // Broadcast clear to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'imagesCleared' }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'downloadImages':
      console.log('Download request received:', request);
      const imagesToDownload = request.images || globalState.capturedImages;
      if (imagesToDownload.length === 0) {
        console.log('No images to download');
        sendResponse({ success: false, error: 'No images to download' });
        return;
      }
      
      console.log('Images to download:', imagesToDownload);
      
      // Download each image file individually
      let downloadCount = 0;
      const totalImages = imagesToDownload.length;
      
      imagesToDownload.forEach((img, index) => {
        const imageUrl = img.url || img;
        const filename = `image_${Date.now()}_${index + 1}.jpg`;
        
        console.log(`Downloading image ${index + 1}/${totalImages}:`, imageUrl);
        
        // Download the actual image file
        chrome.downloads.download({
          url: imageUrl,
          filename: filename,
          saveAs: false // Don't prompt for each file, use browser's default download folder
        }, (downloadId) => {
          downloadCount++;
          console.log(`Download ${index + 1} completed, downloadId:`, downloadId);
          
          // Check if all downloads are complete
          if (downloadCount === totalImages) {
            console.log('All downloads completed');
            sendResponse({ success: true, downloaded: downloadCount });
          }
        });
      });
      
      return true; // Keep message channel open for async response
      break;
      
    case 'sendToTelegram':
      const imagesToSend = request.images || globalState.capturedImages;
      if (imagesToSend.length === 0) {
        sendResponse({ success: false, error: 'No images to send' });
        return;
      }
      
      const imageUrls = imagesToSend.map(img => img.url);
      
      fetch('http://localhost:5000/send_multiple_telegram', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({image_urls: imageUrls})
      })
      .then(response => response.json())
      .then(data => {
        sendResponse({ success: data.success, data: data });
      })
      .catch(error => {
        sendResponse({ success: false, error: error.message });
      });
      
      return true; // Keep message channel open for async response
      
    case 'viewCollection':
      if (globalState.capturedImages.length === 0) {
        sendResponse({ success: false, error: 'No images in collection' });
        break;
      }
      
      try {
        const collectionHtml = generateCollectionHTML(globalState.capturedImages);
        const blob = new Blob([collectionHtml], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        
        chrome.tabs.create({ url }, (tab) => {
          if (chrome.runtime.lastError) {
            sendResponse({ success: false, error: chrome.runtime.lastError.message });
            URL.revokeObjectURL(url);
            return;
          }
          
          sendResponse({ success: true, tabId: tab && tab.id });
          
          // Revoke the object URL after the tab has loaded
          setTimeout(() => URL.revokeObjectURL(url), 60_000);
        });
        
        return true; // Keep message channel open for async response
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;
      
    default:
      sendResponse({ success: false, error: 'Unknown action' });
  }
});

// Handle tab updates to sync state
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url && tab.url.startsWith('http')) {
    // Send current state to new tab
    setTimeout(() => {
      chrome.tabs.sendMessage(tabId, { 
        action: 'initializeState', 
        globalState: globalState 
      }).catch(() => {});
    }, 1000);
  }
});

// Handle extension installation/update
chrome.runtime.onInstalled.addListener(() => {
  saveGlobalState();
  
  // Create context menu items
  chrome.contextMenus.create({
    id: 'imagecapture-main',
    title: '🖼️ ImageCapture',
    contexts: ['all']
  });
  
  chrome.contextMenus.create({
    id: 'toggle-sidebar',
    title: '📱 Toggle Sidebar',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'toggle-overlay-menu',
    title: '👁️ Toggle Overlay Menu',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'toggle-selection-mode',
    title: '🎯 Toggle Selection Mode',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'select-all-images',
    title: '☑️ Select All Images',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'capture-selected-images',
    title: '📸 Capture Selected Images',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'download-selected-images',
    title: '📥 Download Selected Images',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'clear-collection',
    title: '🗑️ Clear Collection',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
});

function generateCollectionHTML(images) {
  const totalSources = (() => {
    try {
      return new Set(images.map(img => new URL(img.url).hostname)).size;
    } catch (error) {
      console.warn('Failed to compute image hostnames:', error);
      return 1;
    }
  })();
  
  const statsStorage = formatBytes(images.length * 100);
  
  const cards = images.map((img, index) => {
    let hostname = '';
    let filename = 'Image';
    try {
      const url = new URL(img.url);
      hostname = url.hostname;
      filename = url.pathname.split('/').pop() || 'Image';
    } catch (_) {}
    
    const capturedDate = new Date(img.timestamp).toLocaleDateString();
    
    return `
                <div class="image-item" data-index="${index}" onclick="toggleImageSelection(this)">
                    <img src="${img.url}" alt="Captured image ${index + 1}" onerror="this.style.display='none'">
                    <div class="image-info">
                        <div class="image-title">${filename}</div>
                        <div class="image-meta">
                            <span>${hostname}</span>
                            <span>${capturedDate}</span>
                        </div>
                    </div>
                </div>
    `;
  }).join('');
  
  return `
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ImageCapture Collection</title>
        <style>
${generateCollectionStyles()}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🖼️ ImageCapture Collection</h1>
            <p>${images.length} images captured</p>
        </div>
        
        <div class="stats">
            <div class="stat-item">
                <span class="stat-number">${images.length}</span>
                <span class="stat-label">Total Images</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">${totalSources}</span>
                <span class="stat-label">Sources</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">${statsStorage}</span>
                <span class="stat-label">Storage Used</span>
            </div>
        </div>
        
        <div class="controls">
            <button class="btn primary" onclick="downloadSelected()">📥 Download Selected</button>
            <button class="btn telegram" onclick="sendToTelegram()">📤 Send to Telegram</button>
            <button class="btn" onclick="toggleSelectionMode()">🎯 Toggle Selection Mode</button>
            <button class="btn" onclick="selectAll()">☑️ Select All</button>
            <button class="btn danger" onclick="clearCollection()">🗑️ Clear Collection</button>
        </div>
        
        <div class="image-grid" id="imageGrid">
${cards}
        </div>
        
        <div class="selection-mode" id="selectionMode">
            <div class="selection-controls">
                <button class="btn" onclick="selectAll()">☑️ Select All</button>
                <button class="btn" onclick="deselectAll()">☐ Deselect All</button>
                <button class="btn danger" onclick="toggleSelectionMode()">✕ Exit Selection</button>
            </div>
            <div class="selection-stats">
                Selected: <span id="selectedCount">0</span> / ${images.length}
            </div>
        </div>
        
        <script>
${generateCollectionScript(images.length)}
        </script>
    </body>
    </html>
  `;
}

function generateCollectionStyles() {
  return `            body {
                margin: 0;
                padding: 20px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                min-height: 100vh;
            }
            
            .header {
                text-align: center;
                margin-bottom: 30px;
            }
            
            .header h1 {
                margin: 0;
                font-size: 32px;
                font-weight: 600;
                margin-bottom: 10px;
            }
            
            .stats {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 30px;
                backdrop-filter: blur(10px);
                display: flex;
                justify-content: space-around;
                flex-wrap: wrap;
                gap: 20px;
            }
            
            .stat-item {
                text-align: center;
            }
            
            .stat-number {
                font-size: 24px;
                font-weight: bold;
                display: block;
            }
            
            .stat-label {
                font-size: 14px;
                opacity: 0.8;
            }
            
            .controls {
                display: flex;
                gap: 12px;
                margin-bottom: 30px;
                flex-wrap: wrap;
                justify-content: center;
            }
            
            .btn {
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
                padding: 12px 20px;
                color: white;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s ease;
                text-decoration: none;
                display: inline-block;
            }
            
            .btn:hover {
                background: rgba(255, 255, 255, 0.3);
                transform: translateY(-2px);
            }
            
            .btn.primary {
                background: #4CAF50;
                border-color: #4CAF50;
            }
            
            .btn.primary:hover {
                background: #45a049;
            }
            
            .btn.danger {
                background: #f44336;
                border-color: #f44336;
            }
            
            .btn.danger:hover {
                background: #da190b;
            }
            
            .btn.telegram {
                background: #0088cc;
                border-color: #0088cc;
            }
            
            .btn.telegram:hover {
                background: #006699;
            }
            
            .image-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            
            .image-item {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                overflow: hidden;
                backdrop-filter: blur(10px);
                border: 3px solid transparent;
                background-clip: padding-box;
                position: relative;
                transition: all 0.3s ease;
                cursor: pointer;
            }
            
            .image-item::before {
                content: '';
                position: absolute;
                top: -3px;
                left: -3px;
                right: -3px;
                bottom: -3px;
                padding: 3px;
                background: linear-gradient(135deg, rgba(255, 255, 255, 0.3), rgba(255, 255, 255, 0.1));
                mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
                mask-composite: exclude;
                border-radius: 12px;
                opacity: 0.75;
                z-index: -1;
            }
            
            .image-item.selected::before {
                background: linear-gradient(135deg, #4CAF50, #45a049);
                opacity: 1;
            }
            
            .image-item:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
            }
            
            .image-item img {
                width: 100%;
                height: 200px;
                object-fit: cover;
                display: block;
            }
            
            .image-info {
                padding: 15px;
            }
            
            .image-title {
                font-size: 14px;
                font-weight: 600;
                margin-bottom: 8px;
                word-break: break-all;
            }
            
            .image-meta {
                font-size: 12px;
                opacity: 0.8;
                display: flex;
                justify-content: space-between;
            }
            
            .selection-mode {
                position: fixed;
                top: 20px;
                right: 20px;
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 15px;
                border-radius: 8px;
                backdrop-filter: blur(10px);
                z-index: 1000;
                display: none;
            }
            
            .selection-mode.active {
                display: block;
            }
            
            .selection-controls {
                display: flex;
                gap: 10px;
                margin-bottom: 10px;
            }
            
            .selection-stats {
                font-size: 12px;
                opacity: 0.8;
            }
            
            @media (max-width: 768px) {
                .image-grid {
                    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                    gap: 15px;
                }
                
                .controls {
                    flex-direction: column;
                    align-items: center;
                }
                
                .btn {
                    width: 100%;
                    max-width: 300px;
                }
            }`;
}

function generateCollectionScript(totalImages) {
  return `            const images = ${JSON.stringify(globalState.capturedImages)};
            const hasExtensionContext = typeof chrome !== 'undefined' && chrome.runtime && typeof chrome.runtime.sendMessage === 'function';
            let selectionMode = false;
            let selectedImages = new Set();
            
            function toggleSelectionMode() {
                selectionMode = !selectionMode;
                const modeDiv = document.getElementById('selectionMode');
                const toggleBtn = document.querySelector('button[onclick="toggleSelectionMode()"]');
                
                if (selectionMode) {
                    modeDiv.classList.add('active');
                    toggleBtn.textContent = '🎯 Exit Selection Mode';
                    toggleBtn.style.background = '#f44336';
                    document.body.style.cursor = 'crosshair';
                } else {
                    modeDiv.classList.remove('active');
                    toggleBtn.textContent = '🎯 Toggle Selection Mode';
                    toggleBtn.style.background = 'rgba(255, 255, 255, 0.2)';
                    document.body.style.cursor = 'default';
                    selectedImages.clear();
                    updateSelectionDisplay();
                    document.querySelectorAll('.image-item').forEach(item => item.classList.remove('selected'));
                }
            }
            
            function toggleImageSelection(element) {
                if (!selectionMode) return;
                
                const index = element.dataset.index;
                if (selectedImages.has(index)) {
                    selectedImages.delete(index);
                    element.classList.remove('selected');
                } else {
                    selectedImages.add(index);
                    element.classList.add('selected');
                }
                updateSelectionDisplay();
            }
            
            function selectAll() {
                if (!selectionMode) {
                    toggleSelectionMode();
                }
                selectedImages.clear();
                document.querySelectorAll('.image-item').forEach((item, index) => {
                    selectedImages.add(index.toString());
                    item.classList.add('selected');
                });
                updateSelectionDisplay();
            }
            
            function deselectAll() {
                selectedImages.clear();
                document.querySelectorAll('.image-item').forEach(item => {
                    item.classList.remove('selected');
                });
                updateSelectionDisplay();
            }
            
            function updateSelectionDisplay() {
                const counter = document.getElementById('selectedCount');
                if (counter) {
                    counter.textContent = selectedImages.size;
                }
            }
            
            function downloadSelected() {
                const imagesToDownload = selectionMode && selectedImages.size > 0 
                    ? Array.from(selectedImages).map(index => images[index])
                    : images;
                
                const urls = imagesToDownload.map(img => img.url).join('\\n');
                const blob = new Blob([urls], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                
                const a = document.createElement('a');
                a.href = url;
                a.download = 'captured_images.txt';
                a.click();
                
                setTimeout(() => URL.revokeObjectURL(url), 0);
                
                alert(\`\${imagesToDownload.length} image URLs downloaded!\`);
            }
            
            function sendToTelegram() {
                const imagesToSend = selectionMode && selectedImages.size > 0 
                    ? Array.from(selectedImages).map(index => images[index])
                    : images;
                
                const imageUrls = imagesToSend.map(img => img.url);
                
                fetch('http://localhost:5000/send_multiple_telegram', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({image_urls: imageUrls})
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert(\`✅ Successfully sent \${data.successful}/\${data.total_images} images to Telegram!\`);
                    } else {
                        alert(\`❌ Failed to send images: \${data.error}\`);
                    }
                })
                .catch(error => {
                    alert(\`❌ Error sending to Telegram: \${error.message}\`);
                });
            }
            
            function clearCollection() {
                if (confirm('Are you sure you want to clear all captured images?')) {
                    if (!hasExtensionContext) {
                        alert('Extension context unavailable. Please reopen this page from the extension.');
                        return;
                    }
                    chrome.runtime.sendMessage({ action: 'clearCapturedImages' }, (response) => {
                        if (response && response.success) {
                            alert('Collection cleared!');
                            location.reload();
                        } else {
                            alert(response && response.error ? response.error : 'Failed to clear collection');
                        }
                    });
                }
            }
            
            document.addEventListener('keydown', (e) => {
                if (e.target.tagName === 'INPUT') return;
                
                switch (e.key.toLowerCase()) {
                    case 's':
                        if (!e.ctrlKey && !e.metaKey) {
                            e.preventDefault();
                            toggleSelectionMode();
                        }
                        break;
                    case 'escape':
                        if (selectionMode) {
                            toggleSelectionMode();
                        }
                        break;
                }
            });
        `;
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!tab || !tab.url || !tab.url.startsWith('http')) return;
  
  switch (info.menuItemId) {
    case 'toggle-sidebar':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleSidebar' }).catch(() => {});
      break;
      
    case 'toggle-overlay-menu':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleOverlayMenu' }).catch(() => {});
      break;
      
    case 'toggle-selection-mode':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleSelectionMode' }).catch(() => {});
      break;
      
    case 'select-all-images':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleSelectAll' }).catch(() => {});
      break;
      
    case 'capture-selected-images':
      chrome.tabs.sendMessage(tab.id, { action: 'captureSelectedImages' }).catch(() => {});
      break;
      
    case 'download-selected-images':
      chrome.tabs.sendMessage(tab.id, { action: 'downloadSelectedImages' }).catch(() => {});
      break;
      
    case 'clear-collection':
      chrome.tabs.sendMessage(tab.id, { action: 'clearCapturedImages' }).catch(() => {});
      break;
  }
}); 
```

## Summary
- Centralized collection rendering in `background.js` so any UI can trigger the shared `viewCollection` tab flow, complete with a blob-backed page and safe fallbacks for missing extension context.  
```213:241:imagebrowserextension/imagebrowserextensiondev/browserextension/browser-extension/background.js
    case 'viewCollection':
      if (globalState.capturedImages.length === 0) {
        sendResponse({ success: false, error: 'No images in collection' });
        break;
      }
      try {
        const collectionHtml = generateCollectionHTML(globalState.capturedImages);
        const blob = new Blob([collectionHtml], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        chrome.tabs.create({ url }, (tab) => {
          if (chrome.runtime.lastError) {
            sendResponse({ success: false, error: chrome.runtime.lastError.message });
            URL.revokeObjectURL(url);
            return;
          }
          sendResponse({ success: true, tabId: tab && tab.id });
          setTimeout(() => URL.revokeObjectURL(url), 60_000);
        });
        return true;
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;
```
- Added a reusable `openCollectionView` action and surfaced it in both the floating overlay and sidebar controls so users can jump straight to their captures without opening the popup.  
```620:636:imagebrowserextension/imagebrowserextensiondev/browserextension/browser-extension/content.js
    viewCollection: {
      text: '📋 View Collection',
      color: '#3F51B5',
      action: () => openCollectionView()
    },
```
```1181:1259:imagebrowserextension/imagebrowserextensiondev/browserextension/browser-extension/content.js
  const viewCollectionBtn = document.createElement('button');
  viewCollectionBtn.textContent = '📋 View Collection';
  viewCollectionBtn.style.cssText = `
    background: #3F51B5;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  viewCollectionBtn.onclick = () => openCollectionView();
  ...
  controls.appendChild(captureBtn);
  controls.appendChild(viewCollectionBtn);
  controls.appendChild(downloadBtn);
```
- Updated popup settings and the main “View Collection” button to use the new message-based flow, keeping overlay configuration in sync with the additional control.  
```93:200:imagebrowserextension/imagebrowserextensiondev/browserextension/browser-extension/popup.js
  document.getElementById('viewCollection').addEventListener('click', () => {
    chrome.runtime.sendMessage({action: 'viewCollection'}, (response) => {
      if (!response || !response.success) {
        alert(response && response.error ? response.error : 'Unable to open collection');
      }
    });
  });
  ...
      const overlayButtons = settings.overlayButtons || ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'];
      ...
  const buttonTypes = ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'];
```

## Testing
- Not run (extension code changes; manual verification recommended after loading the updated build).

## Next Steps
- Load the unpacked extension and confirm the new buttons appear/enabled by default; tweak stored overlay settings if legacy users should auto-adopt the View Collection shortcut.
- Optionally add hover tooltips for quick-toolbar icons so the compact mode exposes button names.

```javascript
    case 'viewCollection':
      if (globalState.capturedImages.length === 0) {
        sendResponse({ success: false, error: 'No images in collection' });
        break;
      }
      try {
        const collectionHtml = generateCollectionHTML(globalState.capturedImages);
        const blob = new Blob([collectionHtml], { type: 'text/html' });
        const url = URL.createObjectURL(blob);
        chrome.tabs.create({ url }, (tab) => {
          if (chrome.runtime.lastError) {
            sendResponse({ success: false, error: chrome.runtime.lastError.message });
            URL.revokeObjectURL(url);
            return;
          }
          sendResponse({ success: true, tabId: tab && tab.id });
          setTimeout(() => URL.revokeObjectURL(url), 60_000);
        });
        return true;
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;
```

```javascript
    viewCollection: {
      text: '📋 View Collection',
      color: '#3F51B5',
      action: () => openCollectionView()
    },
```

```javascript
  const viewCollectionBtn = document.createElement('button');
  viewCollectionBtn.textContent = '📋 View Collection';
  viewCollectionBtn.style.cssText = `
    background: #3F51B5;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  viewCollectionBtn.onclick = () => openCollectionView();
  ...
  controls.appendChild(captureBtn);
  controls.appendChild(viewCollectionBtn);
  controls.appendChild(downloadBtn);
```

```javascript
  document.getElementById('viewCollection').addEventListener('click', () => {
    chrome.runtime.sendMessage({action: 'viewCollection'}, (response) => {
      if (!response || !response.success) {
        alert(response && response.error ? response.error : 'Unable to open collection');
      }
    });
  });
  ...
      const overlayButtons = settings.overlayButtons || ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'];
      ...
  const buttonTypes = ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'];
```

---

**User**

i get these errors 



Executing inline event handler violates the following Content Security Policy directive 'script-src 'self' 'wasm-unsafe-eval' 'inline-speculation-rules' http://localhost:* http://127.0.0.1:*'. Either the 'unsafe-inline' keyword, a hash ('sha256-...'), or a nonce ('nonce-...') is required to enable inline execution. Note that hashes do not apply to event handlers, style attributes and javascript: navigations unless the 'unsafe-hashes' keyword is present. The action has been blocked.

Executing inline script violates the following Content Security Policy directive 'script-src 'self''. Either the 'unsafe-inline' keyword, a hash ('sha256-sOFlDJzMOWEL+RsFvxD9M/BuODUhXHZtzeErLHdppXI='), or a nonce ('nonce-...') is required to enable inline execution. The action has been blocked.

Executing inline script violates the following Content Security Policy directive 'script-src 'self' 'wasm-unsafe-eval' 'inline-speculation-rules' http://localhost:* http://127.0.0.1:*'. Either the 'unsafe-inline' keyword, a hash ('sha256-sOFlDJzMOWEL+RsFvxD9M/BuODUhXHZtzeErLHdppXI='), or a nonce ('nonce-...') is required to enable inline execution. The action has been blocked.

Uncaught Error: Extension context invalidated.

Uncaught Error: Extension context invalidated.

Uncaught (in promise) Error: Could not establish connection. Receiving end does not exist.

Implement the plan as specified, it is attached for your reference. Do NOT edit the plan file itself.

To-do's from the plan have already been created. Do not create them again. Mark them as in_progress as you work, starting with the first one. Don't stop until you have completed all the to-dos.

---

**Cursor**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ImageCapture Collection</title>
    <link rel="stylesheet" href="collection.css">
</head>
<body>
    <div class="header">
        <h1>🖼️ ImageCapture Collection</h1>
        <p id="imageCount">0 images captured</p>
    </div>

    <div class="empty-state" id="emptyState">
        <div class="empty-icon">📁</div>
        <h2>No images captured yet</h2>
        <p>Use the extension to capture images and they will appear here.</p>
        <button class="btn primary" id="openHelp">How to capture</button>
    </div>

    <div class="stats" id="statsPanel">
        <div class="stat-item">
            <span class="stat-number" id="totalImages">0</span>
            <span class="stat-label">Total Images</span>
        </div>
        <div class="stat-item">
            <span class="stat-number" id="totalSources">0</span>
            <span class="stat-label">Sources</span>
        </div>
        <div class="stat-item">
            <span class="stat-number" id="storageUsedValue">0 Bytes</span>
            <span class="stat-label">Storage Used</span>
        </div>
    </div>

    <div class="controls" id="controls">
        <button class="btn primary" id="downloadSelected">📥 Download Selected</button>
        <button class="btn telegram" id="sendToTelegram">📤 Send to Telegram</button>
        <button class="btn" id="toggleSelectionMode">🎯 Toggle Selection Mode</button>
        <button class="btn" id="selectAll">☑️ Select All</button>
        <button class="btn danger" id="clearCollection">🗑️ Clear Collection</button>
    </div>

    <div class="image-grid" id="imageGrid"></div>

    <div class="selection-mode" id="selectionBanner">
        <div class="selection-controls">
            <button class="btn" id="bannerSelectAll">☑️ Select All</button>
            <button class="btn" id="bannerDeselectAll">☐ Deselect All</button>
            <button class="btn danger" id="bannerExitSelection">✕ Exit Selection</button>
        </div>
        <div class="selection-stats">
            Selected: <span id="selectedCount">0</span>
        </div>
    </div>

    <div class="toast" id="toast" role="status" aria-live="polite"></div>

    <script src="collection.js"></script>
</body>
</html>

```

```css
body {
    margin: 0;
    padding: 20px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    min-height: 100vh;
}

.header {
    text-align: center;
    margin-bottom: 30px;
}

.header h1 {
    margin: 0;
    font-size: 32px;
    font-weight: 600;
    margin-bottom: 10px;
}

.stats {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 30px;
    backdrop-filter: blur(10px);
    display: flex;
    justify-content: space-around;
    flex-wrap: wrap;
    gap: 20px;
}

.stat-item {
    text-align: center;
}

.stat-number {
    font-size: 24px;
    font-weight: bold;
    display: block;
}

.stat-label {
    font-size: 14px;
    opacity: 0.8;
}

.controls {
    display: flex;
    gap: 12px;
    margin-bottom: 30px;
    flex-wrap: wrap;
    justify-content: center;
}

.btn {
    background: rgba(255, 255, 255, 0.2);
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 8px;
    padding: 12px 20px;
    color: white;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    text-decoration: none;
    display: inline-block;
}

.btn:hover {
    background: rgba(255, 255, 255, 0.3);
    transform: translateY(-2px);
}

.btn.primary {
    background: #4CAF50;
    border-color: #4CAF50;
}

.btn.primary:hover {
    background: #45a049;
}

.btn.danger {
    background: #f44336;
    border-color: #f44336;
}

.btn.danger:hover {
    background: #da190b;
}

.btn.telegram {
    background: #0088cc;
    border-color: #0088cc;
}

.btn.telegram:hover {
    background: #006699;
}

.image-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.image-item {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    overflow: hidden;
    backdrop-filter: blur(10px);
    border: 3px solid transparent;
    background-clip: padding-box;
    position: relative;
    transition: all 0.3s ease;
    cursor: pointer;
}

.image-item::before {
    content: '';
    position: absolute;
    top: -3px;
    left: -3px;
    right: -3px;
    bottom: -3px;
    padding: 3px;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.3), rgba(255, 255, 255, 0.1));
    mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    mask-composite: exclude;
    border-radius: 12px;
    opacity: 0.75;
    z-index: -1;
}

.image-item.selected::before {
    background: linear-gradient(135deg, #4CAF50, #45a049);
    opacity: 1;
}

.image-item:hover {
    transform: translateY(-5px);
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
}

.image-item img {
    width: 100%;
    height: 200px;
    object-fit: cover;
    display: block;
}

.image-info {
    padding: 15px;
}

.image-title {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 8px;
    word-break: break-word;
}

.image-meta {
    font-size: 12px;
    opacity: 0.8;
    display: flex;
    justify-content: space-between;
    gap: 8px;
}

.selection-mode {
    position: fixed;
    top: 20px;
    right: 20px;
    background: rgba(0, 0, 0, 0.8);
    color: white;
    padding: 15px;
    border-radius: 8px;
    backdrop-filter: blur(10px);
    z-index: 1000;
    display: none;
}

.selection-mode.active {
    display: block;
}

.selection-controls {
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
}

.selection-stats {
    font-size: 12px;
    opacity: 0.8;
}

.toast {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0, 0, 0, 0.85);
    color: white;
    padding: 10px 16px;
    border-radius: 6px;
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.3s ease, transform 0.3s ease;
    z-index: 1100;
}

.toast.show {
    opacity: 1;
    transform: translate(-50%, -10px);
}

.empty-state {
    display: none;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 40px;
    margin: 40px auto;
    max-width: 480px;
    text-align: center;
}

.empty-icon {
    font-size: 48px;
}

.empty-state.active {
    display: flex;
}

@media (max-width: 768px) {
    .image-grid {
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 15px;
    }

    .controls {
        flex-direction: column;
        align-items: center;
    }

    .btn {
        width: 100%;
        max-width: 300px;
    }
}

```

```javascript
(() => {
  const imageGrid = document.getElementById('imageGrid');
  const statsPanel = document.getElementById('statsPanel');
  const controls = document.getElementById('controls');
  const selectionBanner = document.getElementById('selectionBanner');
  const selectedCountEl = document.getElementById('selectedCount');
  const imageCountLabel = document.getElementById('imageCount');
  const totalImagesEl = document.getElementById('totalImages');
  const totalSourcesEl = document.getElementById('totalSources');
  const storageUsedEl = document.getElementById('storageUsedValue');
  const emptyState = document.getElementById('emptyState');
  const toast = document.getElementById('toast');

  const btnDownload = document.getElementById('downloadSelected');
  const btnTelegram = document.getElementById('sendToTelegram');
  const btnToggleSelection = document.getElementById('toggleSelectionMode');
  const btnSelectAll = document.getElementById('selectAll');
  const btnClear = document.getElementById('clearCollection');
  const btnBannerSelectAll = document.getElementById('bannerSelectAll');
  const btnBannerDeselectAll = document.getElementById('bannerDeselectAll');
  const btnBannerExit = document.getElementById('bannerExitSelection');
  const btnOpenHelp = document.getElementById('openHelp');

  let images = [];
  let selectionMode = false;
  const selectedIndices = new Set();

  document.addEventListener('DOMContentLoaded', initialize);
  document.addEventListener('keydown', handleShortcuts);

  btnDownload.addEventListener('click', handleDownloadSelected);
  btnTelegram.addEventListener('click', handleSendToTelegram);
  btnToggleSelection.addEventListener('click', toggleSelectionMode);
  btnSelectAll.addEventListener('click', selectAllImages);
  btnClear.addEventListener('click', handleClearCollection);
  btnBannerSelectAll.addEventListener('click', selectAllImages);
  btnBannerDeselectAll.addEventListener('click', deselectAllImages);
  btnBannerExit.addEventListener('click', () => setSelectionMode(false));
  btnOpenHelp.addEventListener('click', openHelpDocumentation);

  function initialize() {
    chrome.runtime.sendMessage({ action: 'getCapturedImages' }, (response) => {
      if (!response || !Array.isArray(response.images)) {
        showToast('Unable to load captured images');
        showEmptyState();
        return;
      }

      images = response.images;
      renderImages();
      updateStats();

      if (images.length === 0) {
        showEmptyState();
      }
    });
  }

  function renderImages() {
    imageGrid.replaceChildren();

    images.forEach((image, index) => {
      const card = document.createElement('div');
      card.className = 'image-item';
      card.dataset.index = index.toString();

      const img = document.createElement('img');
      img.src = image.url;
      img.alt = `Captured image ${index + 1}`;
      img.onerror = () => { img.style.display = 'none'; };

      const info = document.createElement('div');
      info.className = 'image-info';

      const title = document.createElement('div');
      title.className = 'image-title';
      title.textContent = extractFilename(image.url);

      const meta = document.createElement('div');
      meta.className = 'image-meta';

      const hostnameSpan = document.createElement('span');
      hostnameSpan.textContent = extractHostname(image.url);

      const dateSpan = document.createElement('span');
      dateSpan.textContent = formatDate(image.timestamp);

      meta.appendChild(hostnameSpan);
      meta.appendChild(dateSpan);
      info.appendChild(title);
      info.appendChild(meta);

      card.appendChild(img);
      card.appendChild(info);

      card.addEventListener('click', () => handleImageClick(index, card));

      imageGrid.appendChild(card);
    });
  }

  function handleImageClick(index, card) {
    if (!selectionMode) return;

    if (selectedIndices.has(index)) {
      selectedIndices.delete(index);
      card.classList.remove('selected');
    } else {
      selectedIndices.add(index);
      card.classList.add('selected');
    }

    updateSelectionCounter();
  }

  function handleDownloadSelected() {
    const targets = getSelectedImages();
    if (targets.length === 0) {
      showToast('Select images to download first');
      return;
    }

    chrome.runtime.sendMessage({ action: 'downloadImages', images: targets }, (response) => {
      if (response && response.success) {
        showToast(`Downloading ${response.downloaded || targets.length} images`);
      } else {
        showToast(response && response.error ? response.error : 'Failed to download images');
      }
    });
  }

  function handleSendToTelegram() {
    const targets = getSelectedImages();
    if (targets.length === 0 && selectionMode) {
      showToast('Select images to send first');
      return;
    }

    const imagePayload = targets.length > 0 ? targets : images;
    if (imagePayload.length === 0) {
      showToast('No images available to send');
      return;
    }

    chrome.runtime.sendMessage({ action: 'sendToTelegram', images: imagePayload }, (response) => {
      if (response && response.success) {
        showToast(`Sent ${response.data.successful}/${response.data.total_images} images to Telegram`);
      } else {
        showToast(response && response.error ? response.error : 'Failed to send images');
      }
    });
  }

  function handleClearCollection() {
    if (!confirm('Are you sure you want to clear all captured images?')) {
      return;
    }

    chrome.runtime.sendMessage({ action: 'clearCapturedImages' }, (response) => {
      if (response && response.success) {
        showToast('Collection cleared');
        images = [];
        selectedIndices.clear();
        renderImages();
        updateStats();
        setSelectionMode(false);
        showEmptyState();
      } else {
        showToast(response && response.error ? response.error : 'Failed to clear collection');
      }
    });
  }

  function toggleSelectionMode() {
    setSelectionMode(!selectionMode);
  }

  function setSelectionMode(enabled) {
    selectionMode = enabled;
    btnToggleSelection.textContent = selectionMode ? '🎯 Exit Selection Mode' : '🎯 Toggle Selection Mode';
    btnToggleSelection.classList.toggle('danger', selectionMode);
    selectionBanner.classList.toggle('active', selectionMode);

    if (!selectionMode) {
      selectedIndices.clear();
      document.querySelectorAll('.image-item.selected').forEach((el) => el.classList.remove('selected'));
    }

    document.body.style.cursor = selectionMode ? 'crosshair' : 'default';
    updateSelectionCounter();
  }

  function selectAllImages() {
    if (!selectionMode) {
      setSelectionMode(true);
    }

    selectedIndices.clear();
    images.forEach((_, index) => selectedIndices.add(index));
    document.querySelectorAll('.image-item').forEach((el) => el.classList.add('selected'));
    updateSelectionCounter();
  }

  function deselectAllImages() {
    selectedIndices.clear();
    document.querySelectorAll('.image-item.selected').forEach((el) => el.classList.remove('selected'));
    updateSelectionCounter();
  }

  function getSelectedImages() {
    if (!selectionMode || selectedIndices.size === 0) {
      return selectionMode ? [] : images;
    }
    return Array.from(selectedIndices).map((index) => images[index]);
  }

  function updateSelectionCounter() {
    selectedCountEl.textContent = selectedIndices.size;
  }

  function updateStats() {
    const totalImages = images.length;
    imageCountLabel.textContent = `${totalImages} ${totalImages === 1 ? 'image' : 'images'} captured`;
    totalImagesEl.textContent = totalImages;

    const hostnames = new Set();
    images.forEach((img) => {
      const hostname = extractHostname(img.url);
      if (hostname) hostnames.add(hostname);
    });
    totalSourcesEl.textContent = hostnames.size;

    storageUsedEl.textContent = formatBytes(totalImages * 100);

    const hasImages = totalImages > 0;
    statsPanel.style.display = hasImages ? 'flex' : 'none';
    controls.style.display = hasImages ? 'flex' : 'none';
    imageGrid.style.display = hasImages ? 'grid' : 'none';
  }

  function showEmptyState() {
    statsPanel.style.display = 'none';
    controls.style.display = 'none';
    imageGrid.style.display = 'none';
    emptyState.classList.add('active');
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(showToast.timeoutId);
    showToast.timeoutId = setTimeout(() => {
      toast.classList.remove('show');
    }, 2500);
  }

  function handleShortcuts(event) {
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
      return;
    }

    switch (event.key.toLowerCase()) {
      case 's':
        event.preventDefault();
        toggleSelectionMode();
        break;
      case 'a':
        if (selectionMode) {
          event.preventDefault();
          selectAllImages();
        }
        break;
      case 'd':
        if (selectionMode) {
          event.preventDefault();
          deselectAllImages();
        }
        break;
      case 'escape':
        if (selectionMode) {
          event.preventDefault();
          setSelectionMode(false);
        }
        break;
      default:
        break;
    }
  }

  function extractHostname(url) {
    try {
      return new URL(url).hostname;
    } catch (_) {
      return 'unknown';
    }
  }

  function extractFilename(url) {
    try {
      const path = new URL(url).pathname;
      const candidate = path.split('/').pop();
      return candidate || 'Image';
    } catch (_) {
      return 'Image';
    }
  }

  function formatDate(timestamp) {
    if (!timestamp) return 'Unknown';
    return new Date(timestamp).toLocaleDateString();
  }

  function formatBytes(bytes) {
    if (bytes <= 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  }

  function openHelpDocumentation() {
    chrome.tabs.create({
      url: 'https://github.com', // Placeholder until dedicated docs available
      active: true
    });
  }
})();

```

```javascript
(() => {
  const imageGrid = document.getElementById('imageGrid');
  const statsPanel = document.getElementById('statsPanel');
  const controls = document.getElementById('controls');
  const selectionBanner = document.getElementById('selectionBanner');
  const selectedCountEl = document.getElementById('selectedCount');
  const imageCountLabel = document.getElementById('imageCount');
  const totalImagesEl = document.getElementById('totalImages');
  const totalSourcesEl = document.getElementById('totalSources');
  const storageUsedEl = document.getElementById('storageUsedValue');
  const emptyState = document.getElementById('emptyState');
  const toast = document.getElementById('toast');

  const btnDownload = document.getElementById('downloadSelected');
  const btnTelegram = document.getElementById('sendToTelegram');
  const btnToggleSelection = document.getElementById('toggleSelectionMode');
  const btnSelectAll = document.getElementById('selectAll');
  const btnClear = document.getElementById('clearCollection');
  const btnBannerSelectAll = document.getElementById('bannerSelectAll');
  const btnBannerDeselectAll = document.getElementById('bannerDeselectAll');
  const btnBannerExit = document.getElementById('bannerExitSelection');
  const btnOpenHelp = document.getElementById('openHelp');

  let images = [];
  let selectionMode = false;
  const selectedIndices = new Set();

  document.addEventListener('DOMContentLoaded', initialize);
  document.addEventListener('keydown', handleShortcuts);

  btnDownload.addEventListener('click', handleDownloadSelected);
  btnTelegram.addEventListener('click', handleSendToTelegram);
  btnToggleSelection.addEventListener('click', toggleSelectionMode);
  btnSelectAll.addEventListener('click', selectAllImages);
  btnClear.addEventListener('click', handleClearCollection);
  btnBannerSelectAll.addEventListener('click', selectAllImages);
  btnBannerDeselectAll.addEventListener('click', deselectAllImages);
  btnBannerExit.addEventListener('click', () => setSelectionMode(false));
  btnOpenHelp.addEventListener('click', () => showToast('Capture images via the context menu or floating toolbar.'));

  function initialize() {
    chrome.runtime.sendMessage({ action: 'getCapturedImages' }, (response) => {
      if (!response || !Array.isArray(response.images)) {
        showToast('Unable to load captured images');
        showEmptyState();
        return;
      }

      images = response.images;
      renderImages();
      updateStats();

      if (images.length === 0) {
        showEmptyState();
      }
    });
  }

  function renderImages() {
    imageGrid.replaceChildren();

    images.forEach((image, index) => {
      const card = document.createElement('div');
      card.className = 'image-item';
      card.dataset.index = index.toString();

      const img = document.createElement('img');
      img.src = image.url;
      img.alt = `Captured image ${index + 1}`;
      img.onerror = () => { img.style.display = 'none'; };

      const info = document.createElement('div');
      info.className = 'image-info';

      const title = document.createElement('div');
      title.className = 'image-title';
      title.textContent = extractFilename(image.url);

      const meta = document.createElement('div');
      meta.className = 'image-meta';

      const hostnameSpan = document.createElement('span');
      hostnameSpan.textContent = extractHostname(image.url);

      const dateSpan = document.createElement('span');
      dateSpan.textContent = formatDate(image.timestamp);

      meta.appendChild(hostnameSpan);
      meta.appendChild(dateSpan);
      info.appendChild(title);
      info.appendChild(meta);

      card.appendChild(img);
      card.appendChild(info);

      card.addEventListener('click', () => handleImageClick(index, card));

      imageGrid.appendChild(card);
    });
  }

  function handleImageClick(index, card) {
    if (!selectionMode) return;

    if (selectedIndices.has(index)) {
      selectedIndices.delete(index);
      card.classList.remove('selected');
    } else {
      selectedIndices.add(index);
      card.classList.add('selected');
    }

    updateSelectionCounter();
  }

  function handleDownloadSelected() {
    const targets = getSelectedImages();
    if (targets.length === 0) {
      showToast('Select images to download first');
      return;
    }

    chrome.runtime.sendMessage({ action: 'downloadImages', images: targets }, (response) => {
      if (response && response.success) {
        showToast(`Downloading ${response.downloaded || targets.length} images`);
      } else {
        showToast(response && response.error ? response.error : 'Failed to download images');
      }
    });
  }

  function handleSendToTelegram() {
    const targets = getSelectedImages();
    if (targets.length === 0 && selectionMode) {
      showToast('Select images to send first');
      return;
    }

    const imagePayload = targets.length > 0 ? targets : images;
    if (imagePayload.length === 0) {
      showToast('No images available to send');
      return;
    }

    chrome.runtime.sendMessage({ action: 'sendToTelegram', images: imagePayload }, (response) => {
      if (response && response.success) {
        showToast(`Sent ${response.data.successful}/${response.data.total_images} images to Telegram`);
      } else {
        showToast(response && response.error ? response.error : 'Failed to send images');
      }
    });
  }

  function handleClearCollection() {
    if (!confirm('Are you sure you want to clear all captured images?')) {
      return;
    }

    chrome.runtime.sendMessage({ action: 'clearCapturedImages' }, (response) => {
      if (response && response.success) {
        showToast('Collection cleared');
        images = [];
        selectedIndices.clear();
        renderImages();
        updateStats();
        setSelectionMode(false);
        showEmptyState();
      } else {
        showToast(response && response.error ? response.error : 'Failed to clear collection');
      }
    });
  }

  function toggleSelectionMode() {
    setSelectionMode(!selectionMode);
  }

  function setSelectionMode(enabled) {
    selectionMode = enabled;
    btnToggleSelection.textContent = selectionMode ? '🎯 Exit Selection Mode' : '🎯 Toggle Selection Mode';
    btnToggleSelection.classList.toggle('danger', selectionMode);
    selectionBanner.classList.toggle('active', selectionMode);

    if (!selectionMode) {
      selectedIndices.clear();
      document.querySelectorAll('.image-item.selected').forEach((el) => el.classList.remove('selected'));
    }

    document.body.style.cursor = selectionMode ? 'crosshair' : 'default';
    updateSelectionCounter();
  }

  function selectAllImages() {
    if (!selectionMode) {
      setSelectionMode(true);
    }

    selectedIndices.clear();
    images.forEach((_, index) => selectedIndices.add(index));
    document.querySelectorAll('.image-item').forEach((el) => el.classList.add('selected'));
    updateSelectionCounter();
  }

  function deselectAllImages() {
    selectedIndices.clear();
    document.querySelectorAll('.image-item.selected').forEach((el) => el.classList.remove('selected'));
    updateSelectionCounter();
  }

  function getSelectedImages() {
    if (!selectionMode || selectedIndices.size === 0) {
      return selectionMode ? [] : images;
    }
    return Array.from(selectedIndices).map((index) => images[index]);
  }

  function updateSelectionCounter() {
    selectedCountEl.textContent = selectedIndices.size;
  }

  function updateStats() {
    const totalImages = images.length;
    imageCountLabel.textContent = `${totalImages} ${totalImages === 1 ? 'image' : 'images'} captured`;
    totalImagesEl.textContent = totalImages;

    const hostnames = new Set();
    images.forEach((img) => {
      const hostname = extractHostname(img.url);
      if (hostname) hostnames.add(hostname);
    });
    totalSourcesEl.textContent = hostnames.size;

    storageUsedEl.textContent = formatBytes(totalImages * 100);

    const hasImages = totalImages > 0;
    statsPanel.style.display = hasImages ? 'flex' : 'none';
    controls.style.display = hasImages ? 'flex' : 'none';
    imageGrid.style.display = hasImages ? 'grid' : 'none';
  }

  function showEmptyState() {
    statsPanel.style.display = 'none';
    controls.style.display = 'none';
    imageGrid.style.display = 'none';
    emptyState.classList.add('active');
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(showToast.timeoutId);
    showToast.timeoutId = setTimeout(() => {
      toast.classList.remove('show');
    }, 2500);
  }

  function handleShortcuts(event) {
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) {
      return;
    }

    switch (event.key.toLowerCase()) {
      case 's':
        event.preventDefault();
        toggleSelectionMode();
        break;
      case 'a':
        if (selectionMode) {
          event.preventDefault();
          selectAllImages();
        }
        break;
      case 'd':
        if (selectionMode) {
          event.preventDefault();
          deselectAllImages();
        }
        break;
      case 'escape':
        if (selectionMode) {
          event.preventDefault();
          setSelectionMode(false);
        }
        break;
      default:
        break;
    }
  }

  function extractHostname(url) {
    try {
      return new URL(url).hostname;
    } catch (_) {
      return 'unknown';
    }
  }

  function extractFilename(url) {
    try {
      const path = new URL(url).pathname;
      const candidate = path.split('/').pop();
      return candidate || 'Image';
    } catch (_) {
      return 'Image';
    }
  }

  function formatDate(timestamp) {
    if (!timestamp) return 'Unknown';
    return new Date(timestamp).toLocaleDateString();
  }

  function formatBytes(bytes) {
    if (bytes <= 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  }

})();


```

```javascript
// Background script for ImageCapture extension
let globalState = {
  overlayVisible: false,
  floatingMenuPosition: {
    x: 20,
    y: 20,
    width: 200,
    height: 'auto'
  },
  settings: {
    hoverSelectDelay: 500,
    hoverDeselectDelay: 300,
    autoCaptureHover: false, // Disabled hover selection
    showNotifications: true,
    showSelectionIndicator: true,
    telegramEnabled: true,
    showFloatingMenu: true,
    minImageWidth: 100,
    preferredFileTypes: ['jpg', 'jpeg', 'png'],
    overlayHoverDelay: 1000,
    overlayButtons: ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'],
    overlayDraggable: true,
    quickToolbarMode: false,
    useOverlayIcons: false // New setting for toggleable selection indicators
  },
  capturedImages: [],
  selectedImages: []
};

// Initialize state from storage
chrome.storage.local.get(['globalState', 'capturedImages'], (result) => {
  if (result.globalState) {
    globalState = { ...globalState, ...result.globalState };
  }
  if (result.capturedImages) {
    globalState.capturedImages = result.capturedImages;
  }
  saveGlobalState();
});

// Save global state to storage
function saveGlobalState() {
  chrome.storage.local.set({
    globalState: globalState,
    capturedImages: globalState.capturedImages
  });
}

// Handle messages from content scripts and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'getSettings':
      sendResponse({ settings: globalState.settings });
      break;
      
    case 'setSettings':
      globalState.settings = { ...globalState.settings, ...request.settings };
      saveGlobalState();
      // Broadcast settings update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateSettings', settings: globalState.settings }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'getGlobalState':
      sendResponse({ globalState: globalState });
      break;
      
    case 'setOverlayVisible':
      globalState.overlayVisible = request.visible;
      saveGlobalState();
      // Broadcast overlay visibility update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateOverlayVisibility', visible: request.visible }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'setFloatingMenuPosition':
      globalState.floatingMenuPosition = { ...globalState.floatingMenuPosition, ...request.position };
      saveGlobalState();
      // Broadcast position update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateFloatingMenuPosition', position: globalState.floatingMenuPosition }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'updateSettings':
      globalState.settings = { ...globalState.settings, ...request.settings };
      saveGlobalState();
      // Broadcast settings update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateSettings', settings: globalState.settings }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'captureImage':
      const imageData = {
        url: request.url,
        timestamp: Date.now(),
        domain: new URL(request.url).hostname,
        title: request.title || 'Captured Image'
      };
      
      if (!globalState.capturedImages.find(img => img.url === request.url)) {
        globalState.capturedImages.push(imageData);
        saveGlobalState();
        
        // Broadcast new image to all tabs
        chrome.tabs.query({}, (tabs) => {
          tabs.forEach(tab => {
            chrome.tabs.sendMessage(tab.id, { action: 'newImageCaptured', image: imageData }).catch(() => {});
          });
        });
      }
      sendResponse({ success: true });
      break;
      
    case 'getCapturedImages':
      sendResponse({ images: globalState.capturedImages });
      break;
      
    case 'clearCapturedImages':
      globalState.capturedImages = [];
      saveGlobalState();
      // Broadcast clear to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'imagesCleared' }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'downloadImages':
      console.log('Download request received:', request);
      const imagesToDownload = request.images || globalState.capturedImages;
      if (imagesToDownload.length === 0) {
        console.log('No images to download');
        sendResponse({ success: false, error: 'No images to download' });
        return;
      }
      
      console.log('Images to download:', imagesToDownload);
      
      // Download each image file individually
      let downloadCount = 0;
      const totalImages = imagesToDownload.length;
      
      imagesToDownload.forEach((img, index) => {
        const imageUrl = img.url || img;
        const filename = `image_${Date.now()}_${index + 1}.jpg`;
        
        console.log(`Downloading image ${index + 1}/${totalImages}:`, imageUrl);
        
        // Download the actual image file
        chrome.downloads.download({
          url: imageUrl,
          filename: filename,
          saveAs: false // Don't prompt for each file, use browser's default download folder
        }, (downloadId) => {
          downloadCount++;
          console.log(`Download ${index + 1} completed, downloadId:`, downloadId);
          
          // Check if all downloads are complete
          if (downloadCount === totalImages) {
            console.log('All downloads completed');
            sendResponse({ success: true, downloaded: downloadCount });
          }
        });
      });
      
      return true; // Keep message channel open for async response
      break;
      
    case 'sendToTelegram':
      const imagesToSend = request.images || globalState.capturedImages;
      if (imagesToSend.length === 0) {
        sendResponse({ success: false, error: 'No images to send' });
        return;
      }
      
      const imageUrls = imagesToSend.map(img => img.url);
      
      fetch('http://localhost:5000/send_multiple_telegram', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({image_urls: imageUrls})
      })
      .then(response => response.json())
      .then(data => {
        sendResponse({ success: data.success, data: data });
      })
      .catch(error => {
        sendResponse({ success: false, error: error.message });
      });
      
      return true; // Keep message channel open for async response
      
    case 'viewCollection':
      try {
        const pageUrl = chrome.runtime.getURL('collection.html');
        chrome.tabs.create({ url: pageUrl }, (tab) => {
          if (chrome.runtime.lastError) {
            sendResponse({ success: false, error: chrome.runtime.lastError.message });
            return;
          }
          sendResponse({ success: true, tabId: tab && tab.id });
        });
        return true; // Keep channel open for async response
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;
      
    default:
      sendResponse({ success: false, error: 'Unknown action' });
  }
});

// Handle tab updates to sync state
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url && tab.url.startsWith('http')) {
    // Send current state to new tab
    setTimeout(() => {
      chrome.tabs.sendMessage(tabId, { 
        action: 'initializeState', 
        globalState: globalState 
      }).catch(() => {});
    }, 1000);
  }
});

// Handle extension installation/update
chrome.runtime.onInstalled.addListener(() => {
  saveGlobalState();
  
  // Create context menu items
  chrome.contextMenus.create({
    id: 'imagecapture-main',
    title: '🖼️ ImageCapture',
    contexts: ['all']
  });
  
  chrome.contextMenus.create({
    id: 'toggle-sidebar',
    title: '📱 Toggle Sidebar',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'toggle-overlay-menu',
    title: '👁️ Toggle Overlay Menu',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'toggle-selection-mode',
    title: '🎯 Toggle Selection Mode',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'select-all-images',
    title: '☑️ Select All Images',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'capture-selected-images',
    title: '📸 Capture Selected Images',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'download-selected-images',
    title: '📥 Download Selected Images',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'clear-collection',
    title: '🗑️ Clear Collection',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
});

function generateCollectionHTML(images) {
  const totalSources = (() => {
    try {
      return new Set(images.map(img => new URL(img.url).hostname)).size;
    } catch (error) {
      console.warn('Failed to compute image hostnames:', error);
      return 1;
    }
  })();
  
  const statsStorage = formatBytes(images.length * 100);
  
  const cards = images.map((img, index) => {
    let hostname = '';
    let filename = 'Image';
    try {
      const url = new URL(img.url);
      hostname = url.hostname;
      filename = url.pathname.split('/').pop() || 'Image';
    } catch (_) {}
    
    const capturedDate = new Date(img.timestamp).toLocaleDateString();
    
    return `
                <div class="image-item" data-index="${index}" onclick="toggleImageSelection(this)">
                    <img src="${img.url}" alt="Captured image ${index + 1}" onerror="this.style.display='none'">
                    <div class="image-info">
                        <div class="image-title">${filename}</div>
                        <div class="image-meta">
                            <span>${hostname}</span>
                            <span>${capturedDate}</span>
                        </div>
                    </div>
                </div>
    `;
  }).join('');
  
  return `
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ImageCapture Collection</title>
        <style>
${generateCollectionStyles()}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🖼️ ImageCapture Collection</h1>
            <p>${images.length} images captured</p>
        </div>
        
        <div class="stats">
            <div class="stat-item">
                <span class="stat-number">${images.length}</span>
                <span class="stat-label">Total Images</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">${totalSources}</span>
                <span class="stat-label">Sources</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">${statsStorage}</span>
                <span class="stat-label">Storage Used</span>
            </div>
        </div>
        
        <div class="controls">
            <button class="btn primary" onclick="downloadSelected()">📥 Download Selected</button>
            <button class="btn telegram" onclick="sendToTelegram()">📤 Send to Telegram</button>
            <button class="btn" onclick="toggleSelectionMode()">🎯 Toggle Selection Mode</button>
            <button class="btn" onclick="selectAll()">☑️ Select All</button>
            <button class="btn danger" onclick="clearCollection()">🗑️ Clear Collection</button>
        </div>
        
        <div class="image-grid" id="imageGrid">
${cards}
        </div>
        
        <div class="selection-mode" id="selectionMode">
            <div class="selection-controls">
                <button class="btn" onclick="selectAll()">☑️ Select All</button>
                <button class="btn" onclick="deselectAll()">☐ Deselect All</button>
                <button class="btn danger" onclick="toggleSelectionMode()">✕ Exit Selection</button>
            </div>
            <div class="selection-stats">
                Selected: <span id="selectedCount">0</span> / ${images.length}
            </div>
        </div>
        
        <script>
${generateCollectionScript(images.length)}
        </script>
    </body>
    </html>
  `;
}

function generateCollectionStyles() {
  return `            body {
                margin: 0;
                padding: 20px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                min-height: 100vh;
            }
            
            .header {
                text-align: center;
                margin-bottom: 30px;
            }
            
            .header h1 {
                margin: 0;
                font-size: 32px;
                font-weight: 600;
                margin-bottom: 10px;
            }
            
            .stats {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 30px;
                backdrop-filter: blur(10px);
                display: flex;
                justify-content: space-around;
                flex-wrap: wrap;
                gap: 20px;
            }
            
            .stat-item {
                text-align: center;
            }
            
            .stat-number {
                font-size: 24px;
                font-weight: bold;
                display: block;
            }
            
            .stat-label {
                font-size: 14px;
                opacity: 0.8;
            }
            
            .controls {
                display: flex;
                gap: 12px;
                margin-bottom: 30px;
                flex-wrap: wrap;
                justify-content: center;
            }
            
            .btn {
                background: rgba(255, 255, 255, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 8px;
                padding: 12px 20px;
                color: white;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s ease;
                text-decoration: none;
                display: inline-block;
            }
            
            .btn:hover {
                background: rgba(255, 255, 255, 0.3);
                transform: translateY(-2px);
            }
            
            .btn.primary {
                background: #4CAF50;
                border-color: #4CAF50;
            }
            
            .btn.primary:hover {
                background: #45a049;
            }
            
            .btn.danger {
                background: #f44336;
                border-color: #f44336;
            }
            
            .btn.danger:hover {
                background: #da190b;
            }
            
            .btn.telegram {
                background: #0088cc;
                border-color: #0088cc;
            }
            
            .btn.telegram:hover {
                background: #006699;
            }
            
            .image-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            
            .image-item {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                overflow: hidden;
                backdrop-filter: blur(10px);
                border: 3px solid transparent;
                background-clip: padding-box;
                position: relative;
                transition: all 0.3s ease;
                cursor: pointer;
            }
            
            .image-item::before {
                content: '';
                position: absolute;
                top: -3px;
                left: -3px;
                right: -3px;
                bottom: -3px;
                padding: 3px;
                background: linear-gradient(135deg, rgba(255, 255, 255, 0.3), rgba(255, 255, 255, 0.1));
                mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
                mask-composite: exclude;
                border-radius: 12px;
                opacity: 0.75;
                z-index: -1;
            }
            
            .image-item.selected::before {
                background: linear-gradient(135deg, #4CAF50, #45a049);
                opacity: 1;
            }
            
            .image-item:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
            }
            
            .image-item img {
                width: 100%;
                height: 200px;
                object-fit: cover;
                display: block;
            }
            
            .image-info {
                padding: 15px;
            }
            
            .image-title {
                font-size: 14px;
                font-weight: 600;
                margin-bottom: 8px;
                word-break: break-all;
            }
            
            .image-meta {
                font-size: 12px;
                opacity: 0.8;
                display: flex;
                justify-content: space-between;
            }
            
            .selection-mode {
                position: fixed;
                top: 20px;
                right: 20px;
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 15px;
                border-radius: 8px;
                backdrop-filter: blur(10px);
                z-index: 1000;
                display: none;
            }
            
            .selection-mode.active {
                display: block;
            }
            
            .selection-controls {
                display: flex;
                gap: 10px;
                margin-bottom: 10px;
            }
            
            .selection-stats {
                font-size: 12px;
                opacity: 0.8;
            }
            
            @media (max-width: 768px) {
                .image-grid {
                    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                    gap: 15px;
                }
                
                .controls {
                    flex-direction: column;
                    align-items: center;
                }
                
                .btn {
                    width: 100%;
                    max-width: 300px;
                }
            }`;
}

function generateCollectionScript(totalImages) {
  return `            const images = ${JSON.stringify(globalState.capturedImages)};
            const hasExtensionContext = typeof chrome !== 'undefined' && chrome.runtime && typeof chrome.runtime.sendMessage === 'function';
            let selectionMode = false;
            let selectedImages = new Set();
            
            function toggleSelectionMode() {
                selectionMode = !selectionMode;
                const modeDiv = document.getElementById('selectionMode');
                const toggleBtn = document.querySelector('button[onclick="toggleSelectionMode()"]');
                
                if (selectionMode) {
                    modeDiv.classList.add('active');
                    toggleBtn.textContent = '🎯 Exit Selection Mode';
                    toggleBtn.style.background = '#f44336';
                    document.body.style.cursor = 'crosshair';
                } else {
                    modeDiv.classList.remove('active');
                    toggleBtn.textContent = '🎯 Toggle Selection Mode';
                    toggleBtn.style.background = 'rgba(255, 255, 255, 0.2)';
                    document.body.style.cursor = 'default';
                    selectedImages.clear();
                    updateSelectionDisplay();
                    document.querySelectorAll('.image-item').forEach(item => item.classList.remove('selected'));
                }
            }
            
            function toggleImageSelection(element) {
                if (!selectionMode) return;
                
                const index = element.dataset.index;
                if (selectedImages.has(index)) {
                    selectedImages.delete(index);
                    element.classList.remove('selected');
                } else {
                    selectedImages.add(index);
                    element.classList.add('selected');
                }
                updateSelectionDisplay();
            }
            
            function selectAll() {
                if (!selectionMode) {
                    toggleSelectionMode();
                }
                selectedImages.clear();
                document.querySelectorAll('.image-item').forEach((item, index) => {
                    selectedImages.add(index.toString());
                    item.classList.add('selected');
                });
                updateSelectionDisplay();
            }
            
            function deselectAll() {
                selectedImages.clear();
                document.querySelectorAll('.image-item').forEach(item => {
                    item.classList.remove('selected');
                });
                updateSelectionDisplay();
            }
            
            function updateSelectionDisplay() {
                const counter = document.getElementById('selectedCount');
                if (counter) {
                    counter.textContent = selectedImages.size;
                }
            }
            
            function downloadSelected() {
                const imagesToDownload = selectionMode && selectedImages.size > 0 
                    ? Array.from(selectedImages).map(index => images[index])
                    : images;
                
                const urls = imagesToDownload.map(img => img.url).join('\\n');
                const blob = new Blob([urls], { type: 'text/plain' });
                const url = URL.createObjectURL(blob);
                
                const a = document.createElement('a');
                a.href = url;
                a.download = 'captured_images.txt';
                a.click();
                
                setTimeout(() => URL.revokeObjectURL(url), 0);
                
                alert(\`\${imagesToDownload.length} image URLs downloaded!\`);
            }
            
            function sendToTelegram() {
                const imagesToSend = selectionMode && selectedImages.size > 0 
                    ? Array.from(selectedImages).map(index => images[index])
                    : images;
                
                const imageUrls = imagesToSend.map(img => img.url);
                
                fetch('http://localhost:5000/send_multiple_telegram', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({image_urls: imageUrls})
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert(\`✅ Successfully sent \${data.successful}/\${data.total_images} images to Telegram!\`);
                    } else {
                        alert(\`❌ Failed to send images: \${data.error}\`);
                    }
                })
                .catch(error => {
                    alert(\`❌ Error sending to Telegram: \${error.message}\`);
                });
            }
            
            function clearCollection() {
                if (confirm('Are you sure you want to clear all captured images?')) {
                    if (!hasExtensionContext) {
                        alert('Extension context unavailable. Please reopen this page from the extension.');
                        return;
                    }
                    chrome.runtime.sendMessage({ action: 'clearCapturedImages' }, (response) => {
                        if (response && response.success) {
                            alert('Collection cleared!');
                            location.reload();
                        } else {
                            alert(response && response.error ? response.error : 'Failed to clear collection');
                        }
                    });
                }
            }
            
            document.addEventListener('keydown', (e) => {
                if (e.target.tagName === 'INPUT') return;
                
                switch (e.key.toLowerCase()) {
                    case 's':
                        if (!e.ctrlKey && !e.metaKey) {
                            e.preventDefault();
                            toggleSelectionMode();
                        }
                        break;
                    case 'escape':
                        if (selectionMode) {
                            toggleSelectionMode();
                        }
                        break;
                }
            });
        `;
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!tab || !tab.url || !tab.url.startsWith('http')) return;
  
  switch (info.menuItemId) {
    case 'toggle-sidebar':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleSidebar' }).catch(() => {});
      break;
      
    case 'toggle-overlay-menu':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleOverlayMenu' }).catch(() => {});
      break;
      
    case 'toggle-selection-mode':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleSelectionMode' }).catch(() => {});
      break;
      
    case 'select-all-images':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleSelectAll' }).catch(() => {});
      break;
      
    case 'capture-selected-images':
      chrome.tabs.sendMessage(tab.id, { action: 'captureSelectedImages' }).catch(() => {});
      break;
      
    case 'download-selected-images':
      chrome.tabs.sendMessage(tab.id, { action: 'downloadSelectedImages' }).catch(() => {});
      break;
      
    case 'clear-collection':
      chrome.tabs.sendMessage(tab.id, { action: 'clearCapturedImages' }).catch(() => {});
      break;
  }
}); 
```

```javascript
// Background script for ImageCapture extension
let globalState = {
  overlayVisible: false,
  floatingMenuPosition: {
    x: 20,
    y: 20,
    width: 200,
    height: 'auto'
  },
  settings: {
    hoverSelectDelay: 500,
    hoverDeselectDelay: 300,
    autoCaptureHover: false, // Disabled hover selection
    showNotifications: true,
    showSelectionIndicator: true,
    telegramEnabled: true,
    showFloatingMenu: true,
    minImageWidth: 100,
    preferredFileTypes: ['jpg', 'jpeg', 'png'],
    overlayHoverDelay: 1000,
    overlayButtons: ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'],
    overlayDraggable: true,
    quickToolbarMode: false,
    useOverlayIcons: false // New setting for toggleable selection indicators
  },
  capturedImages: [],
  selectedImages: []
};

// Initialize state from storage
chrome.storage.local.get(['globalState', 'capturedImages'], (result) => {
  if (result.globalState) {
    globalState = { ...globalState, ...result.globalState };
  }
  if (result.capturedImages) {
    globalState.capturedImages = result.capturedImages;
  }
  saveGlobalState();
});

// Save global state to storage
function saveGlobalState() {
  chrome.storage.local.set({
    globalState: globalState,
    capturedImages: globalState.capturedImages
  });
}

// Handle messages from content scripts and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'getSettings':
      sendResponse({ settings: globalState.settings });
      break;
      
    case 'setSettings':
      globalState.settings = { ...globalState.settings, ...request.settings };
      saveGlobalState();
      // Broadcast settings update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateSettings', settings: globalState.settings }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'getGlobalState':
      sendResponse({ globalState: globalState });
      break;
      
    case 'setOverlayVisible':
      globalState.overlayVisible = request.visible;
      saveGlobalState();
      // Broadcast overlay visibility update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateOverlayVisibility', visible: request.visible }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'setFloatingMenuPosition':
      globalState.floatingMenuPosition = { ...globalState.floatingMenuPosition, ...request.position };
      saveGlobalState();
      // Broadcast position update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateFloatingMenuPosition', position: globalState.floatingMenuPosition }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'updateSettings':
      globalState.settings = { ...globalState.settings, ...request.settings };
      saveGlobalState();
      // Broadcast settings update to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'updateSettings', settings: globalState.settings }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'captureImage':
      const imageData = {
        url: request.url,
        timestamp: Date.now(),
        domain: new URL(request.url).hostname,
        title: request.title || 'Captured Image'
      };
      
      if (!globalState.capturedImages.find(img => img.url === request.url)) {
        globalState.capturedImages.push(imageData);
        saveGlobalState();
        
        // Broadcast new image to all tabs
        chrome.tabs.query({}, (tabs) => {
          tabs.forEach(tab => {
            chrome.tabs.sendMessage(tab.id, { action: 'newImageCaptured', image: imageData }).catch(() => {});
          });
        });
      }
      sendResponse({ success: true });
      break;
      
    case 'getCapturedImages':
      sendResponse({ images: globalState.capturedImages });
      break;
      
    case 'clearCapturedImages':
      globalState.capturedImages = [];
      saveGlobalState();
      // Broadcast clear to all tabs
      chrome.tabs.query({}, (tabs) => {
        tabs.forEach(tab => {
          chrome.tabs.sendMessage(tab.id, { action: 'imagesCleared' }).catch(() => {});
        });
      });
      sendResponse({ success: true });
      break;
      
    case 'downloadImages':
      console.log('Download request received:', request);
      const imagesToDownload = request.images || globalState.capturedImages;
      if (imagesToDownload.length === 0) {
        console.log('No images to download');
        sendResponse({ success: false, error: 'No images to download' });
        return;
      }
      
      console.log('Images to download:', imagesToDownload);
      
      // Download each image file individually
      let downloadCount = 0;
      const totalImages = imagesToDownload.length;
      
      imagesToDownload.forEach((img, index) => {
        const imageUrl = img.url || img;
        const filename = `image_${Date.now()}_${index + 1}.jpg`;
        
        console.log(`Downloading image ${index + 1}/${totalImages}:`, imageUrl);
        
        // Download the actual image file
        chrome.downloads.download({
          url: imageUrl,
          filename: filename,
          saveAs: false // Don't prompt for each file, use browser's default download folder
        }, (downloadId) => {
          downloadCount++;
          console.log(`Download ${index + 1} completed, downloadId:`, downloadId);
          
          // Check if all downloads are complete
          if (downloadCount === totalImages) {
            console.log('All downloads completed');
            sendResponse({ success: true, downloaded: downloadCount });
          }
        });
      });
      
      return true; // Keep message channel open for async response
      break;
      
    case 'sendToTelegram':
      const imagesToSend = request.images || globalState.capturedImages;
      if (imagesToSend.length === 0) {
        sendResponse({ success: false, error: 'No images to send' });
        return;
      }
      
      const imageUrls = imagesToSend.map(img => img.url);
      
      fetch('http://localhost:5000/send_multiple_telegram', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({image_urls: imageUrls})
      })
      .then(response => response.json())
      .then(data => {
        sendResponse({ success: data.success, data: data });
      })
      .catch(error => {
        sendResponse({ success: false, error: error.message });
      });
      
      return true; // Keep message channel open for async response
      
    case 'viewCollection':
      try {
        const pageUrl = chrome.runtime.getURL('collection.html');
        chrome.tabs.create({ url: pageUrl }, (tab) => {
          if (chrome.runtime.lastError) {
            sendResponse({ success: false, error: chrome.runtime.lastError.message });
            return;
          }
          sendResponse({ success: true, tabId: tab && tab.id });
        });
        return true; // Keep channel open for async response
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;
      
    default:
      sendResponse({ success: false, error: 'Unknown action' });
  }
});

// Handle tab updates to sync state
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'complete' && tab.url && tab.url.startsWith('http')) {
    // Send current state to new tab
    setTimeout(() => {
      chrome.tabs.sendMessage(tabId, { 
        action: 'initializeState', 
        globalState: globalState 
      }).catch(() => {});
    }, 1000);
  }
});

// Handle extension installation/update
chrome.runtime.onInstalled.addListener(() => {
  saveGlobalState();
  
  // Create context menu items
  chrome.contextMenus.create({
    id: 'imagecapture-main',
    title: '🖼️ ImageCapture',
    contexts: ['all']
  });
  
  chrome.contextMenus.create({
    id: 'toggle-sidebar',
    title: '📱 Toggle Sidebar',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'toggle-overlay-menu',
    title: '👁️ Toggle Overlay Menu',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'toggle-selection-mode',
    title: '🎯 Toggle Selection Mode',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'select-all-images',
    title: '☑️ Select All Images',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'capture-selected-images',
    title: '📸 Capture Selected Images',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'download-selected-images',
    title: '📥 Download Selected Images',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
  
  chrome.contextMenus.create({
    id: 'clear-collection',
    title: '🗑️ Clear Collection',
    contexts: ['all'],
    parentId: 'imagecapture-main'
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!tab || !tab.url || !tab.url.startsWith('http')) return;
  
  switch (info.menuItemId) {
    case 'toggle-sidebar':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleSidebar' }).catch(() => {});
      break;
      
    case 'toggle-overlay-menu':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleOverlayMenu' }).catch(() => {});
      break;
      
    case 'toggle-selection-mode':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleSelectionMode' }).catch(() => {});
      break;
      
    case 'select-all-images':
      chrome.tabs.sendMessage(tab.id, { action: 'toggleSelectAll' }).catch(() => {});
      break;
      
    case 'capture-selected-images':
      chrome.tabs.sendMessage(tab.id, { action: 'captureSelectedImages' }).catch(() => {});
      break;
      
    case 'download-selected-images':
      chrome.tabs.sendMessage(tab.id, { action: 'downloadSelectedImages' }).catch(() => {});
      break;
      
    case 'clear-collection':
      chrome.tabs.sendMessage(tab.id, { action: 'clearCapturedImages' }).catch(() => {});
      break;
  }
}); 
```

```javascript
// Content script for ImageCapture extension
let selectionMode = false;
let selectedImages = new Set();
let sidebarVisible = false;
let sidebarElement = null;
let floatingMenu = null;
let isolationMode = false;
let overlayMenuVisible = false;
let overlayHoverTimer = null;
let floatingMenuPosition = { x: 20, y: 20, width: 280, height: 'auto' };
let settings = {
  hoverSelectDelay: 500,
  hoverDeselectDelay: 300,
  autoCaptureHover: false, // Disabled hover selection
  showNotifications: true,
  showSelectionIndicator: true,
  telegramEnabled: true,
  showFloatingMenu: true,
  minImageWidth: 100,
  preferredFileTypes: ['jpg', 'jpeg', 'png'],
  overlayHoverDelay: 1000,
      overlayButtons: ['overlay', 'selection', 'selectAll', 'sidebar', 'isolation', 'capture', 'viewCollection', 'download', 'quickToolbar'],
  overlayDraggable: true,
  quickToolbarMode: false,
  useOverlayIcons: false // New setting for toggleable selection indicators
};

// Load global state from background script
chrome.runtime.sendMessage({action: 'getGlobalState'}, (response) => {
  if (response && response.globalState) {
    const globalState = response.globalState;
    settings = { ...settings, ...globalState.settings };
    overlayMenuVisible = globalState.overlayVisible;
    selectedImages = new Set(globalState.selectedImages || []);
    floatingMenuPosition = globalState.floatingMenuPosition || { x: 20, y: 20, width: 280, height: 'auto' };
  }
});

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  addImageIndicators();
  createFloatingMenu();
  
  // Monitor for dynamically added images
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.type === 'childList') {
        mutation.addedNodes.forEach((node) => {
          if (node.nodeType === Node.ELEMENT_NODE) {
            const images = node.querySelectorAll('img');
            if (images.length > 0) {
              addImageIndicators();
            }
          }
        });
      }
    });
  });
  
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
});

// Also initialize if DOM is already loaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeExtension);
} else {
  initializeExtension();
}

function initializeExtension() {
  addImageIndicators();
  if (settings.showFloatingMenu) {
    createFloatingMenu();
  }
  
  // Add window resize handler to keep menu within bounds
  window.addEventListener('resize', handleWindowResize);
}

// Handle window resize to keep floating menu within viewport
function handleWindowResize() {
  if (!floatingMenu) return;
  
  const rect = floatingMenu.getBoundingClientRect();
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  
  let needsUpdate = false;
  let newX = floatingMenuPosition.x;
  let newY = floatingMenuPosition.y;
  
  // Check if menu is outside viewport - use absolute positioning
  if (rect.right > viewportWidth) {
    newX = Math.max(20, viewportWidth - rect.width - 20);
    needsUpdate = true;
  }
  
  if (rect.bottom > viewportHeight) {
    newY = Math.max(20, viewportHeight - rect.height - 20);
    needsUpdate = true;
  }
  
  if (rect.left < 0) {
    newX = 20; // Keep menu at minimum left position
    needsUpdate = true;
  }
  
  if (rect.top < 0) {
    newY = Math.min(viewportHeight - rect.height - 20, 20);
    needsUpdate = true;
  }
  
  if (needsUpdate) {
    floatingMenuPosition.x = newX;
    floatingMenuPosition.y = newY;
    
    // Use absolute positioning instead of right-based
    floatingMenu.style.left = `${newX}px`;
    floatingMenu.style.top = `${newY}px`;
    floatingMenu.style.right = 'auto';
    
    // Save updated position
    chrome.runtime.sendMessage({
      action: 'setFloatingMenuPosition',
      position: floatingMenuPosition
    });
  }
}

// Add visual indicators to images with enhanced styling
function addImageIndicators() {
  const images = document.querySelectorAll('img');
  
  images.forEach(img => {
    if (img.dataset.imagecaptureInitialized) return;
    
    img.dataset.imagecaptureInitialized = 'true';
    img.style.cursor = 'pointer';
    
    // Only show borders/overlays when selection mode is active
    if (selectionMode) {
      // Enhanced border styling with increased thickness and reduced opacity
      if (selectedImages.has(img.src)) {
        if (settings.useOverlayIcons) {
          addSelectionOverlay(img);
        } else {
          img.style.border = '10px solid rgba(76, 175, 80, 0.75)';
          img.style.borderRadius = '8px';
          img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
          img.style.boxShadow = '0 0 20px rgba(76, 175, 80, 0.5), inset 0 0 20px rgba(76, 175, 80, 0.2)';
        }
      } else {
        if (settings.useOverlayIcons) {
          addCheckboxOverlay(img);
        } else {
          img.style.border = '10px solid rgba(255, 107, 107, 0.5625)';
          img.style.borderRadius = '8px';
          img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
          img.style.boxShadow = '0 0 20px rgba(255, 107, 107, 0.375), inset 0 0 20px rgba(255, 107, 107, 0.15)';
        }
      }
    } else {
      // Clear any existing borders/overlays when selection mode is off
      if (settings.useOverlayIcons) {
        removeSelectionOverlay(img);
      } else {
        img.style.border = 'none';
        img.style.boxShadow = 'none';
      }
    }
    
    // Click event
    img.addEventListener('click', (e) => {
      if (selectionMode) {
        e.preventDefault();
        e.stopPropagation();
        toggleImageSelection(img);
      }
    });
    
    // Mouse 3 (middle click) event
    img.addEventListener('auxclick', (e) => {
      if (e.button === 1) {
        e.preventDefault();
        e.stopPropagation();
        handleImageAuxClick(e);
      }
    });
  });
}

// Add selection overlay icon
function addSelectionOverlay(img) {
  // Remove any existing overlay
  removeSelectionOverlay(img);
  
  // Create overlay container
  const overlay = document.createElement('div');
  overlay.className = 'imagecapture-selection-overlay';
  overlay.style.cssText = `
    position: absolute;
    top: 10px;
    right: 10px;
    width: 30px;
    height: 30px;
    background: #4CAF50;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 18px;
    font-weight: bold;
    z-index: 1000;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  `;
  overlay.innerHTML = '✓';
  
  // Ensure img has relative positioning
  if (img.style.position !== 'relative' && img.style.position !== 'absolute') {
    img.style.position = 'relative';
  }
  
  img.appendChild(overlay);
}

// Add checkbox overlay for unselected images
function addCheckboxOverlay(img) {
  // Remove any existing overlay
  removeSelectionOverlay(img);
  
  // Create checkbox overlay container
  const overlay = document.createElement('div');
  overlay.className = 'imagecapture-checkbox-overlay';
  overlay.style.cssText = `
    position: absolute;
    top: 10px;
    right: 10px;
    width: 30px;
    height: 30px;
    background: rgba(255, 255, 255, 0.9);
    border: 2px solid #ccc;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #666;
    font-size: 16px;
    font-weight: bold;
    z-index: 1000;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    cursor: pointer;
  `;
  overlay.innerHTML = '';
  
  // Add click handler to the checkbox
  overlay.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    toggleImageSelection(img);
  });
  
  // Ensure img has relative positioning
  if (img.style.position !== 'relative' && img.style.position !== 'absolute') {
    img.style.position = 'relative';
  }
  
  img.appendChild(overlay);
}

// Remove selection overlay icon
function removeSelectionOverlay(img) {
  const overlay = img.querySelector('.imagecapture-selection-overlay, .imagecapture-checkbox-overlay');
  if (overlay) {
    overlay.remove();
  }
}

// Handle image aux click (Mouse 3)
function handleImageAuxClick(e) {
  const img = e.target;
  const imageUrl = img.src;
  
  if (selectedImages.has(imageUrl)) {
    selectedImages.delete(imageUrl);
    animateImageSelection(img, false);
  } else {
    selectedImages.add(imageUrl);
    animateImageSelection(img, true);
  }
  
  updateSelectionCounter();
}

// Animate image selection with enhanced visual feedback
function animateImageSelection(img, isSelected) {
  if (isSelected) {
    if (settings.useOverlayIcons) {
      addSelectionOverlay(img);
    } else {
      img.style.border = '10px solid rgba(76, 175, 80, 0.75)';
      img.style.boxShadow = `
        0 0 20px rgba(76, 175, 80, 0.5), 
        inset 0 0 20px rgba(76, 175, 80, 0.2),
        0 0 40px rgba(76, 175, 80, 0.3),
        0 0 60px rgba(76, 175, 80, 0.1)
      `;
    }
    img.style.transform = 'scale(1.02)';
    img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
    
    setTimeout(() => {
      img.style.transform = 'scale(1)';
    }, 200);
  } else {
    if (settings.useOverlayIcons) {
      addCheckboxOverlay(img);
    } else {
      img.style.border = '10px solid rgba(255, 107, 107, 0.5625)';
      img.style.boxShadow = `
        0 0 20px rgba(255, 107, 107, 0.375), 
        inset 0 0 20px rgba(255, 107, 107, 0.15),
        0 0 40px rgba(255, 107, 107, 0.25),
        0 0 60px rgba(255, 107, 107, 0.1)
      `;
    }
    img.style.transform = 'scale(1)';
    img.style.transition = 'border 0.3s ease, transform 0.2s ease, box-shadow 0.3s ease';
  }
}

// Remove border after download
function removeImageBorder(img) {
  if (settings.useOverlayIcons) {
    removeSelectionOverlay(img);
  } else {
    img.style.border = 'none';
    img.style.boxShadow = 'none';
  }
  img.style.transform = 'scale(1)';
}

// Toggle image selection
function toggleImageSelection(img) {
  const imageUrl = img.src;
  
  if (selectedImages.has(imageUrl)) {
    selectedImages.delete(imageUrl);
    animateImageSelection(img, false);
  } else {
    selectedImages.add(imageUrl);
    animateImageSelection(img, true);
  }
  
  updateSelectionCounter();
}

// Select all images
function selectAllImages() {
  const images = document.querySelectorAll('img');
  images.forEach(img => {
    if (shouldCaptureImage(img)) {
      selectedImages.add(img.src);
      animateImageSelection(img, true);
    }
  });
  updateSelectionCounter();
  showNotification(`Selected ${selectedImages.size} images`);
}

// Deselect all images
function deselectAllImages() {
  const images = document.querySelectorAll('img');
  images.forEach(img => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      animateImageSelection(img, false);
    }
  });
  updateSelectionCounter();
  showNotification('Deselected all images');
}

// Toggle select all/deselect all
function toggleSelectAll() {
  const images = document.querySelectorAll('img');
  const capturableImages = Array.from(images).filter(img => shouldCaptureImage(img));
  const selectedCapturableImages = capturableImages.filter(img => selectedImages.has(img.src));
  
  if (selectedCapturableImages.length === capturableImages.length) {
    deselectAllImages();
  } else {
    selectAllImages();
  }
}

// Capture selected images
function captureSelectedImages() {
  const imagesToCapture = Array.from(selectedImages);
  if (imagesToCapture.length === 0) {
    showNotification('No images selected to capture');
    return;
  }
  
  imagesToCapture.forEach(imageUrl => {
    chrome.runtime.sendMessage({
      action: 'captureImage',
      url: imageUrl,
      title: document.title
    });
    
    // Remove border after capture
    const img = document.querySelector(`img[src="${imageUrl}"]`);
    if (img) {
      removeImageBorder(img);
    }
  });
  
  selectedImages.clear();
  updateSelectionCounter();
  showNotification(`Captured ${imagesToCapture.length} images`);
}

// Update selection counter
function updateSelectionCounter() {
  if (floatingMenu && floatingMenu.counter) {
    floatingMenu.counter.textContent = `Selected: ${selectedImages.size}`;
  }
  if (sidebarElement && sidebarElement.counter) {
    sidebarElement.counter.textContent = `Selected: ${selectedImages.size}`;
  }
}

// Toggle selection mode
function toggleSelectionMode() {
  selectionMode = !selectionMode;
  
  if (selectionMode) {
    document.body.style.cursor = 'crosshair';
    showNotification('Selection mode ON - Click images to select');
  } else {
    document.body.style.cursor = 'default';
    showNotification('Selection mode OFF');
  }
  
  // Refresh image indicators to show/hide borders based on selection mode
  addImageIndicators();
  
  // Update floating menu button
  if (floatingMenu && floatingMenu.toggleBtn) {
    floatingMenu.toggleBtn.textContent = selectionMode ? '🎯 Selection: ON' : '🎯 Selection: OFF';
    floatingMenu.toggleBtn.style.background = selectionMode ? '#4CAF50' : '#ff9800';
    floatingMenu.toggleBtn.style.borderColor = selectionMode ? '#4CAF50' : 'transparent';
  }
  
  // Update sidebar button if exists
  if (sidebarElement && sidebarElement.toggleBtn) {
    sidebarElement.toggleBtn.textContent = selectionMode ? '🎯 Selection: ON' : '🎯 Selection: OFF';
    sidebarElement.toggleBtn.style.background = selectionMode ? '#4CAF50' : '#ff9800';
  }
}

// Toggle overlay menu visibility with hover delay
function toggleOverlayMenu() {
  if (settings.overlayHoverDelay > 0) {
    if (overlayHoverTimer) {
      clearTimeout(overlayHoverTimer);
      overlayHoverTimer = null;
    }
    
    overlayHoverTimer = setTimeout(() => {
      overlayMenuVisible = !overlayMenuVisible;
      
      if (floatingMenu) {
        floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
      }
      
      // Save state to background
      chrome.runtime.sendMessage({
        action: 'setOverlayVisible',
        visible: overlayMenuVisible
      });
      
      showNotification(overlayMenuVisible ? 'Overlay menu shown' : 'Overlay menu hidden');
    }, settings.overlayHoverDelay);
  } else {
    overlayMenuVisible = !overlayMenuVisible;
    
    if (floatingMenu) {
      floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
    }
    
    chrome.runtime.sendMessage({
      action: 'setOverlayVisible',
      visible: overlayMenuVisible
    });
    
    showNotification(overlayMenuVisible ? 'Overlay menu shown' : 'Overlay menu hidden');
  }
}

// Create draggable floating menu with customizable buttons
function createFloatingMenu() {
  if (floatingMenu) return;
  
  floatingMenu = document.createElement('div');
  floatingMenu.id = 'imagecapture-floating-menu';
  floatingMenu.style.cssText = `
    position: fixed;
    left: ${floatingMenuPosition.x}px;
    top: ${floatingMenuPosition.y}px;
    background: rgba(0, 0, 0, 0.8);
    backdrop-filter: blur(10px);
    border-radius: 12px;
    padding: 16px;
    z-index: 10000;
    display: flex;
    flex-direction: column;
    gap: 8px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    transition: all 0.3s ease;
    min-width: 200px;
    max-width: 280px;
    width: 280px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    resize: both;
    overflow: auto;
  `;
  
  // Add drag handle
  const dragHandle = document.createElement('div');
  dragHandle.innerHTML = '⋮⋮';
  dragHandle.style.cssText = `
    position: absolute;
    top: 8px;
    left: 8px;
    color: rgba(255, 255, 255, 0.6);
    cursor: move;
    font-size: 14px;
    font-weight: bold;
    user-select: none;
  `;
  
  // Add close button
  const closeBtn = document.createElement('button');
  closeBtn.innerHTML = '✕';
  closeBtn.style.cssText = `
    position: absolute;
    top: 8px;
    right: 8px;
    background: #f44336;
    color: white;
    border: none;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    cursor: pointer;
    font-size: 12px;
    font-weight: bold;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10001;
    transition: all 0.2s ease;
  `;
  closeBtn.onmouseenter = () => {
    closeBtn.style.background = '#d32f2f';
    closeBtn.style.transform = 'scale(1.1)';
  };
  closeBtn.onmouseleave = () => {
    closeBtn.style.background = '#f44336';
    closeBtn.style.transform = 'scale(1)';
  };
  closeBtn.onclick = () => {
    floatingMenu.remove();
    floatingMenu = null;
  };
  
  // Create button container
  const buttonContainer = document.createElement('div');
  buttonContainer.style.cssText = `
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 20px;
  `;
  
  // Create buttons based on settings
  const buttonConfigs = {
    overlay: {
      text: '👁️ Overlay',
      color: '#607D8B',
      action: () => toggleOverlayMenu()
    },
    selection: {
      text: '🎯 Selection: OFF',
      color: '#ff9800',
      action: () => toggleSelectionMode()
    },
    selectAll: {
      text: '☑️ Select All',
      color: '#2196F3',
      action: () => toggleSelectAll()
    },
    sidebar: {
      text: '📱 Sidebar',
      color: '#2196F3',
      action: () => toggleSidebar()
    },
    isolation: {
      text: '🖼️ Image Mode',
      color: '#9C27B0',
      action: () => toggleIsolationMode()
    },
    capture: {
      text: '📸 Capture',
      color: '#4CAF50',
      action: () => captureSelectedImages()
    },
    viewCollection: {
      text: '📋 View Collection',
      color: '#3F51B5',
      action: () => openCollectionView()
    },
    download: {
      text: '📥 Download',
      color: '#FF9800',
      action: () => downloadSelectedImages()
    },
    quickToolbar: {
      text: '⚡ Quick Toolbar',
      color: '#E91E63',
      action: () => toggleQuickToolbar()
    }
  };
  
  const buttons = {};
  const buttonOrder = [...settings.overlayButtons];
  
  function createButtonElement(buttonType) {
    if (!buttonConfigs[buttonType]) return null;
    
    const config = buttonConfigs[buttonType];
    const btn = document.createElement('div');
    btn.className = 'overlay-button';
    btn.dataset.buttonType = buttonType;
    btn.style.cssText = `
      background: ${config.color};
      color: white;
      border: none;
      padding: 10px 12px;
      border-radius: 6px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 500;
      transition: all 0.2s ease;
      position: relative;
      user-select: none;
      display: flex;
      align-items: center;
      gap: 8px;
    `;
    
    // Add drag handle for reordering
    const handle = document.createElement('div');
    handle.innerHTML = '⋮';
    handle.className = 'button-handle';
    handle.style.cssText = `
      color: rgba(255, 255, 255, 0.6);
      cursor: move;
      font-size: 10px;
      font-weight: bold;
      user-select: none;
      padding: 2px;
    `;
    
    const textSpan = document.createElement('span');
    textSpan.textContent = config.text;
    
    btn.appendChild(handle);
    btn.appendChild(textSpan);
    
    // Add drag functionality for reordering
    makeButtonDraggable(btn, handle, buttonContainer);
    
    btn.onclick = (e) => {
      if (e.target !== handle) {
        config.action();
      }
    };
    
    btn.onmouseenter = () => {
      if (!btn.classList.contains('dragging')) {
        btn.style.transform = 'translateY(-1px)';
        btn.style.boxShadow = '0 4px 8px rgba(0, 0, 0, 0.2)';
      }
    };
    
    btn.onmouseleave = () => {
      if (!btn.classList.contains('dragging')) {
        btn.style.transform = 'translateY(0)';
        btn.style.boxShadow = 'none';
      }
    };
    
    return btn;
  }
  
  // Create and add buttons in order
  buttonOrder.forEach(buttonType => {
    const btn = createButtonElement(buttonType);
    if (btn) {
      buttonContainer.appendChild(btn);
      buttons[buttonType] = btn;
    }
  });
  
  const counter = document.createElement('div');
  counter.textContent = 'Selected: 0';
  counter.style.cssText = `
    color: white;
    font-size: 11px;
    text-align: center;
    margin-top: 8px;
    padding: 4px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 4px;
  `;
  
  floatingMenu.appendChild(dragHandle);
  floatingMenu.appendChild(closeBtn);
  floatingMenu.appendChild(buttonContainer);
  floatingMenu.appendChild(counter);
  
  // Store references
  floatingMenu.toggleBtn = buttons.selection;
  floatingMenu.selectAllBtn = buttons.selectAll;
  floatingMenu.sidebarBtn = buttons.sidebar;
  floatingMenu.isolationBtn = buttons.isolation;
  floatingMenu.captureBtn = buttons.capture;
  floatingMenu.downloadBtn = buttons.download;
  floatingMenu.counter = counter;
  floatingMenu.buttonContainer = buttonContainer;
  
  // Add drag functionality for moving the menu
  if (settings.overlayDraggable) {
    makeDraggable(floatingMenu, dragHandle);
  }
  
  // Add resize observer to track manual resizing
  const resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      if (entry.target === floatingMenu) {
        const rect = entry.target.getBoundingClientRect();
        
        // Only update width and height, preserve current x and y positions
        // This prevents the menu from "jumping" when resizing from the right edge
        // Apply max-width constraint to prevent full-screen stretching
        const maxWidth = settings.quickToolbarMode ? 400 : 280;
        const constrainedWidth = Math.min(rect.width, maxWidth);
        
        const newPosition = {
          x: floatingMenuPosition.x, // Preserve current x position
          y: floatingMenuPosition.y, // Preserve current y position
          width: constrainedWidth,
          height: rect.height
        };
        
        // Only update if the size actually changed to prevent unnecessary updates
        if (newPosition.width !== floatingMenuPosition.width || 
            newPosition.height !== floatingMenuPosition.height) {
          
          floatingMenuPosition = newPosition;
          
          // Temporarily disable transitions during resize to prevent stretching effect
          const originalTransition = floatingMenu.style.transition;
          floatingMenu.style.transition = 'none';
          
          // Apply the constrained width to the element
          floatingMenu.style.width = `${constrainedWidth}px`;
          
          // Don't update min-width dynamically - this causes stretching issues
          // The min-width should remain fixed at the initial value
          
          // Re-enable transitions after a brief delay
          setTimeout(() => {
            floatingMenu.style.transition = originalTransition;
          }, 50);
          
          chrome.runtime.sendMessage({
            action: 'setFloatingMenuPosition',
            position: newPosition
          });
        }
      }
    }
  });
  resizeObserver.observe(floatingMenu);
  
  // Set initial visibility - ensure it's visible if overlayMenuVisible is true
  floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
  
  // Apply toolbar mode if enabled
  if (settings.quickToolbarMode) {
    toggleQuickToolbar();
  }
  
  document.body.appendChild(floatingMenu);
}

// Make element draggable
function makeDraggable(element, handle) {
  let isDragging = false;
  let currentX;
  let currentY;
  let initialX;
  let initialY;
  let xOffset = 0;
  let yOffset = 0;
  
  handle.addEventListener('mousedown', dragStart);
  document.addEventListener('mousemove', drag);
  document.addEventListener('mouseup', dragEnd);
  
  function dragStart(e) {
    // Only allow dragging if the target is the handle or its children
    if (e.target === handle || handle.contains(e.target)) {
      initialX = e.clientX - xOffset;
      initialY = e.clientY - yOffset;
      isDragging = true;
      e.preventDefault(); // Prevent text selection
    }
  }
  
  function drag(e) {
    if (isDragging) {
      e.preventDefault();
      
      currentX = e.clientX - initialX;
      currentY = e.clientY - initialY;
      
      xOffset = currentX;
      yOffset = currentY;
      
      setTranslate(currentX, currentY, element);
    }
  }
  
  function setTranslate(xPos, yPos, el) {
    el.style.transform = `translate3d(${xPos}px, ${yPos}px, 0)`;
  }
  
  function dragEnd(e) {
    initialX = currentX;
    initialY = currentY;
    isDragging = false;
    
    // Save position to background script - use absolute positioning
    const rect = element.getBoundingClientRect();
    const newPosition = {
      x: rect.left,
      y: rect.top,
      width: rect.width,
      height: rect.height
    };
    
    floatingMenuPosition = newPosition;
    
    // Reset transform and apply absolute positioning
    element.style.transform = 'none';
    element.style.left = `${newPosition.x}px`;
    element.style.top = `${newPosition.y}px`;
    
    chrome.runtime.sendMessage({
      action: 'setFloatingMenuPosition',
      position: newPosition
    });
  }
}

// Make button draggable for reordering
function makeButtonDraggable(button, handle, container) {
  let isDragging = false;
  let dragStartY = 0;
  let originalY = 0;
  let placeholder = null;
  
  handle.addEventListener('mousedown', (e) => {
    e.preventDefault();
    e.stopPropagation();
    
    isDragging = true;
    dragStartY = e.clientY;
    originalY = button.offsetTop;
    
    // Create placeholder
    placeholder = document.createElement('div');
    placeholder.style.cssText = `
      height: ${button.offsetHeight}px;
      background: rgba(255, 255, 255, 0.1);
      border: 2px dashed rgba(255, 255, 255, 0.3);
      border-radius: 6px;
      margin: 4px 0;
    `;
    
    // Add dragging class
    button.classList.add('dragging');
    button.style.opacity = '0.8';
    button.style.transform = 'rotate(2deg) scale(1.02)';
    button.style.zIndex = '1000';
    
    // Insert placeholder
    container.insertBefore(placeholder, button);
    
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  });
  
  function handleMouseMove(e) {
    if (!isDragging) return;
    
    const deltaY = e.clientY - dragStartY;
    const newY = originalY + deltaY;
    
    // Find the new position
    const buttons = Array.from(container.children).filter(child => 
      child.classList.contains('overlay-button') && child !== button
    );
    
    let insertIndex = 0;
    for (let i = 0; i < buttons.length; i++) {
      const btn = buttons[i];
      const btnRect = btn.getBoundingClientRect();
      const btnCenter = btnRect.top + btnRect.height / 2;
      
      if (e.clientY < btnCenter) {
        insertIndex = i;
        break;
      }
      insertIndex = i + 1;
    }
    
    // Move placeholder
    const allButtons = Array.from(container.children).filter(child => 
      child.classList.contains('overlay-button') && child !== button
    );
    
    if (placeholder && allButtons.length > 0) {
      if (insertIndex >= allButtons.length) {
        container.appendChild(placeholder);
      } else {
        container.insertBefore(placeholder, allButtons[insertIndex]);
      }
    }
  }
  
  function handleMouseUp() {
    if (!isDragging) return;
    
    isDragging = false;
    
    // Remove dragging class
    button.classList.remove('dragging');
    button.style.opacity = '1';
    button.style.transform = 'rotate(0deg) scale(1)';
    button.style.zIndex = 'auto';
    
    // Move button to placeholder position
    if (placeholder && placeholder.parentNode) {
      placeholder.parentNode.insertBefore(button, placeholder);
      placeholder.remove();
    }
    
    // Update button order in settings
    updateButtonOrder();
    
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  }
}

// Update button order in settings
function updateButtonOrder() {
  if (!floatingMenu || !floatingMenu.buttonContainer) return;
  
  const buttons = Array.from(floatingMenu.buttonContainer.children)
    .filter(child => child.classList.contains('overlay-button'))
    .map(btn => btn.dataset.buttonType);
  
  settings.overlayButtons = buttons;
  
  // Save to background
  chrome.runtime.sendMessage({
    action: 'updateSettings',
    settings: { overlayButtons: buttons }
  });
}

// Download selected images
function downloadSelectedImages() {
  const imagesToDownload = Array.from(selectedImages);
  if (imagesToDownload.length === 0) {
    showNotification('No images selected to download');
    return;
  }
  
  showNotification(`Starting download of ${imagesToDownload.length} images...`);
  
  // Debug logging
  console.log('Downloading images:', imagesToDownload);
  
  chrome.runtime.sendMessage({
    action: 'downloadImages',
    images: imagesToDownload.map(url => ({ url, title: document.title }))
  }, (response) => {
    console.log('Download response:', response);
    if (response && response.success) {
      // Remove borders after download
      imagesToDownload.forEach(imageUrl => {
        const img = document.querySelector(`img[src="${imageUrl}"]`);
        if (img) {
          removeImageBorder(img);
        }
      });
      
      selectedImages.clear();
      updateSelectionCounter();
      showNotification(`Successfully downloaded ${response.downloaded || imagesToDownload.length} images to your browser's download folder`);
    } else {
      showNotification(`Failed to download images: ${response.error || 'Unknown error'}`);
    }
  });
}

function openCollectionView() {
  chrome.runtime.sendMessage({ action: 'viewCollection' }, (response) => {
    const runtimeError = chrome.runtime.lastError && chrome.runtime.lastError.message;
    if (runtimeError) {
      showNotification(runtimeError);
      return;
    }
    if (!response || !response.success) {
      showNotification(response && response.error ? response.error : 'Unable to open collection');
    }
  });
}

// Create sidebar with enhanced features
function createSidebar() {
  if (sidebarElement) return;
  
  sidebarElement = document.createElement('div');
  sidebarElement.id = 'imagecapture-sidebar';
  sidebarElement.style.cssText = `
    position: fixed;
    top: 0;
    right: 0;
    width: 300px;
    height: 100vh;
    background: white;
    box-shadow: -2px 0 10px rgba(0, 0, 0, 0.3);
    z-index: 9999;
    display: flex;
    flex-direction: column;
    transition: width 0.3s ease;
    resize: horizontal;
    overflow: auto;
    min-width: 200px;
    max-width: 80vw;
  `;
  
  // Header
  const header = document.createElement('div');
  header.style.cssText = `
    background: #667eea;
    color: white;
    padding: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
  `;
  header.innerHTML = `
    <h3 style="margin: 0; font-size: 16px;">🖼️ ImageCapture Sidebar</h3>
    <button id="sidebar-close" style="background: #f44336; border: none; color: white; font-size: 18px; cursor: pointer; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold;">✕</button>
  `;
  
  // Controls
  const controls = document.createElement('div');
  controls.style.cssText = `
    padding: 12px;
    border-bottom: 1px solid #eee;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    flex-shrink: 0;
  `;
  
  const toggleBtn = document.createElement('button');
  toggleBtn.textContent = '🎯 Selection: OFF';
  toggleBtn.style.cssText = `
    background: #ff9800;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  toggleBtn.onclick = () => toggleSelectionMode();
  
  const selectAllBtn = document.createElement('button');
  selectAllBtn.textContent = '☑️ Select All';
  selectAllBtn.style.cssText = `
    background: #2196F3;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  selectAllBtn.onclick = () => toggleSelectAll();
  
  const refreshBtn = document.createElement('button');
  refreshBtn.textContent = '🔄 Refresh';
  refreshBtn.style.cssText = `
    background: #4CAF50;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  refreshBtn.onclick = () => refreshSidebar();
  
  const expandBtn = document.createElement('button');
  expandBtn.textContent = '📏 Expand';
  expandBtn.style.cssText = `
    background: #2196F3;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  expandBtn.onclick = () => toggleSidebarExpansion();
  
  const gridBtn = document.createElement('button');
  gridBtn.textContent = '🔲 Grid';
  gridBtn.style.cssText = `
    background: #9C27B0;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  gridBtn.onclick = () => toggleGridMode();
  
  const captureBtn = document.createElement('button');
  captureBtn.textContent = '📸 Capture All';
  captureBtn.style.cssText = `
    background: #4CAF50;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  captureBtn.onclick = () => captureAllImagesToSidebar();
  
  const viewCollectionBtn = document.createElement('button');
  viewCollectionBtn.textContent = '📋 View Collection';
  viewCollectionBtn.style.cssText = `
    background: #3F51B5;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  viewCollectionBtn.onclick = () => openCollectionView();
  
  const downloadBtn = document.createElement('button');
  downloadBtn.textContent = '📥 Download Selected';
  downloadBtn.style.cssText = `
    background: #FF9800;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  downloadBtn.onclick = () => downloadSelectedImages();
  
  const isolationBtn = document.createElement('button');
  isolationBtn.textContent = '🖼️ Image Mode';
  isolationBtn.style.cssText = `
    background: #9C27B0;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  isolationBtn.onclick = () => toggleIsolationMode();
  
  const overlayToggleBtn = document.createElement('button');
  overlayToggleBtn.textContent = '👁️ Overlay Menu On/Off';
  overlayToggleBtn.style.cssText = `
    background: #607D8B;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  overlayToggleBtn.onclick = () => toggleOverlayMenu();
  
  const toolbarToggleBtn = document.createElement('button');
  toolbarToggleBtn.textContent = '⚡ Quick Toolbar';
  toolbarToggleBtn.style.cssText = `
    background: #FF5722;
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: 500;
  `;
  toolbarToggleBtn.onclick = () => toggleQuickToolbar();
  
  controls.appendChild(toggleBtn);
  controls.appendChild(selectAllBtn);
  controls.appendChild(refreshBtn);
  controls.appendChild(expandBtn);
  controls.appendChild(gridBtn);
  controls.appendChild(captureBtn);
  controls.appendChild(viewCollectionBtn);
  controls.appendChild(downloadBtn);
  controls.appendChild(isolationBtn);
  controls.appendChild(overlayToggleBtn);
  controls.appendChild(toolbarToggleBtn);
  
  // Counter
  const counter = document.createElement('div');
  counter.textContent = 'Selected: 0';
  counter.style.cssText = `
    padding: 8px 12px;
    background: #f5f5f5;
    border-bottom: 1px solid #eee;
    font-size: 12px;
    font-weight: 500;
    color: #333;
    flex-shrink: 0;
  `;
  
  // Content area
  const content = document.createElement('div');
  content.style.cssText = `
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 8px;
    min-height: 0;
  `;
  
  sidebarElement.appendChild(header);
  sidebarElement.appendChild(controls);
  sidebarElement.appendChild(counter);
  sidebarElement.appendChild(content);
  
  // Store references
  sidebarElement.toggleBtn = toggleBtn;
  sidebarElement.selectAllBtn = selectAllBtn;
  sidebarElement.refreshBtn = refreshBtn;
  sidebarElement.expandBtn = expandBtn;
  sidebarElement.gridBtn = gridBtn;
  sidebarElement.viewCollectionBtn = viewCollectionBtn;
  sidebarElement.overlayToggleBtn = overlayToggleBtn;
  sidebarElement.toolbarToggleBtn = toolbarToggleBtn;
  sidebarElement.counter = counter;
  sidebarElement.content = content;
  sidebarElement.isExpanded = false;
  sidebarElement.isGridMode = true;
  
  // Close button event
  header.querySelector('#sidebar-close').onclick = () => toggleSidebar();
  
  document.body.appendChild(sidebarElement);
}

// Refresh sidebar content
function refreshSidebar() {
  if (!sidebarElement) return;
  
  captureAllImagesToSidebar();
  showNotification('Sidebar refreshed');
}

// Toggle sidebar
function toggleSidebar() {
  if (sidebarVisible) {
    if (sidebarElement) {
      sidebarElement.remove();
      sidebarElement = null;
    }
    sidebarVisible = false;
  } else {
    createSidebar();
    sidebarVisible = true;
  }
}

// Toggle sidebar expansion
function toggleSidebarExpansion() {
  if (!sidebarElement) return;
  
  sidebarElement.isExpanded = !sidebarElement.isExpanded;
  
  if (sidebarElement.isExpanded) {
    sidebarElement.style.width = '66vw';
    sidebarElement.expandBtn.textContent = '📏 Collapse';
  } else {
    sidebarElement.style.width = '300px';
    sidebarElement.expandBtn.textContent = '📏 Expand';
  }
}

// Toggle grid mode
function toggleGridMode() {
  if (!sidebarElement) return;
  
  sidebarElement.isGridMode = !sidebarElement.isGridMode;
  
  if (sidebarElement.isGridMode) {
    sidebarElement.content.style.gridTemplateColumns = 'repeat(2, 1fr)';
    sidebarElement.gridBtn.textContent = '🔲 Grid';
  } else {
    sidebarElement.content.style.gridTemplateColumns = '1fr';
    sidebarElement.gridBtn.textContent = '📱 Single';
  }
}

// Toggle quick toolbar mode
function toggleQuickToolbar() {
  settings.quickToolbarMode = !settings.quickToolbarMode;
  
  if (floatingMenu) {
    if (settings.quickToolbarMode) {
      // Switch to toolbar mode
      floatingMenu.style.cssText = `
        position: fixed;
        left: ${floatingMenuPosition.x}px;
        top: ${floatingMenuPosition.y}px;
        background: rgba(0, 0, 0, 0.9);
        backdrop-filter: blur(10px);
        border-radius: 8px;
        padding: 8px;
        z-index: 10000;
        display: flex;
        flex-direction: row;
        gap: 4px;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
        border: 1px solid rgba(255, 255, 255, 0.1);
        resize: both;
        overflow: auto;
        min-width: auto;
        max-width: 400px;
        width: auto;
        min-height: auto;
      `;
      
      // Update button container for horizontal layout
      if (floatingMenu.buttonContainer) {
        floatingMenu.buttonContainer.style.cssText = `
          display: flex;
          flex-direction: row;
          gap: 4px;
          margin-top: 0;
        `;
        
        // Update all buttons to compact size
        const buttons = floatingMenu.buttonContainer.querySelectorAll('.overlay-button');
        buttons.forEach(btn => {
          btn.style.cssText = `
            background: ${btn.style.background};
            color: white;
            border: none;
            padding: 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 10px;
            font-weight: 500;
            transition: all 0.2s ease;
            position: relative;
            user-select: none;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 16px;
            height: 16px;
            min-width: 16px;
            min-height: 16px;
          `;
          
          // Hide text, show only icon
          const textSpan = btn.querySelector('span');
          if (textSpan) {
            textSpan.style.display = 'none';
          }
          
          // Hide handle in toolbar mode
          const handle = btn.querySelector('.button-handle');
          if (handle) {
            handle.style.display = 'none';
          }
        });
      }
      
      // Hide counter in toolbar mode
      if (floatingMenu.counter) {
        floatingMenu.counter.style.display = 'none';
      }
      
      // Update sidebar button
      if (sidebarElement && sidebarElement.toolbarToggleBtn) {
        sidebarElement.toolbarToggleBtn.textContent = '📱 Full Menu';
        sidebarElement.toolbarToggleBtn.style.background = '#4CAF50';
      }
      
    } else {
      // Switch back to full menu mode
      floatingMenu.style.cssText = `
        position: fixed;
        left: ${floatingMenuPosition.x}px;
        top: ${floatingMenuPosition.y}px;
        background: rgba(0, 0, 0, 0.8);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        padding: 16px;
        z-index: 10000;
        display: flex;
        flex-direction: column;
        gap: 8px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
        min-width: 200px;
        max-width: 280px;
        width: 280px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        resize: both;
        overflow: auto;
      `;
      
      // Update button container for vertical layout
      if (floatingMenu.buttonContainer) {
        floatingMenu.buttonContainer.style.cssText = `
          display: flex;
          flex-direction: column;
          gap: 8px;
          margin-top: 20px;
        `;
        
        // Update all buttons to full size
        const buttons = floatingMenu.buttonContainer.querySelectorAll('.overlay-button');
        buttons.forEach(btn => {
          btn.style.cssText = `
            background: ${btn.style.background};
            color: white;
            border: none;
            padding: 10px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.2s ease;
            position: relative;
            user-select: none;
            display: flex;
            align-items: center;
            gap: 8px;
            width: auto;
            height: auto;
            min-width: auto;
            min-height: auto;
          `;
          
          // Show text
          const textSpan = btn.querySelector('span');
          if (textSpan) {
            textSpan.style.display = 'inline';
          }
          
          // Show handle
          const handle = btn.querySelector('.button-handle');
          if (handle) {
            handle.style.display = 'inline';
          }
        });
      }
      
      // Show counter
      if (floatingMenu.counter) {
        floatingMenu.counter.style.display = 'block';
      }
      
      // Update sidebar button
      if (sidebarElement && sidebarElement.toolbarToggleBtn) {
        sidebarElement.toolbarToggleBtn.textContent = '📱 Toolbar';
        sidebarElement.toolbarToggleBtn.style.background = '#2196F3';
      }
    }
    
    // Ensure menu is visible
    floatingMenu.style.display = 'flex';
    
    // Save settings
    chrome.runtime.sendMessage({
      action: 'updateSettings',
      settings: settings
    });
  }
}

// Capture all images to sidebar
function captureAllImagesToSidebar() {
  if (!sidebarElement) return;
  
  const images = document.querySelectorAll('img');
  sidebarElement.content.innerHTML = '';
  
  images.forEach(img => {
    if (shouldCaptureImage(img)) {
      const item = createSidebarImageItem(img);
      sidebarElement.content.appendChild(item);
    }
  });
}

// Check if image should be captured
function shouldCaptureImage(img) {
  const minWidth = settings.minImageWidth || 100;
  const preferredTypes = settings.preferredFileTypes || ['jpg', 'jpeg', 'png'];
  
  if (img.naturalWidth < minWidth) return false;
  
  const url = img.src.toLowerCase();
  const hasPreferredType = preferredTypes.some(type => url.includes('.' + type));
  if (!hasPreferredType) return false;
  
  if (img.offsetParent === null) return false;
  
  return true;
}

// Create sidebar image item
function createSidebarImageItem(img) {
  const item = document.createElement('div');
  item.style.cssText = `
    border: 1px solid #ddd;
    border-radius: 4px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s ease;
  `;
  
  const imgElement = document.createElement('img');
  imgElement.src = img.src;
  imgElement.style.cssText = `
    width: 100%;
    height: auto;
    display: block;
  `;
  
  item.appendChild(imgElement);
  
  item.onclick = () => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      item.style.borderColor = '#ddd';
    } else {
      selectedImages.add(img.src);
      item.style.borderColor = '#4CAF50';
    }
    updateSelectionCounter();
  };
  
  return item;
}

// Toggle isolation mode
function toggleIsolationMode() {
  isolationMode = !isolationMode;
  
  if (isolationMode) {
    const images = document.querySelectorAll('img');
    const container = document.createElement('div');
    container.id = 'imagecapture-isolation';
    container.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: #000;
      z-index: 10000;
      overflow: auto;
      padding: 20px;
    `;
    
    const header = document.createElement('div');
    header.style.cssText = `
      position: sticky;
      top: 0;
      background: rgba(0, 0, 0, 0.8);
      color: white;
      padding: 16px;
      margin: -20px -20px 20px -20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    `;
    
    const closeBtn = document.createElement('button');
    closeBtn.textContent = '✕ Close';
    closeBtn.style.cssText = `
      background: #f44336;
      color: white;
      border: none;
      padding: 8px 12px;
      border-radius: 4px;
      cursor: pointer;
      font-weight: bold;
      font-size: 14px;
    `;
    closeBtn.onclick = () => toggleIsolationMode();
    
    header.innerHTML = '<h2>🖼️ Image Isolation Mode</h2>';
    header.appendChild(closeBtn);
    
    const grid = document.createElement('div');
    grid.style.cssText = `
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
    `;
    
    images.forEach(img => {
      if (shouldCaptureImage(img)) {
        const item = createIsolationImageItem(img);
        grid.appendChild(item);
      }
    });
    
    container.appendChild(header);
    container.appendChild(grid);
    document.body.appendChild(container);
  } else {
    const container = document.getElementById('imagecapture-isolation');
    if (container) {
      container.remove();
    }
  }
}

// Create isolation image item
function createIsolationImageItem(img) {
  const item = document.createElement('div');
  item.style.cssText = `
    border: 2px solid #333;
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s ease;
    background: #222;
  `;
  
  const imgElement = document.createElement('img');
  imgElement.src = img.src;
  imgElement.style.cssText = `
    width: 100%;
    height: auto;
    display: block;
  `;
  
  item.appendChild(imgElement);
  
  item.onclick = () => {
    if (selectedImages.has(img.src)) {
      selectedImages.delete(img.src);
      item.style.borderColor = '#333';
    } else {
      selectedImages.add(img.src);
      item.style.borderColor = '#4CAF50';
    }
    updateSelectionCounter();
  };
  
  return item;
}

// Show notification
function showNotification(message) {
  if (settings.showNotifications) {
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: #333;
      color: white;
      padding: 12px 20px;
      border-radius: 6px;
      z-index: 10001;
      font-size: 14px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    `;
    notification.textContent = message;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
      notification.remove();
    }, 3000);
  }
}

// Handle keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  
  switch (e.key.toLowerCase()) {
    case 's':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        toggleSelectionMode();
      }
      break;
    case 'i':
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        captureAllImagesToSidebar();
      }
      break;
    case 'q':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        // Quick capture logic
      }
      break;
    case 'd':
      if (!e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        downloadSelectedImages();
      }
      break;
    case 'escape':
      if (selectionMode) {
        selectionMode = false;
        document.body.style.cursor = 'default';
        showNotification('Selection mode OFF');
      }
      break;
  }
});

// Listen for messages from background script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'toggleOverlay':
      overlayMenuVisible = !overlayMenuVisible;
      if (floatingMenu) {
        floatingMenu.style.display = overlayMenuVisible ? 'flex' : 'none';
      }
      break;
      
    case 'updateSettings':
      const oldUseOverlayIcons = settings.useOverlayIcons;
      const oldShowSelectionIndicator = settings.showSelectionIndicator;
      
      settings = { ...settings, ...request.settings };
      
      // If overlay icons setting changed, refresh all image indicators
      if (oldUseOverlayIcons !== settings.useOverlayIcons || 
          oldShowSelectionIndicator !== settings.showSelectionIndicator) {
        addImageIndicators();
      }
      break;
      
    case 'updateFloatingMenuPosition':
      floatingMenuPosition = request.position;
      if (floatingMenu) {
        // Use absolute positioning
        floatingMenu.style.left = `${floatingMenuPosition.x}px`;
        floatingMenu.style.top = `${floatingMenuPosition.y}px`;
        floatingMenu.style.right = 'auto';
        if (floatingMenuPosition.width && !settings.quickToolbarMode) {
          floatingMenu.style.minWidth = `${floatingMenuPosition.width}px`;
        }
      }
      break;
      
    case 'captureImages':
      captureSelectedImages();
      break;
      
    case 'downloadImages':
      downloadSelectedImages();
      break;
      
    case 'toggleSelectionMode':
      toggleSelectionMode();
      break;
      
    case 'selectAllImages':
      selectAllImages();
      break;
      
    case 'deselectAllImages':
      deselectAllImages();
      break;
      
    case 'toggleSidebar':
      toggleSidebar();
      break;
      
    case 'toggleIsolationMode':
      toggleIsolationMode();
      break;
      
    case 'toggleQuickToolbar':
      toggleQuickToolbar();
      break;
      
    case 'toggleOverlayMenu':
      toggleOverlayMenu();
      break;
      
    case 'toggleSelectAll':
      toggleSelectAll();
      break;
      
    case 'captureSelectedImages':
      captureSelectedImages();
      break;
      
    case 'downloadSelectedImages':
      downloadSelectedImages();
      break;
      
    case 'clearCapturedImages':
      chrome.runtime.sendMessage({
        action: 'clearCapturedImages'
      });
      showNotification('Collection cleared');
      break;
      
    case 'imagesCleared':
      showNotification('Collection cleared');
      break;
  }
  
  sendResponse({ success: true });
}); 
```

## Summary
- Added a packaged collection UI (`collection.html`, `collection.css`, `collection.js`) that renders captures, selection tools, and empty-state messaging entirely with external scripts/styles, avoiding CSP violations while keeping the original look-and-feel.  
```1:61:imagebrowserextension/imagebrowserextensiondev/browserextension/browser-extension/collection.html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    ...
    <script src="collection.js"></script>
</body>
</html>
```
```1:255:imagebrowserextension/imagebrowserextensiondev/browserextension/browser-extension/collection.css
body {
    margin: 0;
    padding: 20px;
    ...
}
```
```1:321:imagebrowserextension/imagebrowserextensiondev/browserextension/browser-extension/collection.js
(() => {
  const imageGrid = document.getElementById('imageGrid');
  ...
})();
```
- Updated the service worker to open the new page through `chrome.runtime.getURL`, eliminating the blob-based inline HTML generation that triggered CSP errors.  
```213:227:imagebrowserextension/imagebrowserextensiondev/browserextension/browser-extension/background.js
    case 'viewCollection':
      try {
        const pageUrl = chrome.runtime.getURL('collection.html');
        chrome.tabs.create({ url: pageUrl }, (tab) => {
          ...
        });
        return true;
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;
```
- Hardened the content-side launcher to surface runtime errors when opening the collection, keeping the overlay/sidebar buttons reliable.  
```1038:1047:imagebrowserextension/imagebrowserextensiondev/browserextension/browser-extension/content.js
function openCollectionView() {
  chrome.runtime.sendMessage({ action: 'viewCollection' }, (response) => {
    const runtimeError = chrome.runtime.lastError && chrome.runtime.lastError.message;
    if (runtimeError) {
      showNotification(runtimeError);
      return;
    }
    if (!response || !response.success) {
      showNotification(response && response.error ? response.error : 'Unable to open collection');
    }
  });
}
```

## Testing
- Not run (extension build requires manual browser reload).  

Reload the unpacked extension, then use “View Collection” from the popup, overlay, or sidebar; the new tab should load without CSP console errors and display captured images or the empty-state message.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    ...
    <script src="collection.js"></script>
</body>
</html>
```

```css
body {
    margin: 0;
    padding: 20px;
    ...
}
```

```javascript
(() => {
  const imageGrid = document.getElementById('imageGrid');
  ...
})();
```

```javascript
    case 'viewCollection':
      try {
        const pageUrl = chrome.runtime.getURL('collection.html');
        chrome.tabs.create({ url: pageUrl }, (tab) => {
          ...
        });
        return true;
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;
```

```javascript
function openCollectionView() {
  chrome.runtime.sendMessage({ action: 'viewCollection' }, (response) => {
    const runtimeError = chrome.runtime.lastError && chrome.runtime.lastError.message;
    if (runtimeError) {
      showNotification(runtimeError);
      return;
    }
    if (!response || !response.success) {
      showNotification(response && response.error ? response.error : 'Unable to open collection');
    }
  });
}
```

