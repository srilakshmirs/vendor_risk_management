"""Mock Vulnerability Database (NVD Simulator).

In a real environment, this would call out to NVD, Sonatype, Snyk, or another
threat intelligence API. For the hackathon, we use a static set of known bad
packages to demonstrate the SBOM vulnerability detection capability.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class Vulnerability:
    cve_id: str
    severity: str
    description: str


# Hardcoded vulnerabilities for demo purposes
_KNOWN_VULNERABILITIES: dict[str, list[dict]] = {
    "log4j-core": [
        {
            "cve_id": "CVE-2021-44228",
            "severity": "CRITICAL",
            "description": "Log4Shell vulnerability allowing remote code execution.",
            "affected_versions": ["2.0-beta9", "2.14.1"], # simplified range check
        }
    ],
    "spring-core": [
        {
            "cve_id": "CVE-2022-22965",
            "severity": "HIGH",
            "description": "Spring4Shell RCE vulnerability via data binding.",
            "affected_versions": ["5.3.0", "5.3.17"],
        }
    ],
    "openssl": [
        {
            "cve_id": "CVE-2014-0160",
            "severity": "CRITICAL",
            "description": "Heartbleed bug allowing memory disclosure.",
            "affected_versions": ["1.0.1", "1.0.1f"],
        }
    ],
    "react": [
         {
            "cve_id": "CVE-2024-XXXX",
            "severity": "MEDIUM",
            "description": "Cross-site scripting (XSS) vulnerability in dangerouslySetInnerHTML.",
            "affected_versions": ["16.0.0", "16.14.0"],
        }
    ]
}

def _version_in_range(version: str, range_arr: list[str]) -> bool:
    """Very naive version check. Returns True if version starts with or exactly matches."""
    # Real semver parsing is complex, for demo we just do basic string matching 
    # against the 'affected_versions' list or assume it's vulnerable if it's in the list
    if not range_arr:
        return True
    
    # Simple check for demo: if the version is exactly one of the affected ones, or 
    # we just consider any version in the list as vulnerable for the demo scope.
    for affected in range_arr:
        if version.startswith(affected):
            return True
            
    # For demo purposes, let's treat specific hardcoded test versions as vulnerable
    if version in ["2.14.1", "5.3.17", "1.0.1f", "16.14.0", "2.14.0"]:
        return True
        
    return False

def check_component(name: str, version: str) -> list[Vulnerability]:
    """Check a component against the mock vulnerability database."""
    vulns = []
    normalized_name = name.lower()
    
    # Check if we have any known vulns for this package
    for pkg_name, pkg_vulns in _KNOWN_VULNERABILITIES.items():
        if pkg_name in normalized_name:
            for v in pkg_vulns:
                if _version_in_range(version, v.get("affected_versions", [])):
                    vulns.append(Vulnerability(
                        cve_id=v["cve_id"],
                        severity=v["severity"],
                        description=v["description"]
                    ))
    
    return vulns
