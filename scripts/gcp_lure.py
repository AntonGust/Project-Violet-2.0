"""Handle GCP service account credential sanitize/restore in dev_workstation.json.

This is a companion to restore_lure_secrets.sh for multi-line JSON blobs
that sed cannot handle reliably.

Usage:
    python scripts/gcp_lure.py --sanitize
    python scripts/gcp_lure.py --restore
"""
import json
import sys
from pathlib import Path

FILE = Path(__file__).resolve().parent.parent / "Reconfigurator" / "profiles" / "dev_workstation.json"
KEY = "/home/jsmith/.config/gcloud/application_default_credentials.json"
PLACEHOLDER = "HONEYPOT_LURE_GCP_APPLICATION_DEFAULT_CREDENTIALS"

REAL_VALUE = json.dumps({
    "type": "service_account",
    "project_id": "acme-staging-294017",
    "private_key_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
    "private_key": (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEpAIBAAKCAQEA2a3B4c5D6e7F8g9H0i1J2k3L4m5N6o7P8q9R0s1T2u3V4w5X\n"
        "6y7Z8a9B0c1D2e3F4g5H6i7J8k9L0m1N2o3P4q5R6s7T8u9V0w1X2y3Z4a5B6c7D\n"
        "8e9F0g1H2i3J4k5L6m7N8o9P0q1R2s3T4u5V6w7X8y9Z0a1B2c3D4e5F6g7H8i9J\n"
        "0k1L2m3N4o5P6q7R8s9T0u1V2w3X4y5Z6a7B8c9D0e1F2g3H4i5J6k7L8m9N0o1P\n"
        "2q3R4s5T6u7V8w9X0y1Z2a3B4c5D6e7F8g9H0i1J2k3L4m5N6o7P8q9R0s1T2u3V\n"
        "AgMBAAECggEAFq4b5Rk3mN7oP8qR0sT1uV2wX3yZ4aB5cD6eF7gH8iJ9kL0mN1oP\n"
        "2qR3sT4uV5wX6yZ7aB8cD9eF0gH1iJ2kL3mN4oP5qR6sT7uV8wX9yZ0aB1cD2eF3\n"
        "gH4iJ5kL6mN7oP8qR9sT0uV1wX2yZ3aB4cD5eF6gH7iJ8kL9mN0oP1qR2sT3uV4w\n"
        "-----END RSA PRIVATE KEY-----\n"
    ),
    "client_email": "dev-sa@acme-staging-294017.iam.gserviceaccount.com",
    "client_id": "109876543210987654321",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/dev-sa%40acme-staging-294017.iam.gserviceaccount.com"
}, indent=2)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("--sanitize", "--restore"):
        print("Usage: python scripts/gcp_lure.py --sanitize|--restore")
        sys.exit(1)

    if not FILE.exists():
        print(f"  skip: {FILE} not found")
        return

    text = FILE.read_text()
    mode = sys.argv[1]

    if mode == "--sanitize":
        if PLACEHOLDER in text:
            return  # already sanitized
        if REAL_VALUE not in text and "service_account" in text:
            # The JSON blob may have been inlined differently; try key-based detection
            # Read as raw text and replace the value for the gcloud key
            pass
        text = text.replace(REAL_VALUE, PLACEHOLDER)
        FILE.write_text(text)
        print(f"  sanitized: {FILE.name} (GCP service account)")
    else:
        if PLACEHOLDER not in text:
            return  # already restored
        text = text.replace(PLACEHOLDER, REAL_VALUE)
        FILE.write_text(text)
        print(f"  restored:  {FILE.name} (GCP service account)")


if __name__ == "__main__":
    main()
