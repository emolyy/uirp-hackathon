import os
import json
from datetime import datetime, timedelta
import random

NUM_TRACTORS = 10
NUM_MONTHS = 60 # 5 years * 12 months
START_DATE = datetime(2020, 7, 1) # Start in July 2020

# Define a "failure threshold" for RUL calculation (e.g., a transmission fails at these hours)
# Each tractor will have a unique failure_hours_threshold
TRACTOR_FAILURE_HOURS = {
    f'JDL30005678{i}': random.randint(10000, 16000) for i in range(NUM_TRACTORS)
}
# Simulate that some tractors might have already had an alternator issue and repaired
TRACTOR_ALTERNATOR_FIXED_HOURS = {
    f'JDL30005678{i}': random.randint(5000, 10000) if random.random() < 0.7 else None # 70% chance of prior fix
    for i in range(NUM_TRACTORS)
}

# Base specifications (same for all tractors in this scenario)
BASE_TRACTOR_SPECS = {
    "model": "John Deere 8R 340",
    "year": 2020,
    "engine_type": "John Deere PowerTech PSS 9.0L",
    "horsepower_hp": 340,
    "transmission_type": "e23 PowerShift with Efficiency Manager",
    "hours_at_purchase": 0.0, # Assuming new tractors
    "attachments_specs": [
      {"name": "John Deere 2730 Combo Ripper", "type": "Tillage", "weight_kg": 4500},
      {"name": "John Deere ExactEmerge Planter", "type": "Planting", "weight_kg": 9000}
    ]
}

# --- Helper Functions for Data Simulation ---

def get_simulated_weather(date, location_lat=40.11, location_lon=-88.21):
    """
    Simulates realistic weather data for Champaign, IL.
    In a real scenario, you'd query a weather API or a historical database.
    """
    month = date.month
    day_of_month = date.day
    # Simple seasonal variations for Champaign, IL (Midwest US)
    if month in [12, 1, 2]: # Winter
        ambient_temp = random.uniform(-10, 5) # C
        humidity = random.uniform(70, 90)
        precipitation = random.uniform(0, 10) if random.random() < 0.5 else 0 # 50% chance of snow/rain
        wind_speed = random.uniform(10, 30)
    elif month in [3, 4, 5]: # Spring
        ambient_temp = random.uniform(5, 20)
        humidity = random.uniform(60, 80)
        precipitation = random.uniform(0, 5) if random.random() < 0.6 else 0 # Higher chance of rain
        wind_speed = random.uniform(15, 25)
    elif month in [6, 7, 8]: # Summer
        ambient_temp = random.uniform(20, 35)
        humidity = random.uniform(50, 75)
        precipitation = random.uniform(0, 3) if random.random() < 0.3 else 0 # Lower chance of rain
        wind_speed = random.uniform(5, 20)
    else: # Autumn (9, 10, 11)
        ambient_temp = random.uniform(10, 25)
        humidity = random.uniform(60, 85)
        precipitation = random.uniform(0, 5) if random.random() < 0.4 else 0
        wind_speed = random.uniform(10, 25)

    return {
        "ambient_temp_c": round(ambient_temp, 1),
        "humidity_percent": round(humidity, 0),
        "precipitation_mm_24hr": round(precipitation, 1),
        "wind_speed_kph": round(wind_speed, 1),
        "wind_direction": random.choice(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
    }

def get_simulated_soil_conditions():
    """Simulates soil conditions for a typical Midwest US farm."""
    return {
        "soil_type": random.choice(["Clay Loam", "Silty Clay Loam", "Loam"]),
        "soil_moisture_percent": random.uniform(25, 45), # Varies
        "terrain_type": "Flat" # Assuming typical Illinois farmland
    }

def simulate_operational_data(current_hours, is_failure_imminent, failure_type=None):
    """
    Simulates operational data, with degradation if failure is imminent.
    This is where the 'realism' of sensor values comes in.
    """
    engine_rpm = random.uniform(800, 2200) # Varies by mode
    engine_load = random.uniform(20, 95)
    coolant_temp = random.uniform(85, 95)
    oil_temp = random.uniform(90, 105)
    oil_pressure = random.uniform(40, 60)
    fuel_consumption = random.uniform(5, 30)
    fuel_level = random.uniform(10, 90)
    egt = random.uniform(300, 600)
    turbo_speed = random.uniform(50000, 130000)
    turbo_pressure = random.uniform(10, 30)

    hydraulic_temp = random.uniform(60, 85)
    transmission_temp = random.uniform(70, 90)
    oil_quality = random.uniform(0.75, 1.0) # Gradually degrades
    vibration_engine = random.uniform(0.05, 0.2)
    vibration_trans = random.uniform(0.05, 0.2) # Focus for failure
    vibration_axle = random.uniform(0.03, 0.1)
    vibration_bearing = random.uniform(0.03, 0.1)

    battery_voltage = random.uniform(12.5, 14.2)
    alternator_output = random.uniform(80, 150)
    error_codes = []

    working_mode = random.choice(["Plowing", "Planting", "Harvesting", "Transport", "Idle"])
    vehicle_speed = 0.0
    if working_mode == "Plowing":
        engine_rpm = random.uniform(1800, 2200)
        engine_load = random.uniform(70, 95)
        fuel_consumption = random.uniform(25, 35)
        hydraulic_temp = random.uniform(75, 90)
        transmission_temp = random.uniform(80, 95)
        vehicle_speed = random.uniform(6, 12)
    elif working_mode == "Transport":
        engine_rpm = random.uniform(1500, 2000)
        engine_load = random.uniform(30, 70)
        fuel_consumption = random.uniform(10, 25)
        hydraulic_temp = random.uniform(60, 75)
        transmission_temp = random.uniform(70, 85)
        vehicle_speed = random.uniform(20, 40)
    elif working_mode == "Idle":
        engine_rpm = random.uniform(700, 900)
        engine_load = random.uniform(5, 15)
        fuel_consumption = random.uniform(2, 5)
        vehicle_speed = 0.0

    # Simulate degradation if failure is imminent (e.g., transmission)
    if is_failure_imminent and failure_type == "Transmission":
        transmission_temp = max(transmission_temp, random.uniform(95, 115)) # Higher temp
        vibration_trans = max(vibration_trans, random.uniform(0.2, 0.5))    # Higher vibration
        if random.random() < 0.3: # 30% chance of a transmission error code
            error_codes.append("DTC_P0700_TransmissionControlSystem")
        if random.random() < 0.1: # Small chance of more critical code
            error_codes.append("DTC_P1700_TransmissionComponentSlippage")

    elif is_failure_imminent and failure_type == "Alternator":
        battery_voltage = min(battery_voltage, random.uniform(11.0, 12.0)) # Lower voltage
        alternator_output = min(alternator_output, random.uniform(0, 50)) # Lower output
        if random.random() < 0.8: # High chance of alternator error
            error_codes.append("DTC_P2501_ChargingSystemVoltageLow")

    return {
        "engine_performance": {
            "engine_rpm": round(engine_rpm, 0),
            "engine_load_percent": round(engine_load, 1),
            "engine_coolant_temp_c": round(coolant_temp, 1),
            "engine_oil_temp_c": round(oil_temp, 1),
            "oil_pressure_psi": round(oil_pressure, 1),
            "fuel_consumption_rate_l_hr": round(fuel_consumption, 1),
            "fuel_level_percent": round(fuel_level, 0),
            "exhaust_gas_temp_c": round(egt, 0),
            "turbocharger_speed_rpm": round(turbo_speed, 0),
            "turbocharger_pressure_psi": round(turbo_pressure, 1)
        },
        "fluid_levels_quality": {
            "hydraulic_fluid_level_percent": random.randint(85, 100),
            "hydraulic_fluid_temp_c": round(hydraulic_temp, 1),
            "transmission_fluid_level_percent": random.randint(85, 100),
            "transmission_fluid_temp_c": round(transmission_temp, 1),
            "coolant_level_percent": random.randint(90, 100),
            "oil_quality_index": round(oil_quality, 2)
        },
        "vibration_data": {
            "engine_vibration_rms_g": round(vibration_engine, 2),
            "transmission_vibration_rms_g": round(vibration_trans, 2),
            "axle_vibration_rms_g": round(vibration_axle, 2),
            "bearing_vibration_rms_g": round(vibration_bearing, 2)
        },
        "pressure_data": {
            "hydraulic_pressure_bar": random.uniform(100, 200),
            "tire_pressure_front_left_psi": random.randint(22, 28),
            "tire_pressure_front_right_psi": random.randint(22, 28),
            "tire_pressure_rear_left_psi": random.randint(12, 18),
            "tire_pressure_rear_right_psi": random.randint(12, 18),
            "fuel_pressure_psi": random.uniform(50, 65)
        },
        "electrical_system": {
            "battery_voltage_v": round(battery_voltage, 1),
            "alternator_output_amps": round(alternator_output, 0),
            "error_codes": error_codes
        },
        "usage_data": {
            "distance_traveled_km": round(random.uniform(0, 50), 1), # Daily distance
            "gps_latitude": round(random.uniform(40.1, 40.2), 4),
            "gps_longitude": round(random.uniform(-88.3, -88.1), 4),
            "working_mode": working_mode,
            "implement_attached": "John Deere 2730 Combo Ripper" if working_mode in ["Plowing", "Planting", "Harvesting"] else "None",
            "implement_hours_this_session": round(random.uniform(0, 8), 1) # Hours for current op
        },
        "other_sensors": {
            "vehicle_speed_kph": round(vehicle_speed, 1)
        }
    }

def generate_maintenance_event(current_hours, event_type, issue_desc, repair_desc, root_cause, parts, labor_hours):
    return {
        "maintenance_id": f"MAINT_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(100,999)}",
        "date_time": datetime.now().isoformat() + "Z", # Placeholder, adjust to actual event date
        "type": event_type,
        "parts_replaced": parts,
        "labor_hours": labor_hours,
        "operator_reported_issue": issue_desc,
        "technician_diagnosis_repair": repair_desc,
        "root_cause_of_failure": root_cause,
        "technician_notes": f"Tractor had {current_hours:.1f} hours at time of service."
    }

def generate_complaint(complaint_desc):
    return {
        "complaint_id": f"COMPL_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(100,999)}",
        "date": datetime.now().strftime('%Y-%m-%d'), # Placeholder
        "description": complaint_desc
    }

for i in range(NUM_TRACTORS):
    tractor_id = f'JDL30005678{i}'
    folder_name = f'tractor_{i}'
    os.makedirs(folder_name, exist_ok=True) # Create folder for each tractor

    current_hours_cumulative = 0.0
    # Randomly assign a failure point for this tractor's transmission
    transmission_failure_hours = TRACTOR_FAILURE_HOURS[tractor_id]
    # Check if this tractor had an alternator fixed
    alternator_fixed_hours = TRACTOR_ALTERNATOR_FIXED_HOURS[tractor_id]
    alternator_already_failed = False
    if alternator_fixed_hours is not None:
        alternator_already_failed = True

    # Keep track of maintenance history for the entire tractor lifecycle
    tractor_full_maintenance_history = []
    tractor_full_complaints_history = []

    for month_offset in range(NUM_MONTHS):
        current_date = START_DATE + timedelta(days=month_offset * 30) # Approx. month start
        month_str = current_date.strftime('%Y%m')
        file_name = os.path.join(folder_name, f'tractor_{i}_month_{month_str}.json')

        monthly_telemetry_records = []
        monthly_maintenance_summary = []
        monthly_customer_complaints = []

        # Simulate daily operation for approx 20 days in the month (some days off)
        operating_days_this_month = random.randint(15, 25)
        for day in range(operating_days_this_month):
            daily_operating_hours = random.uniform(5, 10) # 5-10 hours per operating day
            current_hours_cumulative += daily_operating_hours

            # Determine if a major failure is imminent for this tractor
            is_transmission_failure_imminent = False
            if current_hours_cumulative >= (transmission_failure_hours - 200) and \
               current_hours_cumulative < transmission_failure_hours:
                is_transmission_failure_imminent = True
                # Introduce a complaint in the month leading up to failure
                if random.random() < 0.1 and not any("humming" in c['description'] for c in monthly_customer_complaints):
                    monthly_customer_complaints.append(
                        generate_complaint("Increasing humming noise from transmission, especially under heavy load.")
                    )
            elif current_hours_cumulative >= transmission_failure_hours and \
                 current_hours_cumulative < (transmission_failure_hours + daily_operating_hours):
                # This is the "failure event" day
                is_transmission_failure_imminent = True # Still shows bad signs just before 0 RUL
                # Simulate the actual failure record
                monthly_telemetry_records.append({
                    "timestamp": (current_date + timedelta(days=day, hours=random.randint(8,17))).isoformat() + "Z",
                    "current_operating_hours": round(current_hours_cumulative, 1),
                    "remaining_useful_life_hours": 0.0, # Failure occurred
                    "failure_imminent": True,
                    "telemetry": simulate_operational_data(current_hours_cumulative, True, "Transmission"),
                    "environmental_context": get_simulated_weather(current_date + timedelta(days=day)),
                    "human_factors_external": {
                        "operator_id_anonymized": random.choice(["OPR_XYZ001", "OPR_ABC789"]),
                        "operator_experience_level": random.choice(["Experienced", "Intermediate"]),
                        "region_of_operation": "Midwest US",
                        "customer_complaints": [
                            generate_complaint("Tractor lost all drive, loud grinding noise from transmission.")
                        ]
                    }
                })
                monthly_maintenance_summary.append(
                    generate_maintenance_event(
                        current_hours_cumulative, "Corrective Maintenance - Unscheduled (Major)",
                        "Tractor lost drive, grinding noise.",
                        "Transmission overhaul/replacement due to severe internal wear.",
                        "Accelerated component wear (transmission)",
                        [{"part_number": "R600500", "description": "Transmission Clutch Pack", "cost_usd": 3500.00},
                         {"part_number": "R600501", "description": "Transmission Bearings Set", "cost_usd": 800.00}],
                        18.0
                    )
                )
                # After major repair, RUL conceptually resets for future prediction
                transmission_failure_hours = float('inf') # Mark as "fixed" for this tractor's first major failure
                alternator_already_failed = True # No more alternator failure for this tractor
                break # Tractor is down for repair, move to next month/tractor

            # Simulate alternator failure for some tractors
            is_alternator_failure_imminent = False
            if alternator_fixed_hours and not alternator_already_failed and \
               current_hours_cumulative >= (alternator_fixed_hours - 50) and \
               current_hours_cumulative < alternator_fixed_hours:
                is_alternator_failure_imminent = True
                if random.random() < 0.2 and not any("battery warning" in c['description'] for c in monthly_customer_complaints):
                    monthly_customer_complaints.append(
                        generate_complaint("Battery warning light flickers on dashboard.")
                    )
            elif alternator_fixed_hours and not alternator_already_failed and \
                 current_hours_cumulative >= alternator_fixed_hours and \
                 current_hours_cumulative < (alternator_fixed_hours + daily_operating_hours):
                is_alternator_failure_imminent = True # Still shows bad signs just before 0 RUL
                monthly_telemetry_records.append({
                    "timestamp": (current_date + timedelta(days=day, hours=random.randint(8,17))).isoformat() + "Z",
                    "current_operating_hours": round(current_hours_cumulative, 1),
                    "remaining_useful_life_hours": transmission_failure_hours - current_hours_cumulative,
                    "failure_imminent": True, # This failure is imminent, but major trans. failure is still future
                    "telemetry": simulate_operational_data(current_hours_cumulative, True, "Alternator"),
                    "environmental_context": get_simulated_weather(current_date + timedelta(days=day)),
                    "human_factors_external": {
                        "operator_id_anonymized": random.choice(["OPR_XYZ001", "OPR_ABC789"]),
                        "operator_experience_level": random.choice(["Experienced", "Intermediate"]),
                        "region_of_operation": "Midwest US",
                        "customer_complaints": [
                            generate_complaint("Battery warning light on. Tractor struggling to start.")
                        ]
                    }
                })
                monthly_maintenance_summary.append(
                    generate_maintenance_event(
                        current_hours_cumulative, "Corrective Maintenance - Unscheduled",
                        "Battery not charging.",
                        "Replaced alternator assembly. Tested charging system.",
                        "Component wear (alternator)",
                        [{"part_number": "R500123", "description": "Alternator Assembly", "cost_usd": 750.00}],
                        2.5
                    )
                )
                alternator_already_failed = True # Mark alternator as fixed for this tractor
                # The tractor continues operation, RUL for the *major* failure remains the same.
                # No break, as this is a minor fix.

            # Append general telemetry record
            telemetry_data = simulate_operational_data(
                current_hours_cumulative,
                is_transmission_failure_imminent or is_alternator_failure_imminent
            )
            monthly_telemetry_records.append({
                "timestamp": (current_date + timedelta(days=day, hours=random.randint(0,23))).isoformat() + "Z",
                "current_operating_hours": round(current_hours_cumulative, 1),
                "remaining_useful_life_hours": round(transmission_failure_hours - current_hours_cumulative, 1),
                "failure_imminent": is_transmission_failure_imminent or is_alternator_failure_imminent,
                "telemetry": telemetry_data,
                "environmental_context": get_simulated_weather(current_date + timedelta(days=day)),
                "human_factors_external": {
                    "operator_id_anonymized": random.choice(["OPR_XYZ001", "OPR_ABC789", "OPR_DEF456"]),
                    "operator_experience_level": random.choice(["Experienced", "Intermediate", "New"]),
                    "region_of_operation": "Midwest US",
                    "customer_complaints": [] # Complaints are added specifically above
                }
            })

        # Add scheduled maintenance if applicable (e.g., every 500 hours or annually)
        # This is a simplification; in real life, you'd check hours and date.
        if (month_offset % 12 == 0 and month_offset > 0) or (current_hours_cumulative % 500 < (daily_operating_hours * 2) and current_hours_cumulative // 500 > (current_hours_cumulative - daily_operating_hours*2) // 500):
            if current_hours_cumulative > 100: # Don't add for very first month
                 monthly_maintenance_summary.append(
                    generate_maintenance_event(
                        current_hours_cumulative, "Scheduled Maintenance - Annual/X-Hr Service",
                        "Routine service.",
                        "Completed standard service. All fluids and filters replaced. Checked for wear. System diagnostics clear.",
                        "N/A",
                        [{"part_number": "R200001", "description": "Engine Oil Filter", "cost_usd": 35.00}],
                        8.0
                    )
                )

        # Combine all data for the month
        monthly_data = {
            "tractor_id": tractor_id,
            "data_month": current_date.strftime('%Y-%m'),
            "tractor_specifications": BASE_TRACTOR_SPECS,
            "monthly_telemetry_records": monthly_telemetry_records,
            "monthly_maintenance_summary": monthly_maintenance_summary,
            "monthly_customer_complaints": monthly_customer_complaints
        }

        # Save to file
        with open(file_name, 'w') as f:
            json.dump(monthly_data, f, indent=2)

    print(f"Generated data for {tractor_id} in folder '{folder_name}'.")