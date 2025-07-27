// k6/scripts/soak-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { randomItem } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// Soak test configuration - run for extended period with moderate load
export let options = {
  stages: [
    { duration: '5m', target: 50 },    // Ramp up to 50 users
    { duration: '2h', target: 50 },    // Stay at 50 users for 2 hours
    { duration: '5m', target: 0 },     // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<600'],  // 95% of requests under 600ms
    http_req_failed: ['rate<0.05'],    // Error rate under 5%
    http_reqs: ['rate>50'],            // At least 50 requests per second
    
    // Memory leak detection thresholds
    'http_req_duration{scenario:memory_check}': ['avg<500', 'max<2000'],
  },
};

const testUsers = new SharedArray('users', function() {
  return [
    { email: 'soak1@example.com', password: 'password123' },
    { email: 'soak2@example.com', password: 'password123' },
    { email: 'soak3@example.com', password: 'password123' },
  ];
});

const BASE_URL = __ENV.BASE_URL || 'http://localhost:3000';
const API_URL = `${BASE_URL}/api/v1`;

// Track metrics over time
let requestCount = 0;
let errorCount = 0;
let avgResponseTime = [];

export default function() {
  const user = randomItem(testUsers);
  
  // Authenticate
  let loginRes = http.post(
    `${API_URL}/auth/login`,
    JSON.stringify(user),
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  if (!check(loginRes, { 'login successful': (r) => r.status === 200 })) {
    errorCount++;
    return;
  }
  
  const token = loginRes.json('token');
  const authHeaders = {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  };
  
  // Simulate typical user behavior
  
  // 1. Browse dashboard
  let dashboardRes = http.get(`${API_URL}/dashboard/stats`, authHeaders);
  check(dashboardRes, {
    'dashboard loaded': (r) => r.status === 200,
  });
  avgResponseTime.push(dashboardRes.timings.duration);
  sleep(2);
  
  // 2. List Excel files
  let filesRes = http.get(`${API_URL}/excel_analysis/files?page=1&per_page=10`, authHeaders);
  check(filesRes, {
    'files listed': (r) => r.status === 200,
  });
  avgResponseTime.push(filesRes.timings.duration);
  sleep(1);
  
  // 3. Search knowledge base (memory-intensive operation)
  const searchTerms = ['excel', 'data', 'analysis', 'formula', 'pivot'];
  const searchTerm = randomItem(searchTerms);
  
  let searchRes = http.get(
    `${API_URL}/knowledge_base/qa_pairs?q=${searchTerm}`,
    { ...authHeaders, tags: { scenario: 'memory_check' } }
  );
  
  check(searchRes, {
    'search successful': (r) => r.status === 200,
    'search has results': (r) => r.json('qa_pairs.length') > 0,
  });
  avgResponseTime.push(searchRes.timings.duration);
  sleep(3);
  
  // 4. Create and update data (database operations)
  if (Math.random() < 0.3) { // 30% chance to create content
    const qaData = {
      question: `Soak test question ${Date.now()} - ${requestCount}`,
      answer: `This is a detailed answer for the soak test. It contains enough text to simulate real usage patterns. ${Math.random()}`,
      category: randomItem(['general', 'technical', 'analysis']),
    };
    
    let createRes = http.post(
      `${API_URL}/knowledge_base/qa_pairs`,
      JSON.stringify(qaData),
      authHeaders
    );
    
    check(createRes, {
      'content created': (r) => r.status === 201,
    });
    
    if (createRes.status === 201) {
      const qaId = createRes.json('qa_pair.id');
      sleep(1);
      
      // Update the created content
      let updateRes = http.patch(
        `${API_URL}/knowledge_base/qa_pairs/${qaId}`,
        JSON.stringify({ answer: qaData.answer + ' [Updated]' }),
        authHeaders
      );
      
      check(updateRes, {
        'content updated': (r) => r.status === 200,
      });
    }
  }
  
  // 5. Chat session (connection pooling test)
  if (Math.random() < 0.2) { // 20% chance for chat
    const sessionData = {
      title: `Soak test chat ${Date.now()}`,
      context_type: 'general',
    };
    
    let sessionRes = http.post(
      `${API_URL}/ai_consultation/sessions`,
      JSON.stringify(sessionData),
      authHeaders
    );
    
    if (check(sessionRes, { 'chat session created': (r) => r.status === 201 })) {
      const sessionId = sessionRes.json('session.id');
      
      // Send a message
      let messageRes = http.post(
        `${API_URL}/ai_consultation/sessions/${sessionId}/messages`,
        JSON.stringify({ content: 'How do I perform regression analysis in Excel?' }),
        authHeaders
      );
      
      check(messageRes, {
        'message sent': (r) => r.status === 201,
        'AI responded': (r) => r.json('message.content') !== undefined,
      });
    }
  }
  
  // 6. Logout
  let logoutRes = http.del(`${API_URL}/auth/logout`, null, authHeaders);
  check(logoutRes, {
    'logout successful': (r) => r.status === 200,
  });
  
  requestCount++;
  
  // Every 1000 requests, log performance metrics
  if (requestCount % 1000 === 0) {
    const avgTime = avgResponseTime.reduce((a, b) => a + b, 0) / avgResponseTime.length;
    console.log(`Requests: ${requestCount}, Errors: ${errorCount}, Avg Response: ${avgTime.toFixed(2)}ms`);
    
    // Reset metrics array to prevent memory buildup
    avgResponseTime = [];
  }
  
  sleep(5);
}

// Separate scenario for monitoring system health
export function healthCheck() {
  // Simple health check endpoint
  let healthRes = http.get(`${BASE_URL}/up`);
  
  check(healthRes, {
    'system healthy': (r) => r.status === 200,
    'response time normal': (r) => r.timings.duration < 100,
  });
  
  // Check database connectivity
  let dbHealthRes = http.get(`${API_URL}/health/database`);
  
  check(dbHealthRes, {
    'database connected': (r) => r.status === 200,
    'database response fast': (r) => r.timings.duration < 200,
  });
  
  // Check Redis/cache connectivity
  let cacheHealthRes = http.get(`${API_URL}/health/cache`);
  
  check(cacheHealthRes, {
    'cache connected': (r) => r.status === 200,
    'cache response fast': (r) => r.timings.duration < 50,
  });
  
  sleep(30); // Health check every 30 seconds
}

// Scenario for detecting memory leaks
export function memoryLeakDetection() {
  const user = testUsers[0];
  
  // Authenticate once
  let loginRes = http.post(
    `${API_URL}/auth/login`,
    JSON.stringify(user),
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  const token = loginRes.json('token');
  const authHeaders = {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  };
  
  // Repeatedly perform operations that might leak memory
  for (let i = 0; i < 100; i++) {
    // Large data retrieval
    let largeDataRes = http.get(
      `${API_URL}/excel_analysis/files?page=1&per_page=100&include_analysis=true`,
      authHeaders
    );
    
    check(largeDataRes, {
      'large data retrieved': (r) => r.status === 200,
    });
    
    // Complex search with joins
    let complexSearchRes = http.get(
      `${API_URL}/knowledge_base/qa_pairs?q=excel&include_embeddings=true&include_metadata=true`,
      authHeaders
    );
    
    check(complexSearchRes, {
      'complex search completed': (r) => r.status === 200,
    });
    
    sleep(0.5);
  }
  
  sleep(60); // Wait before next iteration
}