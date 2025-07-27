// Excel Unified Service Worker
// PWA 오프라인 지원 및 캐싱 관리

const CACHE_NAME = 'excel-unified-v1.0.0';
const STATIC_CACHE_NAME = 'excel-unified-static-v1.0.0';
const DYNAMIC_CACHE_NAME = 'excel-unified-dynamic-v1.0.0';

// 캐시할 정적 자원들
const STATIC_ASSETS = [
  '/',
  '/static/css/main.css',
  '/static/js/main.js',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
  '/manifest.json',
  '/offline.html'
];

// 캐시할 API 엔드포인트들
const API_ENDPOINTS = [
  '/api/v1/health',
  '/api/v1/i18n/languages',
  '/api/v1/excel-templates/categories'
];

// 서비스 워커 설치
self.addEventListener('install', event => {
  console.log('[SW] Installing Service Worker...');
  
  event.waitUntil(
    Promise.all([
      // 정적 자원 캐싱
      caches.open(STATIC_CACHE_NAME).then(cache => {
        console.log('[SW] Caching static assets');
        return cache.addAll(STATIC_ASSETS);
      }),
      // API 엔드포인트 사전 캐싱
      caches.open(DYNAMIC_CACHE_NAME).then(cache => {
        console.log('[SW] Pre-caching API endpoints');
        return Promise.all(
          API_ENDPOINTS.map(endpoint => {
            return fetch(endpoint)
              .then(response => cache.put(endpoint, response.clone()))
              .catch(err => console.log(`[SW] Failed to cache ${endpoint}:`, err));
          })
        );
      })
    ]).then(() => {
      console.log('[SW] Service Worker installed successfully');
      // 즉시 활성화
      return self.skipWaiting();
    })
  );
});

// 서비스 워커 활성화
self.addEventListener('activate', event => {
  console.log('[SW] Activating Service Worker...');
  
  event.waitUntil(
    Promise.all([
      // 이전 캐시 정리
      caches.keys().then(cacheNames => {
        return Promise.all(
          cacheNames.map(cacheName => {
            if (cacheName !== STATIC_CACHE_NAME && 
                cacheName !== DYNAMIC_CACHE_NAME &&
                cacheName !== CACHE_NAME) {
              console.log('[SW] Deleting old cache:', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      }),
      // 모든 클라이언트 제어
      self.clients.claim()
    ]).then(() => {
      console.log('[SW] Service Worker activated successfully');
    })
  );
});

// 네트워크 요청 인터셉트
self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);
  
  // POST 요청은 캐시하지 않음
  if (request.method !== 'GET') {
    return;
  }
  
  // Chrome Extension 요청 무시
  if (url.protocol === 'chrome-extension:') {
    return;
  }
  
  event.respondWith(
    handleFetchRequest(request)
  );
});

// 요청 처리 전략
async function handleFetchRequest(request) {
  const url = new URL(request.url);
  
  try {
    // 1. 정적 자원 처리 (Cache First)
    if (isStaticAsset(request)) {
      return await cacheFirst(request, STATIC_CACHE_NAME);
    }
    
    // 2. API 요청 처리 (Network First with Cache Fallback)
    if (isAPIRequest(request)) {
      return await networkFirstWithCache(request, DYNAMIC_CACHE_NAME);
    }
    
    // 3. Excel 파일 분석 결과 (Cache First with Network Update)
    if (isAnalysisResult(request)) {
      return await cacheFirstWithNetworkUpdate(request, DYNAMIC_CACHE_NAME);
    }
    
    // 4. 기본 전략 (Network First)
    return await networkFirst(request);
    
  } catch (error) {
    console.error('[SW] Fetch failed:', error);
    
    // 오프라인 페이지 반환
    if (request.destination === 'document') {
      return caches.match('/offline.html');
    }
    
    // 기본 에러 응답
    return new Response('오프라인 상태에서는 이 기능을 사용할 수 없습니다.', {
      status: 503,
      statusText: 'Service Unavailable',
      headers: new Headers({
        'Content-Type': 'text/plain; charset=utf-8'
      })
    });
  }
}

// 정적 자원 판별
function isStaticAsset(request) {
  const url = new URL(request.url);
  return url.pathname.startsWith('/static/') || 
         url.pathname === '/manifest.json' ||
         url.pathname.endsWith('.css') ||
         url.pathname.endsWith('.js') ||
         url.pathname.endsWith('.png') ||
         url.pathname.endsWith('.jpg') ||
         url.pathname.endsWith('.ico');
}

// API 요청 판별
function isAPIRequest(request) {
  const url = new URL(request.url);
  return url.pathname.startsWith('/api/');
}

// 분석 결과 판별
function isAnalysisResult(request) {
  const url = new URL(request.url);
  return url.pathname.includes('/analysis/') ||
         url.pathname.includes('/templates/') ||
         url.searchParams.has('analysis_id');
}

// Cache First 전략
async function cacheFirst(request, cacheName) {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }
  
  const networkResponse = await fetch(request);
  const cache = await caches.open(cacheName);
  cache.put(request, networkResponse.clone());
  
  return networkResponse;
}

// Network First with Cache Fallback 전략
async function networkFirstWithCache(request, cacheName) {
  try {
    const networkResponse = await fetch(request);
    
    // 성공적인 응답만 캐시
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.log('[SW] Network failed, trying cache:', request.url);
    const cachedResponse = await caches.match(request);
    
    if (cachedResponse) {
      return cachedResponse;
    }
    
    throw error;
  }
}

// Cache First with Network Update 전략
async function cacheFirstWithNetworkUpdate(request, cacheName) {
  const cachedResponse = await caches.match(request);
  
  // 백그라운드에서 네트워크 업데이트
  const networkUpdate = fetch(request).then(response => {
    if (response.ok) {
      caches.open(cacheName).then(cache => {
        cache.put(request, response.clone());
      });
    }
    return response;
  }).catch(() => {
    // 네트워크 실패는 무시
  });
  
  // 캐시된 응답이 있으면 즉시 반환
  if (cachedResponse) {
    return cachedResponse;
  }
  
  // 캐시가 없으면 네트워크 응답 대기
  return await networkUpdate;
}

// Network First 전략
async function networkFirst(request) {
  try {
    return await fetch(request);
  } catch (error) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    throw error;
  }
}

// 백그라운드 동기화 처리
self.addEventListener('sync', event => {
  console.log('[SW] Background sync event:', event.tag);
  
  if (event.tag === 'excel-analysis-sync') {
    event.waitUntil(syncPendingAnalysis());
  } else if (event.tag === 'user-preferences-sync') {
    event.waitUntil(syncUserPreferences());
  }
});

// 대기 중인 Excel 분석 동기화
async function syncPendingAnalysis() {
  try {
    const pendingAnalysis = await getPendingAnalysis();
    
    for (const analysis of pendingAnalysis) {
      try {
        await fetch('/api/v1/excel/analyze', {
          method: 'POST',
          body: analysis.formData,
          headers: analysis.headers
        });
        
        // 성공하면 로컬 스토리지에서 제거
        await removePendingAnalysis(analysis.id);
        
      } catch (error) {
        console.error('[SW] Failed to sync analysis:', error);
      }
    }
  } catch (error) {
    console.error('[SW] Sync failed:', error);
  }
}

// 사용자 설정 동기화
async function syncUserPreferences() {
  try {
    const preferences = await getUserPreferences();
    
    await fetch('/api/v1/user/preferences', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(preferences)
    });
    
  } catch (error) {
    console.error('[SW] Failed to sync preferences:', error);
  }
}

// 푸시 알림 처리
self.addEventListener('push', event => {
  console.log('[SW] Push notification received');
  
  const options = {
    body: 'Excel 분석이 완료되었습니다.',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/badge-72x72.png',
    tag: 'excel-analysis',
    data: {
      url: '/dashboard'
    },
    actions: [
      {
        action: 'view',
        title: '결과 보기',
        icon: '/static/icons/view-24x24.png'
      },
      {
        action: 'dismiss',
        title: '닫기',
        icon: '/static/icons/close-24x24.png'
      }
    ],
    requireInteraction: true,
    timestamp: Date.now()
  };
  
  if (event.data) {
    try {
      const data = event.data.json();
      options.body = data.message || options.body;
      options.data = { ...options.data, ...data };
    } catch (error) {
      console.error('[SW] Failed to parse push data:', error);
    }
  }
  
  event.waitUntil(
    self.registration.showNotification('Excel Unified', options)
  );
});

// 알림 클릭 처리
self.addEventListener('notificationclick', event => {
  console.log('[SW] Notification clicked:', event);
  
  event.notification.close();
  
  const action = event.action;
  const data = event.notification.data;
  
  if (action === 'view' || !action) {
    const url = data.url || '/dashboard';
    
    event.waitUntil(
      clients.matchAll().then(clientList => {
        // 이미 열린 탭이 있는지 확인
        for (const client of clientList) {
          if (client.url.includes(url) && 'focus' in client) {
            return client.focus();
          }
        }
        
        // 새 탭 열기
        if (clients.openWindow) {
          return clients.openWindow(url);
        }
      })
    );
  }
});

// 헬퍼 함수들
async function getPendingAnalysis() {
  // IndexedDB에서 대기 중인 분석 가져오기
  return [];
}

async function removePendingAnalysis(id) {
  // IndexedDB에서 완료된 분석 제거
}

async function getUserPreferences() {
  // 로컬 스토리지에서 사용자 설정 가져오기
  return {};
}

// 메시지 처리 (클라이언트와 통신)
self.addEventListener('message', event => {
  console.log('[SW] Message received:', event.data);
  
  const { type, payload } = event.data;
  
  switch (type) {
    case 'SKIP_WAITING':
      self.skipWaiting();
      break;
      
    case 'CACHE_ANALYSIS_RESULT':
      cacheAnalysisResult(payload);
      break;
      
    case 'GET_CACHE_STATUS':
      getCacheStatus().then(status => {
        event.ports[0].postMessage({ type: 'CACHE_STATUS', payload: status });
      });
      break;
      
    default:
      console.log('[SW] Unknown message type:', type);
  }
});

// 분석 결과 캐싱
async function cacheAnalysisResult(result) {
  try {
    const cache = await caches.open(DYNAMIC_CACHE_NAME);
    const response = new Response(JSON.stringify(result), {
      headers: { 'Content-Type': 'application/json' }
    });
    
    await cache.put(`/analysis/${result.id}`, response);
    console.log('[SW] Analysis result cached:', result.id);
  } catch (error) {
    console.error('[SW] Failed to cache analysis result:', error);
  }
}

// 캐시 상태 확인
async function getCacheStatus() {
  const cacheNames = await caches.keys();
  const status = {};
  
  for (const cacheName of cacheNames) {
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();
    status[cacheName] = keys.length;
  }
  
  return status;
}

console.log('[SW] Service Worker script loaded');