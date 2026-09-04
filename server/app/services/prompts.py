from typing import Optional


def _build_description(height_cm: Optional[int], weight_kg: Optional[int]) -> str:
    if not height_cm or not weight_kg or height_cm <= 0 or weight_kg <= 0:
        return ""
    bmi = weight_kg / ((height_cm / 100.0) ** 2)
    if bmi < 18.5:
        build = "slim, lean"
    elif bmi < 25:
        build = "average, normal"
    elif bmi < 30:
        build = "full, robust"
    else:
        build = "heavy, broad"
    return (
        f"The person has a {build} build (height about {height_cm} cm, weight about {weight_kg} kg). "
        "Reflect this body type accurately in the shoulders, neck and upper chest — "
        "do not slim down or enlarge the body. "
    )


def build_headshot_prompt(
    scene_text: str,
    height_cm: Optional[int] = None,
    weight_kg: Optional[int] = None,
) -> str:
    body = _build_description(height_cm, weight_kg)
    return (
        f"{scene_text} "
        "Framing: proper head-and-shoulders portrait, head takes about one third of the frame, "
        "shoulders and upper chest clearly visible, natural anatomical proportion between head "
        "and body (do NOT make the head oversized or the body tiny). "
        f"{body}"
        "Keep the face and head identical to the input photo."
    )
