"""Certificate generation utilities.

Generates a self-signed X.509 certificate + private key pair and writes them
to PEM files.  Typically used in dev/test environments or when a custom CA
certificate is needed for mTLS with an on-prem Jira instance.

Usage (standalone):
    python -m jira_analyser.cert.generate --out-dir certs/

Usage (as library):
    from jira_analyser.cert.generate import generate_self_signed_cert
    cert_path, key_path = generate_self_signed_cert(out_dir=Path("certs"))
"""

from __future__ import annotations

import datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from jira_analyser.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_KEY_SIZE = 2048
_PUBLIC_EXPONENT = 65537
_VALIDITY_DAYS = 825  # ~27 months, Apple/Chrome limit
_DEFAULT_COUNTRY = "US"
_DEFAULT_ORG = "jira-analyser"
_DEFAULT_CN = "localhost"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_self_signed_cert(
    *,
    out_dir: Path = Path("certs"),
    common_name: str = _DEFAULT_CN,
    organisation: str = _DEFAULT_ORG,
    country: str = _DEFAULT_COUNTRY,
    validity_days: int = _VALIDITY_DAYS,
    cert_filename: str = "cert.pem",
    key_filename: str = "key.pem",
    overwrite: bool = False,
) -> tuple[Path, Path]:
    """Generate a self-signed RSA certificate and private key.

    Args:
        out_dir:        Directory where PEM files will be written.
        common_name:    CN field for the certificate subject / SAN.
        organisation:   O field for the certificate subject.
        country:        C field (two-letter ISO code).
        validity_days:  Certificate lifetime in days.
        cert_filename:  Output filename for the certificate.
        key_filename:   Output filename for the private key.
        overwrite:      If False, raise FileExistsError when files already exist.

    Returns:
        Tuple of (cert_path, key_path).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cert_path = out_dir / cert_filename
    key_path = out_dir / key_filename

    if not overwrite:
        for p in (cert_path, key_path):
            if p.exists():
                raise FileExistsError(
                    f"{p} already exists. Pass overwrite=True to replace it."
                )

    # ── 1. Private key ────────────────────────────────────────────────────────
    logger.info("Generating RSA-%d private key …", _KEY_SIZE)
    private_key = rsa.generate_private_key(
        public_exponent=_PUBLIC_EXPONENT,
        key_size=_KEY_SIZE,
    )

    # ── 2. Certificate ────────────────────────────────────────────────────────
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organisation),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )

    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=validity_days))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(common_name)]),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .sign(private_key, hashes.SHA256())
    )

    # ── 3. Write PEM files ────────────────────────────────────────────────────
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    logger.info("Certificate written → %s", cert_path)

    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    logger.info("Private key written  → %s", key_path)

    return cert_path, key_path


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate a self-signed TLS certificate.")
    parser.add_argument("--out-dir", default="certs", help="Output directory (default: certs/)")
    parser.add_argument("--cn", default=_DEFAULT_CN, help="Common name / hostname")
    parser.add_argument("--org", default=_DEFAULT_ORG, help="Organisation name")
    parser.add_argument("--country", default=_DEFAULT_COUNTRY, help="Two-letter country code")
    parser.add_argument("--days", type=int, default=_VALIDITY_DAYS, help="Validity in days")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    generate_self_signed_cert(
        out_dir=Path(args.out_dir),
        common_name=args.cn,
        organisation=args.org,
        country=args.country,
        validity_days=args.days,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    _cli()
