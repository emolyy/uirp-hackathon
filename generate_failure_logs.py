import os
import json
import csv
from datetime import datetime, timedelta
import random
import math

# Component Lifespans
COMPONENT_LIFESPANS = {
    "engine_system": 15000.0,
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

# Probability Tuning Factors
PROB_SCALING_FACTOR = 0.000005
# Shapes the wear-based probability curve.
#   < 1.0: Probability increases faster initially (more early failures).
#   = 1.0: Linear increase.
#   > 1.0: Accelerates towards end of life (more late failures).

PROB_EXPONENT = 1.5

# BASE_FAILURE_PROB_PER_HOUR: Constant probability for random, non-wear failures.
BASE_FAILURE_PROB_PER_HOUR = 0.00000005 # Very small baseline chance per hour

# Telemetry Parameter Ranges and Normal Fluctuations
TELEMETRY_PARAMS = {
    "engine_coolant_temp_c": {"normal_range": (85, 95), "daily_std_dev": 2, "failure_drift_factor": 0.5, "failure_component": "cooling_system"},
    "engine_oil_pressure_psi": {"normal_range": (40, 60), "daily_std_dev": 3, "failure_drift_factor": -0.4, "failure_component": "engine_system"}, # Negative drift means pressure drops
    "hydraulic_fluid_temp_c": {"normal_range": (70, 85), "daily_std_dev": 2, "failure_drift_factor": 0.3, "failure_component": "hydraulic_system"},
    "hydraulic_pressure_psi": {"normal_range": (2000, 2500), "daily_std_dev": 50, "failure_drift_factor": -0.2, "failure_component": "hydraulic_system"},
    "vibration_level_g": {"normal_range": (0.5, 1.5), "daily_std_dev": 0.1, "failure_drift_factor": 0.8, "failure_component": "processing_cleaning_system"}, # High vibration for processing
    "electrical_voltage_v": {"normal_range": (12.5, 14.0), "daily_std_dev": 0.2, "failure_drift_factor": -0.1, "failure_component": "electrical_system"},
    "fuel_pressure_psi": {"normal_range": (50, 70), "daily_std_dev": 2, "failure_drift_factor": -0.3, "failure_component": "fuel_system"},
    "def_level_percent": {"normal_range": (20, 100), "daily_std_dev": 1, "failure_drift_factor": -0.5, "failure_component": "def_system"}, # Drops faster before DEF system failure
    "oil_level_percent": {"normal_range": (80, 100), "daily_std_dev": 0.5, "failure_drift_factor": -0.2, "failure_component": "engine_system"}, # Gradual drop for engine oil
    "engine_rpm": {"normal_range": (1500, 2200), "daily_std_dev": 100, "failure_drift_factor": 0.1, "failure_component": "engine_system"}, # May fluctuate more before failure
    "engine_load_percent": {"normal_range": (40, 80), "daily_std_dev": 10, "failure_drift_factor": 0.1, "failure_component": "engine_system"},
    "ambient_temp_c": {"normal_range": (10, 30), "daily_std_dev": 3, "failure_drift_factor": 0, "failure_component": None}, # No direct failure link
}

# Seasonal Profiles
SEASONAL_PROFILES = {
    1: {"avg_hours": 2, "temp_shift": -10},
    2: {"avg_hours": 3, "temp_shift": -8},
    3: {"avg_hours": 5, "temp_shift": -3},
    4: {"avg_hours": 8, "temp_shift": 2},
    5: {"avg_hours": 10, "temp_shift": 5},
    6: {"avg_hours": 7, "temp_shift": 8},
    7: {"avg_hours": 6, "temp_shift": 10},
    8: {"avg_hours": 9, "temp_shift": 7},
    9: {"avg_hours": 12, "temp_shift": 3},
    10: {"avg_hours": 10, "temp_shift": -2},
    11: {"avg_hours": 4, "temp_shift": -5},
    12: {"avg_hours": 2, "temp_shift": -10}
}

# Driver Experience Impact
DRIVER_PROFILES = {
    "Novice": {"hours_multiplier_std_dev": 0.3, "stress_factor": 1.2},
    "Experienced": {"hours_multiplier_std_dev": 0.1, "stress_factor": 0.9},
    "Expert": {"hours_multiplier_std_dev": 0.05, "stress_factor": 0.8}
}

# Maintenance Provider Impact
MAINTENANCE_PROFILES = {
    "Dealer": {"repair_effectiveness": 1.0, "lifespan_multiplier": 1.0},
    "Independent": {"repair_effectiveness": 0.9, "lifespan_multiplier": 0.95},
    "Owner": {"repair_effectiveness": 0.7, "lifespan_multiplier": 0.9}
}

# Error Codes (Simplified mapping for demonstration)
ERROR_CODES = {
    "engine_system": ["P0100", "P0200", "P0300"],
    "hydraulic_system": ["H101", "H102"],
    "electrical_system": ["E001", "E002"],
    "cooling_system": ["C001"],
    "fuel_system": ["F001"],
    "transmission_drive_system": ["T001"],
    "processing_cleaning_system": ["PC01"],
    "auger_unloading_system": ["AU01"],
    "def_system": ["D001"],
    "sensor_vision_system": ["S001"]
}

# Simulate 3 years of data
SIMULATION_DAYS = 365 * 3
START_DATE = datetime(2022, 1, 1)

def date_range(start_date, end_date):
    """Generates dates between start_date and end_date (inclusive)."""
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + timedelta(n)

def clamp(value, min_val, max_val):
    """Clamps a value within a given range."""
    return max(min_val, min(value, max_val))

def get_random_error_code(component_name):
    """Returns a random error code for a given component."""
    codes = ERROR_CODES.get(component_name, [])
    return random.choice(codes) if codes else None

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

def simulate_tractor_data(tractor_data):
    tractor_id = tractor_data["tractor_id"]
    specs = tractor_data.get("tractor_specifications", {})
    
    # Use tractor_id as part of the random seed for reproducibility per tractor
    random.seed(f"sim_data_{tractor_id}_seed")

    # Assign driver experience and maintenance provider randomly if not in specs
    driver_experience = specs.get("driver_experience", random.choice(list(DRIVER_PROFILES.keys())))
    maintenance_provider = specs.get("maintenance_provider", random.choice(list(MAINTENANCE_PROFILES.keys())))

    # Initialize component status
    component_status = {}
    initial_hours_at_purchase = specs.get("hours_at_purchase", 0.0)
    for component_name in COMPONENT_LIFESPANS.keys():
        component_status[component_name] = {
            "hours_since_last_repair": initial_hours_at_purchase,
            "failed_on_day": None, # Date of failure if it occurs
            "is_failed": False,
            "effective_lifespan": COMPONENT_LIFESPANS[component_name] * MAINTENANCE_PROFILES[maintenance_provider]["lifespan_multiplier"]
        }
    
    current_operating_hours = initial_hours_at_purchase
    all_daily_records = []
    
    # Track when the next failure is predicted to occur for `time_until_next_failure_hours`
    # This will be filled in a reverse pass after the simulation.
    future_failures = []

    # Simulate day by day
    for day_offset in range(SIMULATION_DAYS):
        current_date = START_DATE + timedelta(days=day_offset)
        month = current_date.month
        
        season_profile = SEASONAL_PROFILES[month]
        driver_profile = DRIVER_PROFILES[driver_experience]

        # Simulate Daily Operating Hours
        avg_daily_hours = season_profile["avg_hours"]
        hours_std_dev = avg_daily_hours * driver_profile["hours_multiplier_std_dev"]
        hours_today = max(0, random.gauss(avg_daily_hours, hours_std_dev))
        
        if any(cs["is_failed"] for cs in component_status.values()):
            hours_today = 0

        current_operating_hours += hours_today

        daily_record = {
            "tractor_id": tractor_id,
            "date": current_date.isoformat(),
            "operating_hours_today": round(hours_today, 2),
            "cumulative_operating_hours": round(current_operating_hours, 2),
            "seasonal_use_factor": season_profile["avg_hours"],
            "driver_experience": driver_experience,
            "maintenance_provider": maintenance_provider,
            "is_failure": 0,
            "failed_component": None,
            "failure_type": None,
            "error_code": None,
            "time_until_next_failure_hours": None
        }

        # Simulate Telemetry Data
        current_telemetry = {}
        for param_name, param_info in TELEMETRY_PARAMS.items():
            normal_min, normal_max = param_info["normal_range"]
            daily_std_dev = param_info["daily_std_dev"]
            
            # Apply seasonal shift to ambient temperature
            if param_name == "ambient_temp_c":
                base_val = (normal_min + normal_max) / 2 + season_profile["temp_shift"]
            else:
                base_val = (normal_min + normal_max) / 2

            # Apply random daily fluctuation
            value = random.gauss(base_val, daily_std_dev)

            # Apply stress factor from driver experience
            if param_name in ["engine_coolant_temp_c", "engine_oil_pressure_psi", "vibration_level_g", "hydraulic_fluid_temp_c", "hydraulic_pressure_psi"]:
                value += (driver_profile["stress_factor"] - 1.0) * (normal_max - normal_min) * 0.1

            # Apply precursor drift if a related component is approaching failure
            # A simple linear drift: if ratio_to_lifespan > 0.7, start drifting
            related_component = param_info.get("failure_component")
            if related_component and not component_status[related_component]["is_failed"]:
                comp_hours = component_status[related_component]["hours_since_last_repair"]
                comp_lifespan = component_status[related_component]["effective_lifespan"]
                
                ratio_to_lifespan = comp_hours / comp_lifespan

                if ratio_to_lifespan > 0.7:
                    drift_amount = (ratio_to_lifespan - 0.7) / 0.3 * (normal_max - normal_min) * param_info["failure_drift_factor"]
                    value += drift_amount

            current_telemetry[param_name] = clamp(value, normal_min, normal_max)
            
            # Special logic for fluid levels (they naturally decrease)
            if param_name in ["def_level_percent", "oil_level_percent"]:
                # Simulate consumption (small daily drop)
                daily_consumption_rate = 0.05
                current_telemetry[param_name] = max(0, current_telemetry[param_name] - daily_consumption_rate * (hours_today / 8.0)) # Scale by hours

                # If fluid level drops below a threshold, it might trigger a failure
                if current_telemetry[param_name] < 10 and not component_status[param_info["failure_component"]]["is_failed"]:
                    pass


        daily_record["telemetry"] = current_telemetry

        # Check for Component Failures
        for component_name, comp_info in COMPONENT_LIFESPANS.items():
            comp_state = component_status[component_name]

            if comp_state["is_failed"]:
                continue

            comp_state["hours_since_last_repair"] += hours_today

            # Calculate wear-based probability
            ratio_to_lifespan = comp_state["hours_since_last_repair"] / comp_state["effective_lifespan"]
            
            # Ensure ratio is not too small for exponentiation, and cap at 2.0 for extreme wear
            clamped_ratio = clamp(ratio_to_lifespan, 0.001, 2.0) 
            wear_based_prob = (clamped_ratio ** PROB_EXPONENT) * PROB_SCALING_FACTOR * hours_today

            # Add base failure probability (pure randomness)
            current_failure_prob = wear_based_prob + (BASE_FAILURE_PROB_PER_HOUR * hours_today)
            current_failure_prob = min(current_failure_prob, 1.0)

            # Check for failure
            if random.random() < current_failure_prob:
                comp_state["is_failed"] = True
                comp_state["failed_on_day"] = current_date

                daily_record["is_failure"] = 1
                daily_record["failed_component"] = component_name
                daily_record["failure_type"] = f"{component_name.replace('_', ' ').title()} Failure (Simulated)"
                daily_record["error_code"] = get_random_error_code(component_name)

                # Store this failure event for the reverse pass calculation
                future_failures.append({
                    "timestamp_dt": current_date,
                    "operating_hours": current_operating_hours,
                    "component": component_name
                })

                # Simulate repair immediately after logging for simplicity.
                repair_effectiveness = MAINTENANCE_PROFILES[maintenance_provider]["repair_effectiveness"]
                comp_state["hours_since_last_repair"] = comp_state["hours_since_last_repair"] * (1 - repair_effectiveness) # Partial reset based on repair quality
                comp_state["is_failed"] = False

        all_daily_records.append(daily_record)

    # Sort future_failures by timestamp in ascending order
    future_failures.sort(key=lambda x: x["timestamp_dt"])

    # Iterate through daily records in reverse to calculate time_until_next_failure_hours
    next_failure_info = None
    
    for i in range(len(all_daily_records) - 1, -1, -1):
        record = all_daily_records[i]
        
        # If this record itself is a failure, update next_failure_info
        if record["is_failure"] == 1:
            next_failure_info = {
                "timestamp_dt": datetime.fromisoformat(record["date"]),
                "operating_hours": record["cumulative_operating_hours"]
            }
            record["time_until_next_failure_hours"] = 0
        else:
            if next_failure_info:
                # Hours difference from current record's cumulative hours to next failure's cumulative hours
                hours_diff = next_failure_info["operating_hours"] - record["cumulative_operating_hours"]
                
                # Ensure hours_diff is non-negative (can be 0 if failure is on the same day)
                record["time_until_next_failure_hours"] = max(0, round(hours_diff, 2))
            else:
                # No future failures found from this point onwards
                record["time_until_next_failure_hours"] = -1

    return all_daily_records

if __name__ == "__main__":
    base_data_directory = 'C:\\Users\\orena\\OneDrive\\Documents\\uirp-hackathon'
    all_summary_results = []

    CSV_HEADERS = [
        "tractor_id", "date", "operating_hours_today", "cumulative_operating_hours",
        "seasonal_use_factor", "driver_experience", "maintenance_provider",
        "is_failure", "failed_component", "failure_type", "error_code",
        "time_until_next_failure_hours"
    ]
    # Add all telemetry parameters to the CSV headers
    for param_name in TELEMETRY_PARAMS.keys():
        CSV_HEADERS.append(f"telemetry_{param_name}")

    # Iterate through tractor data folders (e.g., tractor_0, tractor_1, etc.)
    for tractor_folder_num in range(0, 5):
        current_tractor_folder_path = os.path.join(base_data_directory, 'tractor_' + str(tractor_folder_num))

        if not os.path.isdir(current_tractor_folder_path):
            print(f"Error: Folder '{current_tractor_folder_path}' not found. Skipping.")
            continue

        print(f"\n--- Processing data for folder: {current_tractor_folder_path} ---")
        consolidated_data_for_folder = load_all_monthly_data(current_tractor_folder_path)

        for tractor_id_in_folder, single_tractor_data in consolidated_data_for_folder.items():
            print(f"Simulating data for tractor: {tractor_id_in_folder}")
            
            # Simulate daily telemetry and failures for this tractor
            daily_telemetry_records = simulate_tractor_data(single_tractor_data)
            
            # Count failures for summary
            num_failures = sum(1 for record in daily_telemetry_records if record["is_failure"] == 1)
            all_summary_results.append({
                "tractor_id": tractor_id_in_folder,
                "model": single_tractor_data.get("tractor_specifications", {}).get("model", "Unknown Model"),
                "total_records": len(daily_telemetry_records),
                "simulated_failures": num_failures
            })

            output_filename = f"simulated_telemetry_{tractor_id_in_folder}.csv"
            output_filepath = os.path.join(base_data_directory, output_filename)

            with open(output_filepath, 'w', newline='') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=CSV_HEADERS)
                writer.writeheader()
                
                for record in daily_telemetry_records:
                    # Flatten telemetry dictionary into top-level keys for CSV
                    flat_record = record.copy()
                    telemetry_data = flat_record.pop("telemetry", {})
                    for param_name, value in telemetry_data.items():
                        flat_record[f"telemetry_{param_name}"] = round(value, 2)

                    writer.writerow(flat_record)

            print(f"Simulated telemetry and failure data for {tractor_id_in_folder} saved to: {output_filepath}")

    print("\n--- Overall Simulation Summary Across All Tractors ---")
    total_failures_overall = 0
    total_records_overall = 0
    for result in all_summary_results:
        total_failures_overall += result['simulated_failures']
        total_records_overall += result['total_records']
        print(f"Tractor ID: {result['tractor_id']}, Model: {result['model']}, Total Records: {result['total_records']}, Simulated Failures: {result['simulated_failures']}")
    print(f"\nTotal Simulated Failures Across All Tractors: {total_failures_overall}")
    print(f"Total Daily Records Generated: {total_records_overall}")