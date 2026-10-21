from math import radians, sin, cos, atan2, sqrt


def haversine_meters(lat1, lon1, lat2, lon2):
    a = sin(radians(lat2 - lat1) / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * atan2(sqrt(min(1, a)), sqrt(max(0, 1 - a)))


def walking_minutes(distance_meters, speed_mps=1.4):
    if speed_mps <= 0:
        raise ValueError('Walking speed must be positive')
    return distance_meters / speed_mps / 60
