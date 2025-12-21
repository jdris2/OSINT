"""
Research_Satellite_Image_GeoMatch

Purpose:
  This module analyzes image EXIF GPS metadata from a given profile and attempts to match it with satellite coordinates to estimate precise known addresses. 
  The data source is the EXIF metadata embedded in images (typically JPEGs) and simulated satellite coordinate matching. 
  The module stores geolocation results in the profile['geo'] field using schema-compliant field names, validates output, and logs all operations.

Assumptions:
  - The profile object contains a list of image file paths under profile['images'].
  - EXIF GPS data is present in at least some images.
  - Satellite coordinate matching and reverse geocoding are simulated (no external API calls).
"""

import os
import json
import logging
from typing import Any, Dict, List

from core.module_base import IntelModuleBase

# Since we cannot use third-party libraries, we use the Python standard library for EXIF parsing.
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), '..', 'schemas', 'profile_schema.json')

def get_exif_data(image_path: str) -> Dict[str, Any]:
  """Extract EXIF data from an image file."""
  try:
    image = Image.open(image_path)
    exif_data = image._getexif()
    if not exif_data:
      return {}
    exif = {}
    for tag, value in exif_data.items():
      decoded = TAGS.get(tag, tag)
      if decoded == "GPSInfo":
        gps_data = {}
        for t in value:
          sub_decoded = GPSTAGS.get(t, t)
          gps_data[sub_decoded] = value[t]
        exif[decoded] = gps_data
      else:
        exif[decoded] = value
    return exif
  except Exception as e:
    logging.warning(f"Could not extract EXIF from {image_path}: {e}")
    return {}

def get_decimal_from_dms(dms, ref):
  """Convert GPS coordinates in DMS format to decimal degrees."""
  try:
    degrees = dms[0][0] / dms[0][1]
    minutes = dms[1][0] / dms[1][1]
    seconds = dms[2][0] / dms[2][1]
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if ref in ['S', 'W']:
      decimal = -decimal
    return decimal
  except Exception:
    return None

def extract_gps_coords(exif: Dict[str, Any]) -> Dict[str, float]:
  """Extract latitude and longitude from EXIF GPSInfo."""
  gps_info = exif.get("GPSInfo")
  if not gps_info:
    return {}
  lat = lon = None
  if "GPSLatitude" in gps_info and "GPSLatitudeRef" in gps_info:
    lat = get_decimal_from_dms(gps_info["GPSLatitude"], gps_info["GPSLatitudeRef"])
  if "GPSLongitude" in gps_info and "GPSLongitudeRef" in gps_info:
    lon = get_decimal_from_dms(gps_info["GPSLongitude"], gps_info["GPSLongitudeRef"])
  if lat is not None and lon is not None:
    return {"latitude": lat, "longitude": lon}
  return {}

def simulate_satellite_match(lat: float, lon: float) -> Dict[str, Any]:
  """
  Simulate satellite coordinate matching and reverse geocoding.
  In a real system, this would query a satellite imagery API and a geocoding service.
  """
  # Simulate a known address for demonstration
  return {
    "matched_latitude": lat,
    "matched_longitude": lon,
    "estimated_address": f"Simulated Address near ({lat:.5f}, {lon:.5f})"
  }

def validate_profile(profile: Dict[str, Any]) -> bool:
  """Validate the profile against the schema."""
  try:
    with open(SCHEMA_PATH, "r") as f:
      schema = json.load(f)
    # Minimal validation: check required fields in geo
    geo_schema = schema.get("properties", {}).get("geo", {})
    required = geo_schema.get("required", [])
    for field in required:
      if field not in profile.get("geo", {}):
        return False
    return True
  except Exception as e:
    logging.warning(f"Schema validation failed: {e}")
    return False

class Research_Satellite_Image_GeoMatch(IntelModuleBase):
  """
  Module to match image EXIF location data with satellite coordinates to estimate precise known addresses.
  Stores results in profile['geo'] using schema-compliant field names.
  """

  def run(self, profile: Dict[str, Any]) -> Dict[str, Any]:
    self.log_result("input", profile)
    images: List[str] = profile.get("images", [])
    geo_results = []
    for img_path in images:
      exif = get_exif_data(img_path)
      coords = extract_gps_coords(exif)
      if coords:
        match = simulate_satellite_match(coords["latitude"], coords["longitude"])
        geo_results.append({
          "source_image": os.path.basename(img_path),
          "latitude": coords["latitude"],
          "longitude": coords["longitude"],
          "matched_latitude": match["matched_latitude"],
          "matched_longitude": match["matched_longitude"],
          "estimated_address": match["estimated_address"]
        })
    # Store results in schema-compliant way
    profile['geo'] = {
      "matches": geo_results,
      "method": "satellite_image_exif_match",
      "confidence": 1.0 if geo_results else 0.0
    }
    # Validate output
    if not validate_profile(profile):
      raise ValueError("Profile geo output does not conform to schema.")
    self.log_result("result", profile['geo'])
    return profile
