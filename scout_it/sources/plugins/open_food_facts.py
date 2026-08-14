"""Open Food Facts — food products database. Free, no key.

API docs: https://wiki.openfoodfacts.org/API
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ..base import SourcePlugin, SourceConfig, make_result
from ..source_config import get_source_config
from ..async_fetch import sync_fetch_json

logger = logging.getLogger(__name__)

BASE_URL = "https://world.openfoodfacts.org/cgi/search.pl"


class OpenFoodFactsPlugin(SourcePlugin):
    name = "open_food_facts"
    display_name = "Open Food Facts"
    content_type = "knowledge"
    config = SourceConfig(
        name="open_food_facts",
        requires_api_key=False,
        rate_limit_per_sec=5.0,
        description="Food products database — nutrition, ingredients, allergens.",
    )

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Dict[str, Any]]:
        cfg = get_source_config("open_food_facts")
        url = cfg.get("base_url") or BASE_URL

        params = {
            "search_terms": query,
            "search_simple": 1,
            "action": "process",
            "json": 1,
            "page_size": min(max_results, 50),
        }

        data = sync_fetch_json(url, params=params, timeout=20)
        if not data or "products" not in data:
            return []

        results = []
        for product in data["products"][:max_results]:
            barcode = product.get("code", "")
            product_name = product.get("product_name", "") or product.get("generic_name", "")

            brands = product.get("brands", "")
            categories = product.get("categories", "")
            quantity = product.get("quantity", "")

            # Nutrition.
            nutriments = product.get("nutriments", {})
            energy = nutriments.get("energy-kcal_100g", nutriments.get("energy_100g", 0))
            fat = nutriments.get("fat_100g", 0)
            carbs = nutriments.get("carbohydrates_100g", 0)
            proteins = nutriments.get("proteins_100g", 0)

            ingredients = product.get("ingredients_text", "")
            if len(ingredients) > 300:
                ingredients = ingredients[:300] + "..."

            snippet_parts = []
            if brands:
                snippet_parts.append(f"Brand: {brands}")
            if quantity:
                snippet_parts.append(f"Quantity: {quantity}")
            if energy:
                snippet_parts.append(f"Energy: {energy} kcal/100g")
            snippet = " | ".join(snippet_parts)

            image_url = product.get("image_front_url", "") or product.get("image_url", "")
            url_val = f"https://world.openfoodfacts.org/product/{barcode}" if barcode else ""

            results.append(make_result(
                id=barcode or product_name,
                source="open_food_facts",
                url=url_val,
                title=product_name,
                snippet=snippet,
                content=ingredients,
                content_type="knowledge",
                timestamp="",
                authority_score=0.3,
                lang="en",
                metadata={
                    "barcode": barcode,
                    "brands": brands,
                    "categories": categories,
                    "quantity": quantity,
                    "ingredients": ingredients,
                    "nutrition": {
                        "energy_kcal": energy,
                        "fat_g": fat,
                        "carbs_g": carbs,
                        "proteins_g": proteins,
                    },
                    "image_url": image_url,
                    "nutriscore": product.get("nutriscore_grade", ""),
                    "nova_group": product.get("nova_group", ""),
                },
            ))
        return results


from ..registry import register
PLUGIN = OpenFoodFactsPlugin()
register(PLUGIN)
