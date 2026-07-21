import hashlib

from admin_portal.models import ProductImageCandidate


REPRESENTATION_PROFILES = (
    "a tall, slim adult Black woman with a poised natural stance",
    "a short, curvy adult Black woman with a confident natural stance",
    "a tall, curvy adult Black woman with a relaxed editorial stance",
    "a short, slim adult Black woman with a composed natural stance",
)

GLOBAL_DIRECTION = """Luxury African women's fashion ecommerce photography.
Portrait 3:4 composition, 768x1024 output.
Warm ivory premium studio, editorial but product-legible lighting.
If a person appears, depict one adult Black woman exclusively.
No white models, no men, no children, no celebrities or recognizable public figures.
No text, logo, watermark, price tag, collage, duplicated body parts, or unrelated product.
Show one coherent product design matching the supplied title, description, category, material, and colors."""

SHOT_DIRECTIONS = {
    ProductImageCandidate.ShotType.HERO: (
        "Create the primary catalog hero. For apparel, show the complete silhouette on-model. "
        "For accessories, keep the product dominant and use a model only when naturally appropriate."
    ),
    ProductImageCandidate.ShotType.ALTERNATE: (
        "Create an alternate angle or pose. Preserve exactly the same apparent product design, "
        "materials, construction, and colors as reference image 0."
    ),
    ProductImageCandidate.ShotType.DETAIL: (
        "Create a close product, material, or construction detail. Preserve exactly the same "
        "apparent product design and colors as reference image 0; do not force a full-body view."
    ),
}


def representation_profile(identifier: str) -> str:
    digest = hashlib.sha256(identifier.encode("utf-8")).digest()
    return REPRESENTATION_PROFILES[int.from_bytes(digest[:2], "big") % len(REPRESENTATION_PROFILES)]


def build_prompt(snapshot: dict, shot_type: str) -> str:
    identifier = str(snapshot.get("id") or snapshot.get("slug") or snapshot.get("name") or "product")
    colors = ", ".join(snapshot.get("colors", [])) or "use only colors supported by the description"
    category = str(snapshot.get("category", "fashion product"))
    person_direction = (
        f"When a model is appropriate, use {representation_profile(identifier)}."
    )
    product_context = (
        f"Product title: {snapshot.get('name', '')}. "
        f"Description: {snapshot.get('description', '')}. "
        f"Category: {category}. Material: {snapshot.get('material', '') or 'not specified'}. "
        f"Product colors: {colors}. Tags: {', '.join(snapshot.get('tags', []))}."
    )
    return "\n".join(
        [
            GLOBAL_DIRECTION,
            person_direction,
            product_context,
            SHOT_DIRECTIONS[shot_type],
        ]
    )


def deterministic_seed(identifier: str, shot_type: str) -> int:
    digest = hashlib.sha256(f"{identifier}:{shot_type}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)
