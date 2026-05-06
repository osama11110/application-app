"""Detect which ATS/career portal the browser has landed on."""

ATS_PATTERNS = {
    "greenhouse":       ["greenhouse.io", "boards.greenhouse.io"],
    "lever":            ["jobs.lever.co", "lever.co/"],
    "workday":          ["myworkdayjobs.com", "wd1.myworkday", "wd2.myworkday",
                         "wd3.myworkday", "wd5.myworkday", "myworkday.com"],
    "personio":         ["personio.de", "personio.com", "apply.personio"],
    "erecruiter":       ["erecruiter.net", "erecruiter.at"],
    "smartrecruiters":  ["smartrecruiters.com", "careers.smartrecruiters"],
    "softgarden":       ["softgarden.de", "softgarden.io"],
    "recruitee":        ["recruitee.com"],
    "taleo":            ["taleo.net", "oracle.taleo"],
    "icims":            ["icims.com"],
    "bamboohr":         ["bamboohr.com", "app.bamboohr"],
    "successfactors":   ["successfactors.com", "sapsf.com"],
    "breezy":           ["breezy.hr"],
    "jobvite":          ["jobvite.com"],
    "dvinci":           ["d.vinci.de", "dvinci.de"],
    "rexx":             ["rexx-systems.com", "rexx.com"],
    "umantis":          ["umantis.com", "haufe-umantis"],
    "talentsuite":      ["talentsuite.at", "talentsuite.de"],
}


def detect_ats(url: str) -> str:
    url_lower = url.lower()
    for ats_name, patterns in ATS_PATTERNS.items():
        if any(p in url_lower for p in patterns):
            return ats_name
    return "generic"


def is_external(original_domain: str, current_url: str) -> bool:
    """Returns True if current_url is on a different domain than original_domain."""
    return original_domain.lower() not in current_url.lower()
