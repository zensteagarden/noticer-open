// SPDX-License-Identifier: Apache-2.0
import { verifyPacket } from "./verify.mjs";

const CONTRACT_SCHEMA = "noticer.success-contract.v1";
const MAX_TEXT = 4096;
const PUBLIC_POLICIES = new Set(["packet.integrity.v1", "artifact.text.exact.v1"]);

function requirePlainObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value) || Object.getPrototypeOf(value) !== Object.prototype) {
    throw new TypeError(`${label} must be a plain object`);
  }
}

function cleanText(value, label) {
  if (typeof value !== "string") throw new TypeError(`${label} must be a string`);
  const text = value.trim();
  if (!text) throw new TypeError(`${label} must not be empty`);
  if (text.length > MAX_TEXT) throw new RangeError(`${label} exceeds ${MAX_TEXT} characters`);
  return text;
}

function cleanLimits(values) {
  if (!Array.isArray(values) || values.length === 0) {
    throw new TypeError("doesNotEstablish must contain at least one limitation");
  }
  if (values.length > 12) throw new RangeError("doesNotEstablish has too many items");
  return values.map((value, index) => cleanText(value, `doesNotEstablish[${index}]`));
}

function normalizeObservableCheck(value) {
  requirePlainObject(value, "observableCheck");
  const policyId = cleanText(value.policyId, "observableCheck.policyId");
  if (!PUBLIC_POLICIES.has(policyId)) {
    throw new TypeError(`unsupported public policy: ${policyId}`);
  }
  const statement = cleanText(value.statement, "observableCheck.statement");

  const out = {
    policy_id: policyId,
    statement,
  };

  if (policyId === "artifact.text.exact.v1") {
    out.expected_text = cleanText(value.expectedText, "observableCheck.expectedText");
  } else if (value.expectedText !== undefined) {
    throw new TypeError("expectedText is only valid for artifact.text.exact.v1");
  }

  return out;
}

export function createSuccessContract({ intention, requiredOutcome, observableCheck, doesNotEstablish }) {
  return {
    schema_version: CONTRACT_SCHEMA,
    status: "draft",
    intention: cleanText(intention, "intention"),
    required_outcome: cleanText(requiredOutcome, "requiredOutcome"),
    observable_proxy: normalizeObservableCheck(observableCheck),
    does_not_establish: cleanLimits(doesNotEstablish),
    authorization_note: "This success contract describes a check. It does not grant permission to access an account, mutate a system, spend money, or take an external action.",
  };
}

export function confirmSuccessContract(contract) {
  const normalized = validateSuccessContract(contract);
  return {
    ...normalized,
    status: "confirmed_by_user",
  };
}

export function validateSuccessContract(contract) {
  requirePlainObject(contract, "contract");
  if (contract.schema_version !== CONTRACT_SCHEMA) {
    throw new TypeError(`schema_version must be ${CONTRACT_SCHEMA}`);
  }
  if (!new Set(["draft", "confirmed_by_user"]).has(contract.status)) {
    throw new TypeError("status must be draft or confirmed_by_user");
  }

  const expectedKeys = new Set([
    "schema_version",
    "status",
    "intention",
    "required_outcome",
    "observable_proxy",
    "does_not_establish",
    "authorization_note",
  ]);
  for (const key of Object.keys(contract)) {
    if (!expectedKeys.has(key)) throw new TypeError(`unsupported success-contract field: ${key}`);
  }

  requirePlainObject(contract.observable_proxy, "observable_proxy");
  const observableInput = {
    policyId: contract.observable_proxy.policy_id,
    statement: contract.observable_proxy.statement,
  };
  if (Object.hasOwn(contract.observable_proxy, "expected_text")) {
    observableInput.expectedText = contract.observable_proxy.expected_text;
  }
  const observable = normalizeObservableCheck(observableInput);

  const authorizationNote = cleanText(contract.authorization_note, "authorization_note");
  const requiredAuthorizationNote = "This success contract describes a check. It does not grant permission to access an account, mutate a system, spend money, or take an external action.";
  if (authorizationNote !== requiredAuthorizationNote) {
    throw new TypeError("authorization_note must preserve the public authorization boundary");
  }

  return {
    schema_version: CONTRACT_SCHEMA,
    status: contract.status,
    intention: cleanText(contract.intention, "intention"),
    required_outcome: cleanText(contract.required_outcome, "required_outcome"),
    observable_proxy: observable,
    does_not_establish: cleanLimits(contract.does_not_establish),
    authorization_note: requiredAuthorizationNote,
  };
}

export function renderSuccessContract(contract) {
  const value = validateSuccessContract(contract);
  return [
    `Human intention: ${value.intention}`,
    `Required outcome: ${value.required_outcome}`,
    `Observable check: ${value.observable_proxy.statement}`,
    `Public policy: ${value.observable_proxy.policy_id}`,
    "This does not establish:",
    ...value.does_not_establish.map((item) => `- ${item}`),
    `Status: ${value.status}`,
    "Authorization: none granted by this contract.",
  ].join("\n");
}

export function verificationOptionsFromContract(contract) {
  const value = validateSuccessContract(contract);
  const options = {
    policyId: value.observable_proxy.policy_id,
  };
  if (Object.hasOwn(value.observable_proxy, "expected_text")) {
    options.expectedText = value.observable_proxy.expected_text;
  }
  return options;
}

export function verifyAgainstContract(loaded, contract) {
  return verifyPacket(loaded, verificationOptionsFromContract(contract));
}

export const SUCCESS_CONTRACT_SCHEMA_VERSION = CONTRACT_SCHEMA;
