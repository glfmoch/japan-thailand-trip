"""
parse_timeline.py

Parses a Google Maps Timeline JSON export into a pandas DataFrame
suitable for loading into the visits table.

Google exports Timeline data via Google Takeout:
  My Activity > Location History > Records.json (new format)
  or Semantic Location History/YYYY/YYYY_MONTH.json (legacy format)

TODO: fill in real parsing logic once the export is in data/raw/.
"""

import json
import pandas as pd
from pathlib import Path


def load_timeline_json(path: str | Path) -> dict:
    """Load the raw Timeline JSON file and return the parsed dict."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_place_visits(raw: dict) -> pd.DataFrame:
    """
    Extract placeVisit records from a legacy Semantic Location History JSON.

    Each placeVisit contains a location (name, lat/lon), a duration
    (startTimestamp, endTimestamp), and optional address metadata.

    Returns a DataFrame with columns:
        visit_id, city, country, location_name,
        latitude, longitude, arrival_datetime, departure_datetime, duration_hours
    """
    # TODO: implement once real export structure is confirmed
    raise NotImplementedError(
        "Fill in real parsing logic here. "
        "See README.md for the expected output schema."
    )


def parse_activity_segments(raw: dict) -> pd.DataFrame:
    """
    Extract activitySegment records (movement between places).

    Useful for computing transit time and transport mode (WALKING,
    IN_PASSENGER_VEHICLE, SUBWAY, etc.) between visits.

    Returns a DataFrame with columns:
        segment_id, start_datetime, end_datetime,
        start_lat, start_lon, end_lat, end_lon,
        distance_meters, activity_type
    """
    # TODO: implement once real export structure is confirmed
    raise NotImplementedError("Fill in real parsing logic here.")


def parse_new_format(raw: dict) -> pd.DataFrame:
    """
    Parse the newer Records.json format (single file, all points as a list
    of {latitudeE7, longitudeE7, timestamp, accuracy} objects).

    Useful as a fallback if Semantic History isn't available.
    """
    # TODO: implement once real export structure is confirmed
    raise NotImplementedError("Fill in real parsing logic here.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parse_timeline.py <path_to_timeline.json>")
        sys.exit(1)

    raw = load_timeline_json(sys.argv[1])
    df = parse_place_visits(raw)
    print(df.head())
