'use strict';
const http = require('node:http');
const { spawn } = require('node:child_process');

function status(port) {
  return new Promise((resolve, reject) => {
    const req = http.get({ hostname: '127.0.0.1', port, path: '/api/status', timeout: 1500 }, res => {
      let body = '';
      res.on('data', chunk => { body += chunk; if (body.length > 2e6) req.destroy(new Error('Response too large')); });
      res.on('end', () => {
        try {
          const data = JSON.parse(body);
          if (res.statusCode !== 200 || data.app !== 'wyndle' || data.protocol !== 1) {
            reject(new Error('This port is not running a compatible Wyndle dashboard.'));
          } else resolve(data);
        } catch { reject(new Error('The dashboard returned an invalid response.')); }
      });
      res.on('error', reject);
    });
    req.on('timeout', () => req.destroy(new Error('Wyndle did not respond in time.')));
    req.on('error', reject);
  });
}

class DashboardServer {
  constructor(output) { this.output = output; this.child = undefined; this.pending = undefined; }
  async connect(executable, port) {
    if (!Number.isInteger(port) || port < 1024 || port > 65535) throw new Error('Choose a port between 1024 and 65535 in Wyndle settings.');
    if (this.pending) return this.pending;
    this.pending = this.start(executable, port);
    try { return await this.pending; } finally { this.pending = undefined; }
  }
  async start(executable, port) {
    const url = `http://127.0.0.1:${port}`;
    try { await status(port); return url; } catch (error) {
      // Never launch over an unrelated HTTP service.
      if (error.code !== 'ECONNREFUSED') throw error;
    }
    this.dispose();
    const child = spawn(executable, ['ui', '--no-browser', '--port', String(port)], {
      shell: false, windowsHide: true,
    });
    this.child = child;
    let failure;
    let stderr = '';
    child.on('error', error => { failure = error; });
    child.on('exit', code => { failure = new Error(`Wyndle exited (${code}). ${stderr.trim()}`); });
    child.stdout.on('data', chunk => this.output.append(chunk.toString()));
    child.stderr.on('data', chunk => { stderr = (stderr + chunk.toString()).slice(-4000); this.output.append(chunk.toString()); });
    for (let attempt = 0; attempt < 40; attempt++) {
      if (failure) break;
      await new Promise(resolve => setTimeout(resolve, 250));
      try { await status(port); return url; } catch { /* Wait for startup. */ }
    }
    this.dispose();
    throw new Error(`Could not start Wyndle. Install the Python package and set wyndle.executable to its full path. ${failure?.message || stderr || 'Startup timed out.'}`);
  }
  dispose() { if (this.child) { this.child.kill(); this.child = undefined; } }
}
module.exports = { DashboardServer, status };
