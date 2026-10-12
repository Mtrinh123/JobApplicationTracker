"""Run with: python test_parse.py"""
from main import check_password, hash_password, parse_posting


def page(title="", **meta):
    tags = "".join(f'<meta property="{k.replace("_", ":", 1)}" content="{v}">' for k, v in meta.items())
    return f"<html><head><title>{title}</title>{tags}</head></html>"


cases = [
    (page("Software Engineer at Acme | LinkedIn"), "Acme", "Software Engineer"),
    (page("Acme hiring Data Analyst in Raleigh, NC | LinkedIn"), "Acme", "Data Analyst in Raleigh, NC"),
    (page(og_title="Job Application for Backend Intern at Globex"), "Globex", "Backend Intern"),
    (page("Product Designer - Initech"), "Initech", "Product Designer"),
    (page("Frontend Developer – Hooli"), "Hooli", "Frontend Developer"),
    (page("Careers", og_site_name="Umbrella"), "Umbrella", "Careers"),
    (page(""), "", ""),
]

for html, company, role in cases:
    got = parse_posting(html)
    assert got == {"company": company, "role": role}, (html, got)

stored = hash_password("correct horse")
assert check_password("correct horse", stored)
assert not check_password("wrong horse", stored)
assert hash_password("correct horse") != stored, "salt should differ each time"

print(f"{len(cases)} parse cases and password checks passed")
