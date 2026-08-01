"""Offline data pipeline for the Japan & Thailand trip dashboard.

Modules:
    config    — shared paths, currency rates, category rules, geo windows
    spending  — parse the messy .docx spending log into a clean table
    timeline  — parse the Google Maps Timeline JSON into a movement route
    photos    — extract GPS + timestamp from photos and build thumbnails
    vision    — match each geotagged photo to a same-day purchase (Anthropic API)
"""
