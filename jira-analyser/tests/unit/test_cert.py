"""Tests for certificate generation."""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from jira_analyser.cert.generate import generate_self_signed_cert


def test_generates_cert_and_key(tmp_path: Path) -> None:
    cert_path, key_path = generate_self_signed_cert(out_dir=tmp_path)

    assert cert_path.exists()
    assert key_path.exists()


def test_cert_has_correct_cn(tmp_path: Path) -> None:
    cert_path, _ = generate_self_signed_cert(out_dir=tmp_path, common_name="test.example.com")

    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    cn = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
    assert cn == "test.example.com"


def test_raises_on_existing_files(tmp_path: Path) -> None:
    generate_self_signed_cert(out_dir=tmp_path)
    with pytest.raises(FileExistsError):
        generate_self_signed_cert(out_dir=tmp_path)


def test_overwrite_replaces_files(tmp_path: Path) -> None:
    generate_self_signed_cert(out_dir=tmp_path)
    cert_path, _ = generate_self_signed_cert(out_dir=tmp_path, overwrite=True)
    assert cert_path.exists()


def test_private_key_is_valid_rsa(tmp_path: Path) -> None:
    _, key_path = generate_self_signed_cert(out_dir=tmp_path)
    key = load_pem_private_key(key_path.read_bytes(), password=None)
    assert key.key_size == 2048
