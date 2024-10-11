#!/usr/bin/python3
#Script that checks if .id is present and if it matches the file name.
import json
import os
import pathlib
import sys
import xml.etree.ElementTree as ET

def reportMissing(pure_path):
    print(f"Resource {pure_path} has no .id")

def reportMismatch(pure_path):
    print(f"Resource id doesn't match the file name in {pure_path}")

def extract_filename_without_resource_type(stem):
    if '-' in stem:
        return stem.split('-', 1)[1]  # Split on first occurrence of '-' and return the part after the resource type
    return stem

if __name__ == "__main__":
    success = True

    for file_path in sys.argv[1:]:
        if os.environ.get("debug", "0") != "0":
            print(f"Checking file {file_path}")
        pure_path = pathlib.PurePath(file_path)

        if pure_path.suffix.lower() == ".json":
            root = json.load(open(file_path))
            if "id" not in root:
                reportMissing(pure_path)
                success = False
            else:
                file_stem = pure_path.stem
                expected_id_without_type = extract_filename_without_resource_type(file_stem)
                
                # First check if the id matches the full filename (with resource type)
                if root["id"] == file_stem:
                    continue  # No mismatch, move to next file
                # Then check if the id matches the filename without the resource type
                elif root["id"] != expected_id_without_type:
                    reportMismatch(pure_path)
                    success = False

        elif pure_path.suffix.lower() == ".xml":
            root = ET.fromstring(open(pure_path).read())
            id_elem = root.find("{http://hl7.org/fhir}id")
            if id_elem is None:
                reportMissing(pure_path)
                success = False
            else:
                file_stem = pure_path.stem
                expected_id_without_type = extract_filename_without_resource_type(file_stem)
                
                # First check if the id matches the full filename (with resource type)
                if id_elem.attrib.get("value") == file_stem:
                    continue  # No mismatch, move to next file
                # Then check if the id matches the filename without the resource type
                elif id_elem.attrib.get("value") != expected_id_without_type:
                    reportMismatch(pure_path)
                    success = False

    if not success:
        print("\nSome invalid resources were found!")
        sys.exit(1)
    else:
        print("No problems found")