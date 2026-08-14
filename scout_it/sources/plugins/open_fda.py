"""Open FDA — open data from the US FDA. Free, no key (key optional for higher limits).

API docs: https://open.fda.gov/data/api/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://api.fda.gov/drug/event.json"


class OpenFdaPlugin(SourcePlugin):
    name = "open_fda"
    display_name = "openFDA"
    content_type = "knowledge"
    config = SourceConfig(
        name="open_fda",
        requires_api_key=False,
        rate_limit_per_sec=4.0,
        description="US FDA open data — drug adverse events, recalls, device data.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("open_fda")
        url = cfg.get("base_url") or BASE_URL

        # openFDA uses search=some_field:"term" syntax.
        params = {
            "search": f'patient.drug.medicinalproduct:"{query}"+patient.reaction.reactionmeddrapt:"{query}"',
            "limit": min(max_results, 100),
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data:
            return []

        # openFDA returns {"meta":..., "results":[...]} or {"error":...} if no results.
        if "error" in data or "results" not in data:
            return []

        results = []
        for event in data["results"][:max_results]:
            safety_id = str(event.get("safetyreportid", ""))
            patient = event.get("patient", {})

            # Drugs.
            drugs = patient.get("drug", [])
            drug_names = []
            for d in drugs[:3]:
                name = d.get("medicinalproduct", "")
                if name:
                    drug_names.append(name)

            # Reactions.
            reactions = patient.get("reaction", [])
            reaction_terms = [r.get("reactionmeddrapt", "") for r in reactions[:5] if r.get("reactionmeddrapt")]

            received_date = event.get("receivedate", "")
            patient_age = patient.get("patientonsetage", "")
            patient_sex = patient.get("patientsex", "")

            sex_map = {"0": "unknown", "1": "male", "2": "female", 0: "unknown", 1: "male", 2: "female"}
            sex_str = sex_map.get(patient_sex, "unknown")

            snippet_parts = []
            if drug_names:
                snippet_parts.append(f"Drugs: {', '.join(drug_names[:3])}")
            if reaction_terms:
                snippet_parts.append(f"Reactions: {', '.join(reaction_terms[:3])}")
            if patient_age:
                snippet_parts.append(f"Age: {patient_age}")
            snippet_parts.append(f"Sex: {sex_str}")
            snippet = " | ".join(snippet_parts)

            results.append(make_result(
                id=safety_id,
                source="open_fda",
                url=f"https://open.fda.gov/data/faers/",
                title=f"FDA Adverse Event: {', '.join(drug_names[:2]) or query}",
                snippet=snippet,
                content="",
                content_type="knowledge",
                timestamp=received_date,
                authority_score=0.6,
                lang="en",
                metadata={
                    "safety_report_id": safety_id,
                    "drugs": drug_names,
                    "reactions": reaction_terms,
                    "received_date": received_date,
                    "patient_age": patient_age,
                    "patient_sex": sex_str,
                    "serious": event.get("serious", ""),
                    "country": event.get("occurcountry", ""),
                },
            ))
        return results


from ..registry import register
PLUGIN = OpenFdaPlugin()
register(PLUGIN)
