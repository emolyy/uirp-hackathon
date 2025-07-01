import os
import json
from datetime import datetime, timedelta
import random
import csv # Import the csv module
import math

# --- Constants for Component Lifespans and Probability Tuning ---
COMPONENT_LIFESPANS = {
    "engine_system": 10000.0,
    "transmission_drive_system": 12000.0,
    "hydraulic_system": 10000.0,
    "fuel_system": 8000.0,
    "cooling_system": 7500.0,
    "electrical_system": 7000.0,
    "air_system": 10000.0,
    "processing_cleaning_system": 4000.0,
    "auger_unloading_system": 5000.0,
    "sensor_vision_system": 6000.0,
    "chassis_structural": 12000.0,
    "def_system": 6000.0
}

# Probability tuning factors
PROB_SCALING_FACTOR = 0.0005
PROB_EXPONENT = 2.5
BASE_FAILURE_PROB_PER_HOUR = 0.000002

# --- Helper Function: load_all_monthly_data (unchanged) ---
def load_all_monthly_data(folder_path):
    all_tractor_data = {}

    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            filepath = os.path.join(folder_path, filename)
            try:
                with open(filepath, 'r') as f:
                    month_data = json.load(f)

                tractor_id = month_data.get("tractor_id")
                monthly_records = month_data.get("monthly_telemetry_records", [])
                tractor_specifications = month_data.get("tractor_specifications", {})

                if tractor_id:
                    if tractor_id not in all_tractor_data:
                        all_tractor_data[tractor_id] = {
                            "tractor_id": tractor_id,
                            "tractor_specifications": tractor_specifications,
                            "monthly_telemetry_records": []
                        }
                    all_tractor_data[tractor_id]["monthly_telemetry_records"].extend(monthly_records)
                else:
                    print(f"Warning: '{filename}' does not contain 'tractor_id'. Skipping.")

            except json.JSONDecodeError:
                print(f"Error: Could not decode JSON from '{filename}'. Skipping.")
            except Exception as e:
                print(f"An unexpected error occurred while processing '{filename}': {e}")

    for tractor_id, data in all_tractor_data.items():
        if data["monthly_telemetry_records"] and "timestamp" in data["monthly_telemetry_records"][0]:
            data["monthly_telemetry_records"].sort(key=lambda x: datetime.strptime(x["timestamp"], "%Y-%m-%dT%H:%M:%SZ"))

    return all_tractor_data


# --- Simulation Function: simulate_failures (Modified for CSV output structure) ---
def simulate_failures(tractor_data):
    tractor_id = tractor_data["tractor_id"]
    specs = tractor_data.get("tractor_specifications", {})
    monthly_records = tractor_data.get("monthly_telemetry_records", [])

    # Instead of a nested structure, directly collect failure rows for CSV
    # Each item in this list will be a dictionary representing one row in the CSV
    failures_for_csv = []

    random.seed(f"sim_{tractor_id}_seed")

    component_status = {}
    initial_hours_at_purchase = specs.get("hours_at_purchase", 0.0)

    for component_name in COMPONENT_LIFESPANS.keys():
        component_status[component_name] = {
            "hours_since_last_repair": initial_hours_at_purchase,
            "failed": False
        }

    previous_record_hours = initial_hours_at_purchase

    for record_idx, record in enumerate(monthly_records):
        current_operating_hours = record.get("current_operating_hours")
        timestamp_str = record.get("timestamp")

        if current_operating_hours is None or timestamp_str is None:
            continue

        hours_delta = current_operating_hours - previous_record_hours
        if hours_delta < 0:
            hours_delta = 0

        if hours_delta == 0:
            continue

        previous_record_hours = current_operating_hours

        for component_name, lifespan_hours in COMPONENT_LIFESPANS.items():
            comp_state = component_status[component_name]

            if comp_state["failed"]:
                continue

            comp_state["hours_since_last_repair"] += hours_delta
            ratio_to_lifespan = comp_state["hours_since_last_repair"] / lifespan_hours

            wear_based_prob = (max(0.001, ratio_to_lifespan) ** PROB_EXPONENT) * PROB_SCALING_FACTOR * hours_delta
            current_failure_prob = wear_based_prob + (BASE_FAILURE_PROB_PER_HOUR * hours_delta)
            current_failure_prob = min(current_failure_prob, 1.0)

            if random.random() < current_failure_prob:
                comp_state["failed"] = True

                # --- Capture only the specified data for the CSV row ---
                failures_for_csv.append({
                    "component_failed": component_name,
                    "failure_timestamp": timestamp_str[:7],
                    "operating_hours_at_failure": math.floor(current_operating_hours),
                })
                # Simulate repair
                comp_state["hours_since_last_repair"] = 0.0
                comp_state["failed"] = False

    return failures_for_csv # Return the list of dictionaries directly


# Define the base directory where your tractor data folders are located
base_data_directory = 'C:\\Users\\orena\\OneDrive\\Documents\\uirp-hackathon'

# This list will collect *all* simulated results from all folders for the final summary print.
# This list will now contain lists of failure dictionaries from each call to simulate_failures
all_summary_results_for_print = []

# Define CSV headers
CSV_HEADERS = ["component_failed", "failure_timestamp", "operating_hours_at_failure"]

# Iterate through tractor data folders (e.g., tractor_0, tractor_1, etc.)
for tractor_folder_num in range(0, 60):
    current_tractor_folder_path = os.path.join(base_data_directory, f"tractor_{tractor_folder_num}")

    if not os.path.isdir(current_tractor_folder_path):
        print(f"Error: Folder '{current_tractor_folder_path}' not found. Skipping.")
        continue

    print(f"\n--- Processing data for folder: {current_tractor_folder_path} ---")
    
    consolidated_data_for_folder = load_all_monthly_data(current_tractor_folder_path)

    # This list will store all failure rows (dictionaries) for the current folder's CSV
    current_folder_csv_rows = []

    for tractor_id_in_folder, single_tractor_data in consolidated_data_for_folder.items():
        print(f"Simulating failures for tractor: {tractor_id_in_folder}")
        
        # simulate_failures now returns a list of dictionaries directly for CSV rows
        sim_failures_list = simulate_failures(single_tractor_data)
        
        current_folder_csv_rows.extend(sim_failures_list)
        all_summary_results_for_print.append({ # Store for final print summary
            "tractor_id": tractor_id_in_folder,
            "model": single_tractor_data.get("tractor_specifications", {}).get("model", "Unknown Model"),
            "simulated_failures": sim_failures_list # Keep the full list for counting
        })

    # --- Output the simulated results to a CSV file PER FOLDER PROCESSED ---
    output_filename = f"simulated_failure_results_tractor_{tractor_folder_num}.csv" # Changed extension to .csv
    output_filepath = os.path.join(base_data_directory, "failure_logs", output_filename)

    if current_folder_csv_rows: # Only write if there are failures to report
        with open(output_filepath, 'w', newline='') as outfile: # newline='' is crucial for CSV
            writer = csv.DictWriter(outfile, fieldnames=CSV_HEADERS)
            writer.writeheader() # Write the header row
            writer.writerows(current_folder_csv_rows) # Write all failure rows

        print(f"Simulated failure logs for {current_tractor_folder_path} saved to: {output_filepath}")
    else:
        print(f"No failures simulated for {current_tractor_folder_path}. No CSV file created.")


# --- Overall Summary (Run once after all folders are processed) ---
print("\n--- Overall Simulation Summary Across All Folders ---")
total_failures_overall = 0
for result in all_summary_results_for_print:
    num_failures = len(result['simulated_failures'])
    total_failures_overall += num_failures
    print(f"Tractor ID: {result['tractor_id']}, Model: {result['model']}, Simulated Failures: {num_failures}")
print(f"\nTotal Simulated Failures Across All Tractors: {total_failures_overall}")