const test = require('node:test');
const assert = require('node:assert');
const request = require('supertest');
const app = require('../server');

test('GET /health returns ok', async () => {
  const res = await request(app).get('/health');
  assert.strictEqual(res.status, 200);
  assert.strictEqual(res.body.status, 'ok');
});

test('GET /orders returns a list', async () => {
  const res = await request(app).get('/orders');
  assert.strictEqual(res.status, 200);
  assert.ok(Array.isArray(res.body));
});
