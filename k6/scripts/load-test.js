// k6/scripts/load-test.js
import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { SharedArray } from 'k6/data';
import { randomItem } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// Test configuration
export let options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp up to 50 users
    { duration: '5m', target: 100 },  // Ramp up to 100 users
    { duration: '10m', target: 100 }, // Stay at 100 users
    { duration: '5m', target: 200 },  // Spike to 200 users
    { duration: '10m', target: 100 }, // Back to 100 users
    { duration: '3m', target: 0 },    // Ramp down to 0
  ],
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'], // 95% under 500ms, 99% under 1s
    http_req_failed: ['rate<0.1'],                   // Error rate under 10%
    http_reqs: ['rate>100'],                         // At least 100 requests per second
  },
};

// Test data
const testUsers = new SharedArray('users', function() {
  return [
    { email: 'test1@example.com', password: 'password123' },
    { email: 'test2@example.com', password: 'password123' },
    { email: 'test3@example.com', password: 'password123' },
    { email: 'test4@example.com', password: 'password123' },
    { email: 'test5@example.com', password: 'password123' },
  ];
});

const BASE_URL = __ENV.BASE_URL || 'http://localhost:3000';
const API_URL = `${BASE_URL}/api/v1`;

// Helper functions
function authenticateUser(user) {
  let loginRes = http.post(
    `${API_URL}/auth/login`,
    JSON.stringify(user),
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  check(loginRes, {
    'login successful': (r) => r.status === 200,
    'token received': (r) => r.json('token') !== '',
  });
  
  return loginRes.json('token');
}

function getAuthHeaders(token) {
  return {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  };
}

// Main test scenario
export default function() {
  const user = randomItem(testUsers);
  
  group('Authentication Flow', function() {
    // Login
    const token = authenticateUser(user);
    const authHeaders = getAuthHeaders(token);
    
    // Get profile
    let profileRes = http.get(`${API_URL}/profile`, authHeaders);
    check(profileRes, {
      'profile retrieved': (r) => r.status === 200,
      'correct user email': (r) => r.json('user.email') === user.email,
    });
    
    sleep(1);
  });
  
  group('Excel Analysis Flow', function() {
    const token = authenticateUser(user);
    const authHeaders = getAuthHeaders(token);
    
    // List files
    let filesRes = http.get(`${API_URL}/excel_analysis/files`, authHeaders);
    check(filesRes, {
      'files listed': (r) => r.status === 200,
      'response time OK': (r) => r.timings.duration < 300,
    });
    
    // Upload file (simulated with small payload)
    const payload = {
      file: http.file(open('./test-data/small.xlsx', 'b'), 'test.xlsx'),
    };
    
    let uploadRes = http.post(
      `${API_URL}/excel_analysis/files`,
      payload,
      authHeaders
    );
    
    check(uploadRes, {
      'file uploaded': (r) => r.status === 201,
      'file ID returned': (r) => r.json('file.id') !== undefined,
      'upload time acceptable': (r) => r.timings.duration < 2000,
    });
    
    if (uploadRes.status === 201) {
      const fileId = uploadRes.json('file.id');
      
      // Poll for analysis completion
      let attempts = 0;
      let analysisComplete = false;
      
      while (attempts < 10 && !analysisComplete) {
        sleep(2);
        
        let statusRes = http.get(
          `${API_URL}/excel_analysis/files/${fileId}`,
          authHeaders
        );
        
        if (statusRes.json('file.status') === 'completed') {
          analysisComplete = true;
          check(statusRes, {
            'analysis completed': (r) => r.json('file.analysis_result') !== null,
          });
        }
        
        attempts++;
      }
    }
    
    sleep(2);
  });
  
  group('Knowledge Base Operations', function() {
    const token = authenticateUser(user);
    const authHeaders = getAuthHeaders(token);
    
    // Search QA pairs
    let searchRes = http.get(
      `${API_URL}/knowledge_base/qa_pairs?q=excel`,
      authHeaders
    );
    
    check(searchRes, {
      'search successful': (r) => r.status === 200,
      'search results returned': (r) => r.json('qa_pairs') !== undefined,
      'search response fast': (r) => r.timings.duration < 200,
    });
    
    // Create QA pair
    const qaData = {
      question: `Test question ${Date.now()}`,
      answer: 'Test answer with some details',
      category: 'general',
    };
    
    let createRes = http.post(
      `${API_URL}/knowledge_base/qa_pairs`,
      JSON.stringify(qaData),
      authHeaders
    );
    
    check(createRes, {
      'QA pair created': (r) => r.status === 201,
      'QA ID returned': (r) => r.json('qa_pair.id') !== undefined,
    });
    
    sleep(1);
  });
  
  group('AI Consultation', function() {
    const token = authenticateUser(user);
    const authHeaders = getAuthHeaders(token);
    
    // Create chat session
    const sessionData = {
      title: `Performance test session ${Date.now()}`,
      context_type: 'general',
    };
    
    let sessionRes = http.post(
      `${API_URL}/ai_consultation/sessions`,
      JSON.stringify(sessionData),
      authHeaders
    );
    
    check(sessionRes, {
      'session created': (r) => r.status === 201,
      'session ID returned': (r) => r.json('session.id') !== undefined,
    });
    
    if (sessionRes.status === 201) {
      const sessionId = sessionRes.json('session.id');
      
      // Send message
      const messageData = {
        content: 'What is the best way to analyze Excel data?',
      };
      
      let messageRes = http.post(
        `${API_URL}/ai_consultation/sessions/${sessionId}/messages`,
        JSON.stringify(messageData),
        authHeaders
      );
      
      check(messageRes, {
        'message sent': (r) => r.status === 201,
        'AI response received': (r) => r.json('message.role') === 'assistant',
        'response time acceptable': (r) => r.timings.duration < 5000,
      });
    }
    
    sleep(3);
  });
}

// Stress test scenario
export function stressTest() {
  const user = randomItem(testUsers);
  const token = authenticateUser(user);
  const authHeaders = getAuthHeaders(token);
  
  // Rapid file uploads
  for (let i = 0; i < 5; i++) {
    const payload = {
      file: http.file(open('./test-data/small.xlsx', 'b'), `stress-${i}.xlsx`),
    };
    
    let uploadRes = http.post(
      `${API_URL}/excel_analysis/files`,
      payload,
      authHeaders
    );
    
    check(uploadRes, {
      'stress upload successful': (r) => r.status === 201,
    });
  }
  
  // Concurrent searches
  let batch = [
    ['GET', `${API_URL}/knowledge_base/qa_pairs?q=excel`, null, authHeaders],
    ['GET', `${API_URL}/knowledge_base/qa_pairs?q=data`, null, authHeaders],
    ['GET', `${API_URL}/knowledge_base/qa_pairs?q=analysis`, null, authHeaders],
  ];
  
  let responses = http.batch(batch);
  
  responses.forEach((res, i) => {
    check(res, {
      [`batch request ${i} successful`]: (r) => r.status === 200,
    });
  });
}

// Spike test scenario
export function spikeTest() {
  // Simulate sudden spike in chat messages
  const user = randomItem(testUsers);
  const token = authenticateUser(user);
  const authHeaders = getAuthHeaders(token);
  
  // Create multiple sessions simultaneously
  let sessionPromises = [];
  
  for (let i = 0; i < 10; i++) {
    const sessionData = {
      title: `Spike test session ${i}`,
      context_type: 'general',
    };
    
    sessionPromises.push(
      http.post(
        `${API_URL}/ai_consultation/sessions`,
        JSON.stringify(sessionData),
        authHeaders
      )
    );
  }
  
  // Wait briefly
  sleep(0.5);
  
  // Send messages to all sessions
  sessionPromises.forEach((res, i) => {
    if (res.status === 201) {
      const sessionId = res.json('session.id');
      
      http.post(
        `${API_URL}/ai_consultation/sessions/${sessionId}/messages`,
        JSON.stringify({ content: `Spike test message ${i}` }),
        authHeaders
      );
    }
  });
}