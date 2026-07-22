import hashlib

from admin_portal.models import ProductImageCandidate


PROMPT_POLICY_V1 = "v1-automatic"
PROMPT_POLICY_V2 = "v2-controlled-variety"

SHOT_ORDER = (
    ProductImageCandidate.ShotType.HERO,
    ProductImageCandidate.ShotType.ALTERNATE,
    ProductImageCandidate.ShotType.DETAIL,
)

REPRESENTATION_PROFILES = (
    {
        "bodyProfile": "slim",
        "skinTone": "light_brown",
        "stature": "tall",
        "identity": "angular oval face with high cheekbones",
        "hair": "shoulder-length natural twists",
        "pose": "poised natural stance",
    },
    {
        "bodyProfile": "curvy",
        "skinTone": "deep_brown",
        "stature": "short",
        "identity": "soft round face with full cheeks",
        "hair": "short natural coils",
        "pose": "confident relaxed stance",
    },
    {
        "bodyProfile": "athletic",
        "skinTone": "medium_brown",
        "stature": "medium-height",
        "identity": "long face with a defined jawline",
        "hair": "high braided bun",
        "pose": "grounded editorial stance",
    },
    {
        "bodyProfile": "curvy",
        "skinTone": "dark_brown",
        "stature": "tall",
        "identity": "heart-shaped face with broad cheekbones",
        "hair": "long neat box braids",
        "pose": "graceful upright stance",
    },
    {
        "bodyProfile": "slim",
        "skinTone": "deep_brown",
        "stature": "petite",
        "identity": "square face with a softly defined jaw",
        "hair": "close-cropped natural hair",
        "pose": "composed natural stance",
    },
    {
        "bodyProfile": "athletic",
        "skinTone": "light_brown",
        "stature": "short",
        "identity": "oval face with a broad forehead",
        "hair": "rounded natural afro",
        "pose": "easy dynamic stance",
    },
    {
        "bodyProfile": "curvy",
        "skinTone": "medium_brown",
        "stature": "petite",
        "identity": "diamond-shaped face with a narrow chin",
        "hair": "side-parted natural locs",
        "pose": "warm self-assured stance",
    },
    {
        "bodyProfile": "slim",
        "skinTone": "dark_brown",
        "stature": "medium-height",
        "identity": "broad oval face with a strong brow",
        "hair": "low braided ponytail",
        "pose": "refined three-quarter stance",
    },
)

COMPOSITION_DIRECTIONS = {
    "automatic": "a product-legible ecommerce composition",
    "standing": "a standing ecommerce composition",
    "seated": "a seated ecommerce composition that keeps the product fully legible",
    "walking": "a natural walking composition with the product sharply legible",
    "three_quarter": "a three-quarter ecommerce composition",
}

DETAIL_DIRECTIONS = {
    "automatic": "the most informative product construction detail",
    "fabric": "the fabric texture and material quality",
    "pattern": "the print or pattern alignment and clarity",
    "stitching": "the stitching and seam finish",
    "closure": "the closure hardware and fastening construction",
    "construction": "the garment or accessory construction",
}

GLOBAL_DIRECTION = """Luxury African women's fashion ecommerce photography.
Portrait 3:4 composition, 768x1024 output.
Warm ivory premium studio, editorial but product-legible lighting."""

FINAL_GUARDRAILS = """FINAL IMMUTABLE REQUIREMENTS:
Use only the described product design and the assigned real catalog color; do not add, remove, or redesign product features.
Any person shown must be one adult Black woman. Never show a white or non-Black model, a man, a child, a celebrity, or a recognizable public figure.
No unsafe or sexualized content. No text, logo, watermark, price tag, collage, duplicated body parts, or unrelated product.
The structured directions above override any conflicting creative direction."""

DETAIL_FINAL_GUARDRAILS = """FINAL IMMUTABLE REQUIREMENTS:
This is a product-only image. Show no person, face, hands, limbs, skin, mannequin body parts, or other body parts.
Use only the described product design and the assigned real catalog color; do not add, remove, or redesign product features.
No unsafe content. No text, logo, watermark, price tag, collage, or unrelated product.
The structured directions above override any conflicting creative direction."""


def _stable_index(value: str, length: int) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % length


def representation_profile(identifier: str, shot_type: str = "hero") -> dict[str, str]:
    offset = 0 if shot_type == ProductImageCandidate.ShotType.HERO else 1
    index = (_stable_index(f"{identifier}:representation", len(REPRESENTATION_PROFILES)) + offset) % len(
        REPRESENTATION_PROFILES
    )
    return dict(REPRESENTATION_PROFILES[index])


def rotated_catalog_colors(snapshot: dict, revision: int = 0) -> list[str]:
    colors = list(dict.fromkeys(str(color).strip() for color in snapshot.get("colors", []) if str(color).strip()))
    if not colors:
        return []
    identifier = str(snapshot.get("id") or snapshot.get("slug") or snapshot.get("name") or "product")
    start = _stable_index(f"{identifier}:colors:{revision}", len(colors))
    return colors[start:] + colors[:start]


def allocate_colors(
    snapshot: dict,
    requested: dict[str, str | None],
    *,
    revision: int = 0,
    reserved: dict[str, str] | None = None,
) -> dict[str, str | None]:
    colors = rotated_catalog_colors(snapshot, revision)
    assignments: dict[str, str | None] = dict(reserved or {})
    for shot_type in SHOT_ORDER:
        selected = requested.get(shot_type)
        if selected:
            assignments[shot_type] = selected
    if not colors:
        for shot_type in SHOT_ORDER:
            assignments.setdefault(shot_type, None)
        return assignments

    used = [color for color in assignments.values() if color]
    for shot_type in SHOT_ORDER:
        if shot_type in assignments:
            continue
        unused = next((color for color in colors if color not in used), None)
        selected = unused or colors[len(used) % len(colors)]
        assignments[shot_type] = selected
        used.append(selected)
    return assignments


def resolve_shot_overrides(
    snapshot: dict,
    requested_by_shot: dict[str, dict],
    *,
    revisions: dict[str, int] | None = None,
    reserved_colors: dict[str, str] | None = None,
) -> dict[str, dict]:
    revisions = revisions or {}
    color_revision = max(revisions.values(), default=0)
    colors = allocate_colors(
        snapshot,
        {shot: values.get("color") for shot, values in requested_by_shot.items()},
        revision=color_revision,
        reserved=reserved_colors,
    )
    identifier = str(snapshot.get("id") or snapshot.get("slug") or snapshot.get("name") or "product")
    resolved: dict[str, dict] = {}
    for shot_type, requested in requested_by_shot.items():
        normalized = dict(requested)
        normalized.setdefault("color", None)
        normalized.setdefault("instruction", "")
        if shot_type == ProductImageCandidate.ShotType.DETAIL:
            normalized.setdefault("detailFocus", "automatic")
            resolved[shot_type] = {
                "requested": normalized,
                "resolved": {
                    "color": colors.get(shot_type),
                    "detailFocus": normalized["detailFocus"],
                },
            }
            continue

        normalized.setdefault("bodyProfile", "automatic")
        normalized.setdefault("skinTone", "automatic")
        normalized.setdefault("composition", "automatic")
        profile = representation_profile(identifier, shot_type)
        body_profile = normalized["bodyProfile"]
        skin_tone = normalized["skinTone"]
        if body_profile != "automatic":
            profile["bodyProfile"] = body_profile
        if skin_tone != "automatic":
            profile["skinTone"] = skin_tone
        profile["composition"] = normalized["composition"]
        profile["color"] = colors.get(shot_type)
        resolved[shot_type] = {"requested": normalized, "resolved": profile}
    return resolved


def _humanize(value: str) -> str:
    return value.replace("_", "-")


def build_prompt(
    snapshot: dict,
    shot_type: str,
    overrides: dict | None = None,
    *,
    policy_version: str = PROMPT_POLICY_V2,
) -> str:
    if overrides is None:
        overrides = resolve_shot_overrides(snapshot, {shot_type: {}})[shot_type]
    requested = overrides.get("requested", {})
    resolved = overrides.get("resolved", {})
    assigned_color = resolved.get("color")
    color_direction = (
        f"Assigned product color: {assigned_color}. Use this color exactly."
        if assigned_color
        else "No variant color is available; use only colors supported by the frozen description or product reference."
    )
    product_context = (
        f"Product title: {snapshot.get('name', '')}. "
        f"Description: {snapshot.get('description', '')}. "
        f"Category: {snapshot.get('category', 'fashion product')}. "
        f"Material: {snapshot.get('material', '') or 'not specified'}. "
        f"Tags: {', '.join(snapshot.get('tags', []))}."
    )
    if shot_type == ProductImageCandidate.ShotType.DETAIL:
        shot_direction = (
            "Create a product-only ecommerce detail photograph of the item on a clean studio surface. "
            "Use reference image 0 only for product-design fidelity; do not crop so tightly that the product becomes abstract. "
            f"Emphasize {DETAIL_DIRECTIONS[resolved.get('detailFocus', 'automatic')]}. "
            "For accessories, show a natural close view of hardware, texture, strap, closure, edge finish, or construction. "
            "Recolor only to the assigned catalog color where applicable."
        )
        final_guardrails = DETAIL_FINAL_GUARDRAILS
    else:
        model_direction = (
            f"Depict a {_humanize(resolved.get('skinTone', 'medium_brown'))}-skinned adult Black woman with a "
            f"{resolved.get('bodyProfile', 'slim')} build and {resolved.get('stature', 'medium-height')} stature, "
            f"{resolved.get('identity', 'distinct natural facial features')}, and {resolved.get('hair', 'natural hair')}. "
            f"Use {COMPOSITION_DIRECTIONS[resolved.get('composition', 'automatic')]} and a "
            f"{resolved.get('pose', 'natural stance')}."
        )
        if shot_type == ProductImageCandidate.ShotType.HERO:
            shot_direction = (
                "Create the primary catalog hero. For apparel, show the complete silhouette on-model. "
                "For accessories, keep the product dominant while retaining the assigned model direction."
            )
        else:
            shot_direction = (
                "Create an alternate catalog image using reference image 0 only for garment construction. "
                "Show a clearly different person from Hero, with the assigned face, hair, skin tone, body profile, "
                "pose, color, and framing. Show the item being worn from a meaningfully different product angle "
                "than Hero, prioritizing a back view or rear three-quarter view when the product has visible back "
                "construction; otherwise use a side profile or turned view that reveals fit, drape, strap placement, "
                "closure, hem, and silhouette details not visible in the front hero. Preserve the product design exactly."
            )
        shot_direction = f"{shot_direction}\n{model_direction}"
        final_guardrails = FINAL_GUARDRAILS

    manual_direction = requested.get("instruction", "")
    manual_section = (
        f"Lower-priority owner creative direction: {manual_direction}"
        if manual_direction
        else "Lower-priority owner creative direction: none."
    )
    return "\n".join(
        [
            f"Prompt policy: {policy_version}.",
            GLOBAL_DIRECTION,
            product_context,
            color_direction,
            shot_direction,
            manual_section,
            final_guardrails,
        ]
    )


def deterministic_seed(identifier: str, shot_type: str, revision: int = 0) -> int:
    digest = hashlib.sha256(
        f"{identifier}:{shot_type}:{PROMPT_POLICY_V2}:{revision}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)
