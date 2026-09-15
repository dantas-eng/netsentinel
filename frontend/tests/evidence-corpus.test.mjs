import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {counterInterval} from '../../src/netsentinel/api/static/core.mjs';

const url = new URL('../../tests/fixtures/evidence_cases.json', import.meta.url);
const payload = JSON.parse(await readFile(url, 'utf8'));

test('shared evidence corpus matches counterInterval reason_code', () => {
  assert.ok(payload.cases.length >= 10);
  for (const fixture of payload.cases) {
    const result = counterInterval(fixture.before, fixture.after);
    assert.equal(result.reason_code, fixture.expected.reason_code, fixture.name);
    assert.equal(typeof result.reason === 'string' || result.reason == null, true, fixture.name);
    if (fixture.expected.verified) {
      assert.equal(result.comparable, true, fixture.name);
    }
  }
});
