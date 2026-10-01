import { LIMITS } from "./limits.mjs";

export function parseStrict(text) {
  if (typeof text !== "string" || !text.isWellFormed()) throw Object.assign(new Error("INVALID_UNICODE"), { code: "MALFORMED_PACKET" });
  const parser = new Parser(text);
  const value = parser.parseValue(0);
  parser.skipWs();
  if (!parser.eof()) throw Object.assign(new Error("TRAILING_INPUT"), { code: "MALFORMED_PACKET" });
  return value;
}

class Parser {
  constructor(text) {
    this.text = text;
    this.i = 0;
  }

  eof() {
    return this.i >= this.text.length;
  }

  peek() {
    return this.text[this.i];
  }

  skipWs() {
    while (this.i < this.text.length && " \t\r\n".includes(this.text[this.i])) this.i += 1;
  }

  parseValue(depth) {
    if (depth > LIMITS.max_depth) throw Object.assign(new Error("DEPTH"), { code: "LIMIT_EXCEEDED" });
    this.skipWs();
    const ch = this.peek();
    if (ch === "{") return this.parseObject(depth);
    if (ch === "[") return this.parseArray(depth);
    if (ch === '"') return this.parseString();
    if (ch === "t" || ch === "f") return this.parseLiteral();
    if (ch === "n") return this.parseNull();
    if (ch === "-" || (ch >= "0" && ch <= "9")) return this.parseNumber();
    throw Object.assign(new Error("UNEXPECTED"), { code: "MALFORMED_PACKET" });
  }

  parseObject(depth) {
    this.i += 1;
    const obj = {};
    const seen = new Set();
    this.skipWs();
    if (this.peek() === "}") {
      this.i += 1;
      return obj;
    }
    while (true) {
      this.skipWs();
      if (this.peek() !== '"') throw Object.assign(new Error("KEY"), { code: "MALFORMED_PACKET" });
      const key = this.parseString();
      if (seen.has(key)) throw Object.assign(new Error("DUPLICATE_KEY"), { code: "MALFORMED_PACKET" });
      seen.add(key);
      this.skipWs();
      if (this.peek() !== ":") throw Object.assign(new Error("COLON"), { code: "MALFORMED_PACKET" });
      this.i += 1;
      // __proto__ is a JSON member, never an inherited property setter.
      Object.defineProperty(obj, key, { value: this.parseValue(depth + 1), enumerable: true, writable: true, configurable: true });
      this.skipWs();
      if (this.peek() === ",") {
        this.i += 1;
        continue;
      }
      if (this.peek() === "}") {
        this.i += 1;
        return obj;
      }
      throw Object.assign(new Error("OBJECT_END"), { code: "MALFORMED_PACKET" });
    }
  }

  parseArray(depth) {
    this.i += 1;
    const arr = [];
    this.skipWs();
    if (this.peek() === "]") {
      this.i += 1;
      return arr;
    }
    while (true) {
      arr.push(this.parseValue(depth + 1));
      this.skipWs();
      if (this.peek() === ",") {
        this.i += 1;
        continue;
      }
      if (this.peek() === "]") {
        this.i += 1;
        return arr;
      }
      throw Object.assign(new Error("ARRAY_END"), { code: "MALFORMED_PACKET" });
    }
  }

  parseString() {
    this.i += 1;
    let out = "";
    while (!this.eof()) {
      const ch = this.text[this.i];
      if (ch === '"') {
        this.i += 1;
        if (!out.isWellFormed()) throw Object.assign(new Error("INVALID_UNICODE"), { code: "MALFORMED_PACKET" });
        if (out.length > LIMITS.max_string_chars) throw Object.assign(new Error("STRING"), { code: "LIMIT_EXCEEDED" });
        return out;
      }
      if (ch === "\\") {
        this.i += 1;
        const esc = this.text[this.i];
        const map = { '"': '"', "\\": "\\", "/": "/", b: "\b", f: "\f", n: "\n", r: "\r", t: "\t" };
        if (map[esc] !== undefined) {
          out += map[esc];
          this.i += 1;
          continue;
        }
        if (esc === "u") {
          const hex = this.text.slice(this.i + 1, this.i + 5);
          if (!/^[0-9a-fA-F]{4}$/.test(hex)) throw Object.assign(new Error("UNICODE"), { code: "MALFORMED_PACKET" });
          out += String.fromCharCode(Number.parseInt(hex, 16));
          this.i += 5;
          continue;
        }
        throw Object.assign(new Error("ESCAPE"), { code: "MALFORMED_PACKET" });
      }
      if (ch < " ") throw Object.assign(new Error("CONTROL"), { code: "MALFORMED_PACKET" });
      out += ch;
      this.i += 1;
    }
    throw Object.assign(new Error("STRING_END"), { code: "MALFORMED_PACKET" });
  }

  parseLiteral() {
    if (this.text.startsWith("true", this.i)) {
      this.i += 4;
      return true;
    }
    if (this.text.startsWith("false", this.i)) {
      this.i += 5;
      return false;
    }
    throw Object.assign(new Error("LITERAL"), { code: "MALFORMED_PACKET" });
  }

  parseNull() {
    if (this.text.startsWith("null", this.i)) {
      this.i += 4;
      return null;
    }
    throw Object.assign(new Error("NULL"), { code: "MALFORMED_PACKET" });
  }

  parseNumber() {
    const start = this.i;
    if (this.peek() === "-") this.i += 1;
    if (this.peek() === "0") this.i += 1;
    else if (this.peek() >= "1" && this.peek() <= "9") {
      while (this.peek() >= "0" && this.peek() <= "9") this.i += 1;
    } else throw Object.assign(new Error("NUMBER"), { code: "MALFORMED_PACKET" });
    if (this.peek() === "." || this.peek() === "e" || this.peek() === "E") {
      throw Object.assign(new Error("NON_SAFE_INTEGER"), { code: "MALFORMED_PACKET" });
    }
    const raw = this.text.slice(start, this.i);
    if (raw === "-0") throw Object.assign(new Error("NON_SAFE_INTEGER"), { code: "MALFORMED_PACKET" });
    const value = Number(raw);
    if (!Number.isSafeInteger(value)) throw Object.assign(new Error("NON_SAFE_INTEGER"), { code: "MALFORMED_PACKET" });
    return value;
  }
}
