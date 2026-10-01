export const LIMITS_VERSION = "limits.v1";

export const LIMITS = {
  version: LIMITS_VERSION,
  max_manifest_bytes: 1048576,
  max_packet_bytes: 26214400,
  max_blob_bytes: 10485760,
  max_attestation_bytes: 1048576,
  max_files: 100,
  max_depth: 32,
  max_string_chars: 1000000,
};
