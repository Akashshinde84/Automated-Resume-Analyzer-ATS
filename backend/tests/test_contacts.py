import pytest

from app.services.extraction.contacts import extract_contacts


@pytest.mark.parametrize("raw,e164", [
    ("+44 20 7946 0018", "+442079460018"),
    ("+1 650 253 0000", "+16502530000"),
    ("+91 98765 43210", "+919876543210"),
    ("+33 1 42 68 53 00", "+33142685300"),
])
def test_international_phone_numbers(raw, e164):
    contacts, _ = extract_contacts(f"Phone: {raw}", None)
    assert contacts["phones"][0].e164 == e164


def test_national_phone_region_required():
    contacts, warnings = extract_contacts("Phone: 020 7946 0018", None)
    assert contacts["phones"][0].e164 is None
    assert contacts["phones"][0].status == "ambiguous"
    assert warnings
    contacts, _ = extract_contacts("Phone: 020 7946 0018", "GB")
    assert contacts["phones"][0].e164 == "+442079460018"


def test_phone_extension_and_invalid_number():
    contacts, _ = extract_contacts("Tel: +1 650 253 0000 ext. 123", None)
    assert contacts["phones"][0].extension == "123"
    assert contacts["phones"][0].e164 == "+16502530000"
    contacts, _ = extract_contacts("Phone: +999 123456789", None)
    assert contacts["phones"][0].e164 is None
    assert contacts["phones"][0].status == "invalid"


def test_dates_ids_not_treated_as_phones():
    contacts, _ = extract_contacts("2019 - 2023\nCandidate ID: 1234567890\nhttps://example.test/1234567890", None)
    assert contacts["phones"] == []


def test_contacts_deduplicate_and_respect_url_host():
    contacts, _ = extract_contacts("""jane+work@Example.test jane+work@Example.test
linkedin.com/in/jane
https://linkedin.com/in/jane
https://linkedin.com.evil.test/in/jane
https://github.com/jane
Website: https://jane.example.test
https://other-company.example.test
""", None)
    assert contacts["emails"] == ["jane+work@example.test"]
    assert contacts["linkedin_urls"] == ["https://linkedin.com/in/jane"]
    assert contacts["github_urls"] == ["https://github.com/jane"]
    assert contacts["portfolio_urls"] == ["https://jane.example.test"]


def test_inline_contacts():
    contacts, _ = extract_contacts("jane@example.test | Phone: +44 20 7946 0018", None)
    assert contacts["emails"] == ["jane@example.test"]
    assert contacts["phones"][0].e164 == "+442079460018"
