'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { DashboardServer, status } = require('../server');

async function serve(t, data, code = 200) {
  const server = http.createServer((_req, res) => { res.writeHead(code); res.end(JSON.stringify(data)); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  return server.address().port;
}
test('attaches to a compatible running server without spawning a process', async t => {
  const port = await serve(t, { app: 'wyndle', protocol: 1 });
  const manager = new DashboardServer({ append() {} });
  assert.equal(await manager.connect('/nonexistent/executable', port), `http://127.0.0.1:${port}`);
  assert.equal(manager.child, undefined);
});
test('does not take over an unrelated service', async t => {
  const port = await serve(t, { app: 'something-else' });
  await assert.rejects(status(port), /compatible Wyndle/);
  const manager = new DashboardServer({ append() {} });
  await assert.rejects(manager.connect('wyndle', port), /compatible Wyndle/);
  assert.equal(manager.child, undefined);
});
test('rejects invalid ports before launching a command', async () => {
  const manager = new DashboardServer({ append() {} });
  await assert.rejects(manager.connect('wyndle', 0), /Choose a port/);
});
