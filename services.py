EARTH_RADIUS = 1.0
EARTH_TEMP_K = 255.0

HABITABLE_TEMP_MIN = 180
HABITABLE_TEMP_MAX = 310
ROCKY_RADIUS_MAX = 1.6


def calculate_similarity(radius_earth: float, temperature_k: float) -> float:
    """
    Índice de similitud con la Tierra, de 0 a 1.
    Compara radio y temperatura contra los valores terrestres.
    """
    if radius_earth is None or temperature_k is None:
        return 0.0

    radius_score = 1 - abs(radius_earth - EARTH_RADIUS) / (radius_earth + EARTH_RADIUS)
    temp_score = 1 - abs(temperature_k - EARTH_TEMP_K) / (temperature_k + EARTH_TEMP_K)

    similarity = (radius_score * temp_score) ** 0.5
    return round(similarity, 3)


def classify_planet(radius_earth: float, temperature_k: float) -> str:
    """
    Clasifica el planeta según su tamaño y temperatura.
    """
    if radius_earth is None or temperature_k is None:
        return "unknown"

    if radius_earth > 6:
        return "gas_giant"
    if radius_earth > ROCKY_RADIUS_MAX:
        return "mini_neptune"

    if HABITABLE_TEMP_MIN <= temperature_k <= HABITABLE_TEMP_MAX:
        return "potentially_habitable"
    if temperature_k > HABITABLE_TEMP_MAX:
        return "too_hot"
    return "too_cold"