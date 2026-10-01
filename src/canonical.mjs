import { createHash } from "node:crypto";

const CONTROL = new Set([0x08, 0x09, 0x0a, 0x0c, 0x0d]);

export function sha256Hex(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

export function digestOf(bytes) {
  return `sha256:${sha256Hex(bytes)}`;
}

function escapeString(value) {
  if (!value.isWellFormed()) throw new Error("INVALID_UNICODE");
  let out = '"';
  for (const ch of value) {
    const code = ch.codePointAt(0);
    if (ch === '"') out += '\\"';
    else if (ch === "\\") out += "\\\\";
    else if (code === 0x08) out += "\\b";
    else if (code === 0x09) out += "\\t";
    else if (code === 0x0a) out += "\\n";
    else if (code === 0x0c) out += "\\f";
    else if (code === 0x0d) out += "\\r";
    else if (code < 0x20) out += `\\u${code.toString(16).padStart(4, "0")}`;
    else out += ch;
  }
  return `${out}"`;
}

function compareKeys(a, b) {
  const al = a.length;
  const bl = b.length;
  const n = Math.min(al, bl);
  for (let i = 0; i < n; i += 1) {
    const d = a.charCodeAt(i) - b.charCodeAt(i);
    if (d !== 0) return d;
  }
  return al - bl;
}

export function canonicalize(value) {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value) || Object.is(value, -0)) {
      throw new Error("NON_SAFE_INTEGER");
    }
    return String(value);
  }
  if (typeof value === "string") return escapeString(value);
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalize(item)).join(",")}]`;
  }
  if (typeof value === "object") {
    const keys = Object.keys(value).sort(compareKeys);
    return `{${keys.map((key) => `${escapeString(key)}:${canonicalize(value[key])}`).join(",")}}`;
  }
  throw new Error("UNSUPPORTED_VALUE");
}

export function canonicalBytes(value) {
  return Buffer.from(canonicalize(value), "utf8");
}

export function evaluationDigest(evaluation) {
  const copy = { ...evaluation };
  delete copy.evaluation_digest;
  delete copy.runtime_identity;
  return digestOf(canonicalBytes(copy));
}

export { CONTROL };
