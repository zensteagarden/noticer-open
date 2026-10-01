import { readdirSync, lstatSync, openSync, fstatSync, readSync, closeSync, constants } from 'node:fs';
import { join, resolve } from 'node:path';
import { digestOf, canonicalBytes, sha256Hex } from './canonical.mjs';
import { parseStrict } from './parse.mjs';
import { LIMITS } from './limits.mjs';

const BLOB_NAME=/^sha256-[0-9a-f]{64}$/;
const ATTESTATION_NAME=/^[A-Za-z0-9_-][A-Za-z0-9._-]{0,127}\.json$/;
const ID=/^[A-Za-z0-9._-]{1,128}$/;
const error=(code='MALFORMED_PACKET')=>Object.assign(new Error(code),{code});
const object=value=>value!==null && typeof value==='object' && !Array.isArray(value);

// Snapshot each file through one opened handle, with preallocation bounded by
// policy. Directory ancestors must remain exclusively controlled by the caller;
// Node does not provide portable openat confinement against hostile parent swaps.
export function readBoundedFile(path, maxBytes) {
  const before=lstatSync(path);
  if (!before.isFile() || before.isSymbolicLink() || before.nlink>1) throw error();
  if (before.size>maxBytes) throw error('LIMIT_EXCEEDED');
  const fd=openSync(path,constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0) | (constants.O_NONBLOCK ?? 0));
  try {
    const opened=fstatSync(fd);
    if (!opened.isFile() || opened.nlink>1 || opened.ino!==before.ino || opened.dev!==before.dev) throw error();
    const bytes=Buffer.alloc(Math.min(opened.size,maxBytes)+1);
    let size=0, count;
    while (size<bytes.length && (count=readSync(fd,bytes,size,bytes.length-size,null))>0) size+=count;
    const after=fstatSync(fd);
    if (size>maxBytes || after.size>maxBytes) throw error('LIMIT_EXCEEDED');
    if (size!==opened.size || after.size!==opened.size || after.mtimeMs!==opened.mtimeMs || after.ctimeMs!==opened.ctimeMs) throw error();
    return bytes.subarray(0,size);
  } finally { closeSync(fd); }
}

export function decodeJson(bytes) {
  // ignoreBOM:true preserves the BOM character so the strict parser rejects it.
  return parseStrict(new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes));
}

function directory(path, optional=false) {
  let st;
  try { st=lstatSync(path); } catch(e) { if (optional && e.code==='ENOENT') return []; throw e; }
  if (st.isSymbolicLink() || !st.isDirectory()) throw error();
  return readdirSync(path).sort();
}

// Version 0.1's narrow implemented contract. Public schema generation remains a
// separate release gate; validation here must not claim unsupported adjudication.
export function validateManifest(m) {
  if (!object(m)) throw error();
  const allowed=new Set(['schema_version','observations','evidence','claims','obligations','extensions','adjudication','verdict']);
  if (Object.keys(m).some(k=>!allowed.has(k)) || (m.extensions!==undefined && !object(m.extensions))) throw error();
  for (const name of ['observations','evidence','claims','obligations']) {
    if (!Array.isArray(m[name]) || m[name].length>200) throw error();
  }
  for (const [list,key] of [['observations','observation_id'],['evidence','evidence_id'],['claims','claim_id'],['obligations','obligation_id']]) {
    const ids=new Set();
    for (const item of m[list]) {
      if (!object(item) || !ID.test(item[key] ?? '') || ids.has(item[key])) throw error();
      ids.add(item[key]);
    }
  }
  for (const item of m.evidence) {
    if (!ID.test(item.observation_id ?? '') || !/^sha256:[0-9a-f]{64}$/.test(item.digest ?? '') || !Number.isSafeInteger(item.byte_length) || item.byte_length<0 || typeof item.media_type!=='string') throw error();
  }
  for (const claim of m.claims) {
    if (typeof claim.predicate!=='string' || !object(claim.parameters) || !Array.isArray(claim.evidence_refs) || claim.evidence_refs.some(ref=>typeof ref!=='string' || !ID.test(ref))) throw error();
    if (claim.predicate==='text.exact.v1' && (typeof claim.parameters.expected!=='string' || claim.evidence_refs.length!==1)) throw error();
  }
}

export function loadPacket(root) {
  try {
    const packetRoot=resolve(root);
    const top=directory(packetRoot);
    if (top.some(name=>!['manifest.json','blobs','attestations','README.md'].includes(name))) throw error();
    const raw=readBoundedFile(join(packetRoot,'manifest.json'),LIMITS.max_manifest_bytes);
    const manifest=decodeJson(raw);
    if (!object(manifest) || typeof manifest.schema_version!=='string') throw error();
    if (manifest.schema_version!=='0.1') return {ok:false,code:'UNSUPPORTED_SCHEMA'};
    validateManifest(manifest);
    const blobs=new Map(), attestations=[];
    // The shipped sample has an inert README; it is not verification evidence.
    const readme=top.includes('README.md') ? readBoundedFile(join(packetRoot,'README.md'),LIMITS.max_manifest_bytes) : Buffer.alloc(0);
    let packetBytes=raw.length+readme.length, files=1+(top.includes('README.md')?1:0);
    for (const [folder,pattern,limit] of [['blobs',BLOB_NAME,LIMITS.max_blob_bytes],['attestations',ATTESTATION_NAME,LIMITS.max_attestation_bytes]]) {
      const names=directory(join(packetRoot,folder),true);
      files+=names.length;
      if (files>LIMITS.max_files) throw error('LIMIT_EXCEEDED');
      for (const name of names) {
        if (!pattern.test(name)) throw error();
        const bytes=readBoundedFile(join(packetRoot,folder,name),Math.min(limit,LIMITS.max_packet_bytes-packetBytes));
        packetBytes+=bytes.length;
        if (folder==='blobs') {
          const expected=name.slice('sha256-'.length);
          if (sha256Hex(bytes)!==expected) throw error('DIGEST_MISMATCH');
          if (!manifest.evidence.some(e=>e.digest===`sha256:${expected}`)) throw error();
          blobs.set(`sha256:${expected}`,bytes);
        } else attestations.push({name,value:decodeJson(bytes),raw_length:bytes.length});
      }
    }
    return {ok:true,manifest,blobs,attestations,manifestDigest:digestOf(canonicalBytes(manifest))};
  } catch(e) { return {ok:false,code:['LIMIT_EXCEEDED','DIGEST_MISMATCH'].includes(e.code)?e.code:'MALFORMED_PACKET'}; }
}
