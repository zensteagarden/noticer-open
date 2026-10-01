import { sign, verify, generateKeyPairSync } from "node:crypto";

const version = process.version;
const { publicKey, privateKey } = generateKeyPairSync("ed25519");
const message = Buffer.from("doctor");
const signature = sign(null, message, privateKey);
const ok = verify(null, message, publicKey, signature);
console.log(`runtime ${version}`);
console.log(`ed25519 ${ok ? "ok" : "fail"}`);
console.log("cloud prerequisites are optional for the public verifier");
console.log("target runtime remains Node 24 LTS; this process is the available sandbox runtime");
if (!ok) process.exit(1);
