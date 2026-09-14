import {test} from 'node:test';
import assert from 'node:assert/strict';
import {Api, ApiError, EventFeed, graphData, counterInterval, riskStyle} from '../../src/netsentinel/api/static/core.mjs';

const ok = json => ({ok: true, status: 200, json: async () => json});
test('login obtains public CSRF first, preserves cookies and rotates token before mutations', async () => {
  const calls = [];
  const api = new Api(async (path, options) => {
    calls.push({path, options});
    if (path.endsWith('/csrf')) return ok({csrf_token: 'before'});
    if (path.endsWith('/login')) return ok({csrf_token: 'after', operator: 'operador'});
    return ok({});
  });
  await api.login('operador', 'test-only');
  await api.request('/api/devices/mac/reputation', 'POST', {known: true, reason: 'Reconhecido'});
  assert.deepEqual(calls.map(c => c.path), ['/api/auth/csrf', '/api/auth/login', '/api/devices/mac/reputation']);
  assert.equal(calls[1].options.headers['X-CSRF-Token'], 'before');
  assert.equal(calls[2].options.headers['X-CSRF-Token'], 'after');
  assert(calls.every(c => c.options.credentials === 'same-origin' && c.options.cache === 'no-store'));
});
test('CSRF failure prevents credentials from being sent', async () => {
  const paths = [];
  const api = new Api(async p => { paths.push(p); return {ok: false, status: 503, json: async () => ({error: 'unavailable'})}; });
  await assert.rejects(api.login('u', 'secret'), ApiError);
  assert.deepEqual(paths, ['/api/auth/csrf']);
});
test('WebSocket future ID never skips missed REST events; replay is deduplicated', async () => {
  const accepted = [], feed = new EventFeed(e => accepted.push(e.event_id));
  feed.ingest({event_id: 7});
  const api = {request: async path => { assert(path.includes('after_id=0')); return {events: [1,2,3,4,5,6,7].map(event_id => ({event_id}))}; }};
  await feed.replay(api);
  assert.deepEqual(accepted, [7,1,2,3,4,5,6]);
  assert.equal(feed.cursor, 7);
  assert.deepEqual(feed.newest().map(e => e.event_id), [7,6,5,4,3,2,1]);
});
test('replay fetches all pages and bounds rendered history to 200', async () => {
  const feed = new EventFeed(() => {}); let calls = 0;
  await feed.replay({request: async path => {
    calls++;
    if (calls === 1) return {events: Array.from({length: 500}, (_,i) => ({event_id: i+1}))};
    assert(path.includes('after_id=500')); return {events: [{event_id: 501}]};
  }});
  assert.equal(calls, 2); assert.equal(feed.cursor, 501); assert.equal(feed.items.size, 200);
  assert.equal(feed.newest().at(-1).event_id, 302);
});
test('logout while fetching prevents old replay from repopulating the new session', async () => {
  const feed = new EventFeed(() => {}); let active = true;
  await feed.replay({request: async () => { active = false; return {events: [{event_id: 1}]}; }}, () => active);
  assert.equal(feed.items.size, 0); assert.equal(feed.cursor, 0);
});
test('graph distinguishes a destination-only MAC and broadcast from judged devices', () => {
  const data = graphData({nodes: [{mac: 'aa', risk: {score: 82.38, classification: 'suspeito'}}],
    links: [{source: 'aa', target: 'ff:ff:ff:ff:ff:ff', packets: 30}, {source: 'aa', target: 'bb', packets: 1}]});
  assert.equal(data.nodes.length, 3);
  assert(data.nodes[0].label.includes('suspeito'));
  assert(data.nodes[1].label.includes('Broadcast'));
  assert(data.nodes[2].label.includes('Destino observado'));
  assert.equal(data.edges[0].to, 'ff:ff:ff:ff:ff:ff');
  assert.equal(riskStyle({score: null, classification: null}).label, 'Sem avaliação');
});
const reading = (n = 0, changes = {}) => ({run_id: 'agent-1', attacker_mac: 'aa', timestamp: n+1,
  mitigated: true, blocked: true, arp_static_correct: true,
  counters: {seen: {packets: n}, dropped: {packets: n}, passed: {packets: 0}}, ...changes});
test('counter evidence shows active drops and zero post-filter delivery, never verifies ping', () => {
  const result = counterInterval(reading(), reading(10));
  assert.equal(result.comparable, true);
  assert.deepEqual(result.deltas, {seen: 10, dropped: 10, passed: 0});
  assert(result.reason.includes('Ping exige verificação separada'));
});
test('silent segment, counter reset, changed agent and absent readings cannot look like proof', () => {
  assert(counterInterval(reading(), reading(0, {timestamp: 2})).reason.includes('não prova bloqueio'));
  assert.equal(counterInterval(reading(10), reading(2, {timestamp: 20})).comparable, false);
  assert.equal(counterInterval(reading(), reading(10, {run_id: 'new'})).comparable, false);
  assert.equal(counterInterval(null, reading()).comparable, false);
  assert.equal(counterInterval(reading(), reading(10, {simulated: true})).comparable, false);
});
test('delivery after filtering and unconfirmed static ARP remain explicit failures of evidence', () => {
  const passed = reading(10); passed.counters.passed.packets = 2;
  assert(counterInterval(reading(), passed).reason.includes('Houve pacotes entregues'));
  assert(counterInterval(reading(), reading(10, {arp_static_correct: false})).reason.includes('não confirmam'));
});
