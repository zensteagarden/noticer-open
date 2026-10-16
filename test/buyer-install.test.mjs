// Primary buyer docs must agree with the released connector, not GitHub Latest.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const read = p => readFileSync(new URL(`../${p}`, import.meta.url), 'utf8');
const version = '0.3.2-dev.20261016';
const digest = 'cc34e591327b60362923f895b710ccc43264317a01b9dfc0c1dbd3393390d7fb';
const registry = JSON.parse(read('mcp-commercial/server.json'));
const url = `https://github.com/zensteagarden/noticer-open/releases/download/noticer-commercial-mcp-v${version}/noticer-commercial-mcp-${version}.mcpb`;

test('current Registry source pins the published buyer artifact and runtime', () => {
  assert.equal(registry.name, 'io.github.zensteagarden/noticer');
  assert.equal(registry.version, version);
  assert.equal(registry.repository.subfolder, `mcp-commercial/${version}`);
  assert.equal(registry.packages.length, 1);
  const pkg = registry.packages[0];
  assert.equal(pkg.version, version);
  assert.equal(pkg.identifier, url);
  assert.equal(pkg.fileSha256, digest);
  assert.equal(pkg.transport.type, 'stdio');
  assert.equal(JSON.parse(read(`mcp-commercial/${version}/manifest.json`)).version, version);
});
for (const path of ['README.md', 'mcp-commercial/AGENT_GUIDE.md']) {
  test(`${path}: download, checksum and launch stay on the same release`, () => {
    const doc = read(path);
    assert.ok(doc.includes(`VER=${version}`));
    assert.ok(doc.includes(`${digest}  noticer-commercial-mcp-$VER.mcpb`));
    assert.ok(doc.includes('releases/download/noticer-commercial-mcp-v$VER/noticer-commercial-mcp-$VER.mcpb'));
    assert.ok(doc.includes(`versions/${version}`));
    assert.ok(doc.includes('set -eu\nVER='), 'stop on download/checksum failure');
    assert.ok(doc.includes('uv run --frozen --quiet --directory'));
    assert.doesNotMatch(doc, /0\.3\.[01](?:-dev(?:\.\d+)?)?/);
    assert.doesNotMatch(doc, /https:\/\/github\.com\/[^\s)"<>]+\/releases\/latest/);
    assert.doesNotMatch(doc, /versions\/latest/);
  });
}
test('host config path and documented server identity match installed version', () => {
  const doc = read('mcp-commercial/AGENT_GUIDE.md');
  const configs = [...doc.matchAll(/```json\n([\s\S]*?)\n```/g)].map(m => JSON.parse(m[1]));
  const cfg = configs.find(x => x.mcpServers)?.mcpServers.noticer;
  assert.equal(cfg.command, 'uv');
  assert.deepEqual(cfg.args, ['run','--frozen','--quiet','--directory',`/home/YOU/.local/share/noticer-mcp/${version}`,'sales_mcp.py']);
  assert.equal(cfg.env.NOTICER_COMMERCIAL_CONFIG_FILE, '');
  assert.ok(doc.includes('server identity `noticer` / `'+version+'`'));
  assert.ok(doc.includes('${XDG_STATE_HOME:-$HOME/.local/state}/noticer/config.json'));
  assert.ok(read('README.md').includes('noticer-mcp-v0.1.0'), 'preserve separate legacy connector');
});
