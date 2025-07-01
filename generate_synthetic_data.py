import os
import json
from datetime import datetime, timedelta
import random
import pandas as pd

NUM_SAMPLES = 1
NUM_MONTHS = 120
START_DATE = datetime(2015, 7, 1)

# Define a "failure threshold" for RUL calculation (e.g., a transmission fails at these hours)
# Each tractor will have a unique failure_hours_threshold
TRACTOR_FAILURE_HOURS = {
    i: random.randint(5000, 10000) for i in range(NUM_SAMPLES)
}

# Seasonal Operating Profiles for Champaign, IL (Corn/Soybean belt)
# Define average operating days and average daily hours per month
# Educated guess
MONTHLY_OPERATING_PROFILE = {
    1: {'operating_days_range': (2, 8), 'daily_hours_range': (1, 4), 'primary_mode': 'Transport/Idle'}, # Jan: Low, winter, snow, transport
    2: {'operating_days_range': (3, 10), 'daily_hours_range': (1, 4), 'primary_mode': 'Transport/Idle'}, # Feb: Low, winter, snow, transport
    3: {'operating_days_range': (8, 18), 'daily_hours_range': (4, 8), 'primary_mode': 'Tillage/Prep'}, # Mar: Spring prep, warmer
    4: {'operating_days_range': (18, 28), 'daily_hours_range': (8, 14), 'primary_mode': 'Planting/Tillage'}, # Apr: High, planting begins
    5: {'operating_days_range': (18, 28), 'daily_hours_range': (8, 14), 'primary_mode': 'Planting/Spraying'}, # May: High, planting/early spraying
    6: {'operating_days_range': (10, 20), 'daily_hours_range': (6, 10), 'primary_mode': 'Cultivating/Hay'}, # Jun: Medium-High, cultivating, hay
    7: {'operating_days_range': (8, 18), 'daily_hours_range': (5, 9), 'primary_mode': 'Spraying/Field Maintenance'}, # Jul: Medium, summer maintenance, some spraying
    8: {'operating_days_range': (10, 20), 'daily_hours_range': (6, 10), 'primary_mode': 'Spraying/Light Tillage'}, # Aug: Medium, pre-harvest, light tillage
    9: {'operating_days_range': (18, 28), 'daily_hours_range': (8, 14), 'primary_mode': 'Harvesting'}, # Sep: High, harvest begins
    10: {'operating_days_range': (18, 28), 'daily_hours_range': (8, 14), 'primary_mode': 'Harvesting/Tillage'}, # Oct: High, peak harvest/post-harvest tillage
    11: {'operating_days_range': (15, 25), 'daily_hours_range': (6, 10), 'primary_mode': 'Tillage/Fertilizing'}, # Nov: High-Medium, post-harvest tillage/fertilizing
    12: {'operating_days_range': (5, 15), 'daily_hours_range': (3, 7), 'primary_mode': 'Tillage/Transport/Idle'} # Dec: Medium-Low, late tillage, transport, winter prep
}

def get_simulated_weather(date, location_lat=40.11, location_lon=-88.21):
    """
    Simulates realistic weather data for Champaign, IL based on the month.
    This function provides a simplified, rule-based weather simulation.
    """
    month = date.month
    # Simple seasonal variations Midwest
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

BASE_OUTPUT_DIR = 'actual_data_csv'

TYPES_OF_FAILURES = {
    "Transmission Failure": 0,
    "Engine Failure": 1,
    "Hydraulic System Failure": 2,
    "Electrical System Failure": 3,
    "Tire Damage": 4,
    "Fuel System Failure": 5,
    "Cooling System Failure": 6,
    "Brake System Failure": 7,
    "Steering System Failure": 8,
    "Exhaust System Failure": 9
}

# Typical operating range for each sensor in normal conditions
SENSOR_BASELINES = {
    'engine_temp_c': (80, 100),
    'fuel_efficiency_l_hr': (10, 25),
    'engine_vibration_g': (0.5, 2.0),
    'oil_pressure_psi': (40, 60),
    'transmission_temp_c': (70, 90),
    'transmission_vibration_g': (0.4, 1.8),
    'transmission_fluid_level_percent': (90, 100),
    'hydraulic_pressure_psi': (2000, 3000),
    'hydraulic_fluid_temp_c': (60, 80),
    'hydraulic_fluid_level_percent': (90, 100),
    'battery_voltage_v': (12.5, 14.5),
    'alternator_current_a': (10, 50),
    'electrical_resistance_ohm': (0.1, 1.0),
    'tire_pressure_psi': (15, 25),
    'tire_vibration_g': (0.3, 1.5),
    'fuel_pressure_psi': (45, 65),
    'coolant_temp_c': (85, 95),
    'coolant_level_percent': (95, 100),
    'brake_temp_c': (50, 80),
    'brake_fluid_pressure_psi': (1000, 1500),
    'steering_effort_n': (50, 150),
    'exhaust_temp_c': (200, 400),
    'emissions_co2_ppm': (300, 600)
}

# Maps each failure type to the sensors it affects and the direction of the trend ('+' for increase, '-' for decrease).
# Again, an educated guess
FAILURE_TRENDS = {
    "Engine Failure": {
        'engine_temp_c': '+', 'fuel_efficiency_l_hr': '+',
        'engine_vibration_g': '+', 'oil_pressure_psi': '-',
        'exhaust_temp_c': '+', 'emissions_co2_ppm': '+'
    },
    "Transmission Failure": {
        'transmission_temp_c': '+', 'transmission_vibration_g': '+',
        'transmission_fluid_level_percent': '-', 'fuel_efficiency_l_hr': '+'
    },
    "Hydraulic System Failure": {
        'hydraulic_pressure_psi': '-', 'hydraulic_fluid_temp_c': '+',
        'hydraulic_fluid_level_percent': '-'
    },
    "Electrical System Failure": {
        'battery_voltage_v': '-', 'alternator_current_a': '+',
        'electrical_resistance_ohm': '+'
    },
    "Tire Damage": {
        'tire_pressure_psi': '-', 'tire_vibration_g': '+',
        'fuel_efficiency_l_hr': '+'
    },
    "Fuel System Failure": {
        'fuel_pressure_psi': '-', 'fuel_efficiency_l_hr': '+',
        'engine_vibration_g': '+'
    },
    "Cooling System Failure": {
        'coolant_temp_c': '+', 'coolant_level_percent': '-',
        'engine_temp_c': '+'
    },
    "Brake System Failure": {
        'brake_temp_c': '+', 'brake_fluid_pressure_psi': '-'
    },
    "Steering System Failure": {
        'steering_effort_n': '+', 'hydraulic_pressure_psi': '-'
    },
    "Exhaust System Failure": {
        'exhaust_temp_c': '+', 'emissions_co2_ppm': '+',
        'engine_vibration_g': '+'
    }
}

FAILURE_WINDOW_HOURS = 500 # The number of hours before the predicted failure when sensor trends start to become noticeable.
FAILURE_MAGNITUDE_FACTOR = 0.25 # The maximum percentage change a sensor value will deviate from its baseline at the exact point of failure.
NOISE_FACTOR = 0.05 # The percentage of a sensor's range used for random noise in its readings.

os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
print(f"Base folder '{BASE_OUTPUT_DIR}' ensured to exist.")

# Iterates through to create sample data
for i in range(NUM_SAMPLES):
    current_hours_cumulative = 0.0
    # Randomly select failure type
    type_of_failure = random.choice(list(TYPES_OF_FAILURES.keys()))
    # Get failure hour threshold
    failure_hours_for_sample = TRACTOR_FAILURE_HOURS[i]
    print(f"Sample {i}: Failure type '{type_of_failure}' expected at {failure_hours_for_sample} hours.")

    sample_data_rows = []
    failure_occurred_this_sample = False

    # Simulate data month by month until the total simulation duration or failure occurs
    for month_offset in range(NUM_MONTHS):
        current_date = START_DATE + timedelta(days=month_offset * 30) # Approximate month progression
        month_profile = MONTHLY_OPERATING_PROFILE[current_date.month]

        # Calculate monthly operating hours based on the seasonal profile
        operating_days = random.randint(*month_profile['operating_days_range'])
        daily_hours = random.uniform(*month_profile['daily_hours_range'])
        monthly_operating_hours = operating_days * daily_hours

        # Update the cumulative operating hours for the tractor
        current_hours_cumulative += monthly_operating_hours

        # Determine if failure is imminent or has occurred
        # Flag: 1 if failure trend is active, 0 otherwise
        failure_imminent = 0
        # Flag: 1 if failure occurs in this month, 0 otherwise
        failure_occurred = 0
        # Calculate Remaining Useful Life (RUL)
        remaining_useful_life = max(0, failure_hours_for_sample - current_hours_cumulative)

        # Check for failure occurrence
        if current_hours_cumulative >= failure_hours_for_sample:
            failure_occurred = 1
            failure_occurred_this_sample = True
            # For the last data point, set cumulative hours exactly to the failure point
            current_hours_cumulative = failure_hours_for_sample
            print(f"Sample {i}: Failure occurred at {current_hours_cumulative:.2f} hours in month {month_offset+1}.")
        # Check if the tractor is within the failure prediction window
        elif (failure_hours_for_sample - current_hours_cumulative) <= FAILURE_WINDOW_HOURS:
            failure_imminent = 1
            print(f"Sample {i}: Failure imminent (within {FAILURE_WINDOW_HOURS} hours) in month {month_offset+1}.")

        # Simulate weather data for the current month
        weather_data = get_simulated_weather(current_date)

        # Simulate sensor data, applying failure trends if applicable
        sensor_data = {}
        for sensor, (min_val, max_val) in SENSOR_BASELINES.items():
            # Base value for the sensor
            base_value = random.uniform(min_val, max_val)
            # Range for random noise
            noise_range = (max_val - min_val) * NOISE_FACTOR
            # Add initial noise
            final_value = base_value + random.uniform(-noise_range, noise_range)

            # Apply failure trend if failure is imminent and this sensor is affected by the chosen failure type
            if failure_imminent == 1 and sensor in FAILURE_TRENDS.get(type_of_failure, {}):
                # Calculate how far into the failure window the tractor is
                hours_into_failure_window = failure_hours_for_sample - current_hours_cumulative
                # Normalize progress from 0 (start of window) to 1 (at failure point)
                progress_in_window = (FAILURE_WINDOW_HOURS - hours_into_failure_window) / FAILURE_WINDOW_HOURS
                
                # Use a quadratic increase for trend intensity to make it more pronounced closer to failure
                trend_intensity = progress_in_window ** 2 

                trend_direction = FAILURE_TRENDS[type_of_failure][sensor]
                # Calculate the magnitude of the trend based on the max deviation and current intensity
                trend_amount = (max_val - min_val) * FAILURE_MAGNITUDE_FACTOR * trend_intensity

                # If the sensor value should increase
                if trend_direction == '+':
                    final_value = base_value + trend_amount + random.uniform(-noise_range/2, noise_range/2)
                    # For fuel efficiency, higher is worse, so allow it to go above max_val
                    if 'efficiency' in sensor:
                        # Cap at a reasonable upper bound
                        final_value = min(final_value, max_val * 1.5)
                    else:
                        # For other increasing metrics (temps, vibrations), ensure it's above base
                        final_value = max(final_value, base_value)
                elif trend_direction == '-':
                    final_value = base_value - trend_amount + random.uniform(-noise_range/2, noise_range/2)
                    # Ensure value doesn't drop below a reasonable lower bound
                    # Allow some undershoot for failure
                    final_value = max(final_value, min_val * 0.5)

            # Round sensor values for cleaner data
            sensor_data[sensor] = round(final_value, 2)

        # Simulate driver experience (constant for the simulation, could be dynamic)
        driver_experience_years = random.randint(1, 30)

        # Simulate maintenance adherence (90% chance of being followed)
        was_regular_maintenance_followed = 1 if random.random() < 0.9 else 0

        # Combine all generated data for the current month into a single record
        monthly_record = {
            'sample_id': i,
            'date': current_date.strftime('%Y-%m-%d'),
            'month': current_date.month,
            'year': current_date.year,
            'cumulative_hours': round(current_hours_cumulative, 2),
            'monthly_operating_hours': round(monthly_operating_hours, 2),
            'ambient_temp_c': weather_data['ambient_temp_c'],
            'humidity_percent': weather_data['humidity_percent'],
            'precipitation_mm_24hr': weather_data['precipitation_mm_24hr'],
            'wind_speed_kph': weather_data['wind_speed_kph'],
            'driver_experience_years': driver_experience_years,
            'was_regular_maintenance_followed': was_regular_maintenance_followed,
            **sensor_data,
            'failure_imminent': failure_imminent,
            'failure_occurred': failure_occurred,
            'type_of_failure': TYPES_OF_FAILURES[type_of_failure], # Use the index of the failure type
            'remaining_useful_life_hours': round(remaining_useful_life, 2)
        }
        sample_data_rows.append(monthly_record)

        # Stop data generation for this sample if failure has occurred
        if failure_occurred_this_sample:
            break

    # Convert the list of monthly records into a pandas DataFrame and save to a CSV file
    df = pd.DataFrame(sample_data_rows)
    output_csv_path = os.path.join(BASE_OUTPUT_DIR, f'sample_{i}_data.csv')
    df.to_csv(output_csv_path, index=False)
    print(f"Data for sample {i} saved to {output_csv_path}")

print("\nSimulation complete. Check the 'validation_data_csv' directory for generated data.")
