import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, symlinkSync, unlinkSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { digestOf, canonicalize } from '../src/canonical.mjs';
import { parseStrict } from '../src/parse.mjs';
import { loadPacket } from '../src/packet.mjs';
import { verifyPacket } from '../src/verify.mjs';

function fixture(t) {
  const root=mkdtempSync(join(tmpdir(),'noticer-boundary-'));
  t.after(()=>rmSync(root,{recursive:true,force:true}));
  const packet=join(root,'packet'); mkdirSync(packet); mkdirSync(join(packet,'blobs'));
  const bytes=Buffer.from('ok'), digest=digestOf(bytes);
  const manifest={schema_version:'0.1',observations:[{observation_id:'o'}],evidence:[{evidence_id:'e',observation_id:'o',digest,byte_length:2,media_type:'text/plain'}],claims:[],obligations:[]};
  const save=()=>writeFileSync(join(packet,'manifest.json'),JSON.stringify(manifest)); save();
  writeFileSync(join(packet,'blobs',digest.replace(':','-')),bytes);
  return {root,packet,manifest,save};
}
test('JSON prototype names remain inert committed properties',()=>{
  const value=parseStrict('{"__proto__":{"owned":true}}');
  assert.equal(Object.getPrototypeOf(value),Object.prototype);
  assert.equal(Object.hasOwn(value,'__proto__'),true);
  assert.equal(value.owned,undefined);
  assert.equal(canonicalize(value),'{"__proto__":{"owned":true}}');
});
test('escaped aliases, unpaired surrogates and negative zero reject',()=>{
  for(const input of ['{"a":1,"\\u0061":2}','"\\ud800"','"\\udc00"','-0']) assert.throws(()=>parseStrict(input));
  assert.equal(parseStrict('"\\ud83d\\ude00"'),'😀');
  assert.throws(()=>canonicalize('\ud800'));
});
test('malformed UTF-8 manifest is not replacement-decoded into a valid packet',t=>{
  const f=fixture(t); const raw=Buffer.from(JSON.stringify(f.manifest));
  const at=raw.indexOf(Buffer.from('text/plain'));raw[at]=0xff;
  writeFileSync(join(f.packet,'manifest.json'),raw);
  assert.equal(loadPacket(f.packet).ok,false);
});
test('manifest and blob-directory symlinks are refused',t=>{
  const f=fixture(t);
  writeFileSync(join(f.root,'outside.json'),JSON.stringify(f.manifest));
  unlinkSync(join(f.packet,'manifest.json'));
  symlinkSync(join(f.root,'outside.json'),join(f.packet,'manifest.json'));
  assert.equal(loadPacket(f.packet).ok,false);
  unlinkSync(join(f.packet,'manifest.json'));f.save();
  rmSync(join(f.packet,'blobs'),{recursive:true});mkdirSync(join(f.root,'outside'));
  symlinkSync(join(f.root,'outside'),join(f.packet,'blobs'),'dir');
  assert.equal(loadPacket(f.packet).ok,false);
});
test('missing required arrays, duplicate observations and false lengths cannot ALLOW',t=>{
  const f=fixture(t);
  delete f.manifest.claims;f.save();
  assert.equal(verifyPacket(loadPacket(f.packet)).verdict,'DENY');
  f.manifest.claims=[];f.manifest.observations.push({observation_id:'o'});f.save();
  assert.equal(verifyPacket(loadPacket(f.packet)).verdict,'DENY');
  f.manifest.observations.pop();f.manifest.evidence[0].byte_length=9;f.save();
  assert.equal(verifyPacket(loadPacket(f.packet)).verdict,'DENY');
});
test('undeclared blobs cannot be accepted as part of an integrity packet',t=>{
  const f=fixture(t);const bytes=Buffer.from('unlisted');
  writeFileSync(join(f.packet,'blobs',digestOf(bytes).replace(':','-')),bytes);
  assert.equal(loadPacket(f.packet).ok,false);
});
