#!/usr/bin/env bash
#
# Generate a VAPID key pair for Web Push.
#
# Output format matches what pywebpush expects: bgmon hands
# VAPID_PRIVATE_KEY straight to pywebpush, which forwards it to
# py_vapid.Vapid.from_string(). That base64url-decodes the string and treats a
# 32-byte result as the raw private key, so these are base64url values, not
# PEM, with the padding stripped.
#
# The pair is derived by `cryptography` rather than by slicing DER bytes with
# `tail -c`. That idiom is common but wrong here: in a PKCS8 wrapper the private
# key sits at a fixed offset ahead of an embedded public key, so `tail -c 32`
# silently returns the tail of the public key. The result parses without error
# and signs with a key that does not match VAPID_PUBLIC_KEY, which breaks push
# delivery only at runtime.
#
# Usage:
#   ./scripts/generate-vapid-keys.sh            # print the .env lines
#   ./scripts/generate-vapid-keys.sh --write    # also write them into .env
#
set -euo pipefail

write_to_env=false
if [[ "${1:-}" == "--write" ]]; then
  write_to_env=true
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Prefer the project venv, where cryptography is installed via pywebpush.
python_bin=""
for candidate in "$repo_root/backend/.venv/bin/python" python3; do
  if command -v "$candidate" >/dev/null 2>&1 && \
     "$candidate" -c "import cryptography" >/dev/null 2>&1; then
    python_bin="$candidate"
    break
  fi
done

if [[ -z "$python_bin" ]]; then
  echo "error: need python3 with the 'cryptography' package" >&2
  echo "       run this from the project venv, or: pip install cryptography" >&2
  exit 1
fi

keys="$("$python_bin" - <<'PY'
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

key = ec.generate_private_key(ec.SECP256R1())


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


private_raw = key.private_numbers().private_value.to_bytes(32, "big")
public_raw = key.public_key().public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint,
)

# Self-check: the published pair must actually belong together, so re-derive
# the public key from the private one and compare before printing anything.
rederived = (
    ec.derive_private_key(int.from_bytes(private_raw, "big"), ec.SECP256R1())
    .public_key()
    .public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
)
if rederived != public_raw or len(public_raw) != 65 or len(private_raw) != 32:
    raise SystemExit("internal error: generated key pair is inconsistent")

print(b64url(public_raw))
print(b64url(private_raw))
PY
)"

public_key="$(printf '%s\n' "$keys" | sed -n 1p)"
private_key="$(printf '%s\n' "$keys" | sed -n 2p)"

echo "Add these to your .env:"
echo
echo "VAPID_PUBLIC_KEY=$public_key"
echo "VAPID_PRIVATE_KEY=$private_key"
echo

if [[ "$write_to_env" == true ]]; then
  env_file="$repo_root/.env"
  if [[ ! -f "$env_file" ]]; then
    echo "error: $env_file not found; create it from .env.example first" >&2
    exit 1
  fi
  # Replace rather than append: dotenv resolves duplicates by taking whichever
  # line comes last, so a second VAPID_PRIVATE_KEY would silently win.
  sed -i.bak -e "/^VAPID_PUBLIC_KEY=/d" -e "/^VAPID_PRIVATE_KEY=/d" "$env_file"
  rm -f "$env_file.bak"
  {
    echo "VAPID_PUBLIC_KEY=$public_key"
    echo "VAPID_PRIVATE_KEY=$private_key"
  } >>"$env_file"
  echo "Wrote VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY to $env_file"
fi

echo "Shown once. Losing these keys invalidates every existing browser push"
echo "subscription; users then have to re-subscribe."