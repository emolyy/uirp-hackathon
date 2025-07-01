from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import pandas as pd
import joblib
import numpy as np
import os # Included for compatibility with the provided function

# This is the exact preprocessing function you provided in your training script.
def preprocess_and_engineer_features(df, columns_to_drop, lags=3, rolling_windows=[5, 10, 20], diff_periods=[1, 3], ewma_spans=[10, 20]):
    processed_df = df.copy()
    if 'sample_id' not in processed_df.columns:
        temp_sample_id_present = False
    else:
        temp_sample_id_present = True
        processed_df = processed_df.sort_values(by=['sample_id']).reset_index(drop=True)

    numerical_cols_for_fe = [
        col for col in processed_df.columns
        if pd.api.types.is_numeric_dtype(processed_df[col]) and
           col not in ['sample_id', 'remaining_useful_life_hours']
    ]
    for col in numerical_cols_for_fe:
        for i in range(1, lags + 1):
            if temp_sample_id_present:
                processed_df[f'{col}_lag_{i}'] = processed_df.groupby('sample_id')[col].shift(i)
            else:
                processed_df[f'{col}_lag_{i}'] = processed_df[col].shift(i)
        for window in rolling_windows:
            if temp_sample_id_present:
                processed_df[f'{col}_rolling_mean_{window}'] = processed_df.groupby('sample_id')[col].rolling(window=window).mean().reset_index(level=0, drop=True)
                processed_df[f'{col}_rolling_std_{window}'] = processed_df.groupby('sample_id')[col].rolling(window=window).std().reset_index(level=0, drop=True)
            else:
                processed_df[f'{col}_rolling_mean_{window}'] = processed_df[col].rolling(window=window).mean()
                processed_df[f'{col}_rolling_std_{window}'] = processed_df[col].rolling(window=window).std()
        for period in diff_periods:
            if temp_sample_id_present:
                processed_df[f'{col}_diff_{period}'] = processed_df.groupby('sample_id')[col].diff(periods=period)
            else:
                processed_df[f'{col}_diff_{period}'] = processed_df[col].diff(periods=period)
        for span in ewma_spans:
            if temp_sample_id_present:
                processed_df[f'{col}_ewma_{span}'] = processed_df.groupby('sample_id')[col].ewm(span=span, adjust=False).mean().reset_index(level=0, drop=True)
            else:
                processed_df[f'{col}_ewma_{span}'] = processed_df[col].ewm(span=span, adjust=False).mean()
    if 'remaining_useful_life_hours' in processed_df.columns:
        y = processed_df['remaining_useful_life_hours']
    else:
        y = None
    existing_columns_to_drop = [col for col in columns_to_drop if col in processed_df.columns]
    X = processed_df.drop(columns=existing_columns_to_drop, axis=1)
    for col in X.columns:
        if X[col].dtype == 'object':
            X = X.drop(columns=[col])
    initial_rows = X.shape[0]
    if y is not None:
        X_aligned, y_aligned = X.align(y, join='inner', axis=0)
        combined_for_dropna = pd.concat([X_aligned, y_aligned], axis=1)
        combined_for_dropna.dropna(inplace=True)
        X = combined_for_dropna.drop(columns=['remaining_useful_life_hours'])
        y = combined_for_dropna['remaining_useful_life_hours']
    else:
        X.dropna(inplace=True)
    return X, y


# --- 1. Load Model and the FULL Historical Data for the sample ---
try:
    # Load your pre-trained model
    model = joblib.load('mae_403.joblib')
    # Load the full history for the equipment we want to predict on
    full_history_df = pd.read_csv('sample_0_data.csv')
except FileNotFoundError as e:
    print(f"Error: {e}. Make sure 'mae_403.joblib' and 'sample_0_data.csv' are present.")
    exit()


# --- 2. Process the ENTIRE History to Generate Features Correctly ---

# Define the columns to drop, same as in your training script
columns_to_drop = [
    'sample_id', 'date', 'type_of_failure', 'failure_imminent',
    'failure_occurred', 'remaining_useful_life_hours'
]

print("Processing full history to engineer features for prediction...")
# Process the entire dataframe. The function will calculate lags/rolling-windows
# correctly for every row based on its history.
X_processed, y_processed = preprocess_and_engineer_features(full_history_df, columns_to_drop)


# --- 3. Select the Final Rows for Prediction ---

# Now that all features are calculated, select the last 5 rows to predict on
X_to_predict = X_processed.tail(5)
y_actual = y_processed.tail(5)

# --- 4. Align Columns and Predict ---

# CRITICAL: Get the feature columns from the model itself to ensure perfect alignment
# XGBoost models store feature names if trained on a DataFrame
model_features = model.get_booster().feature_names
X_to_predict_aligned = X_to_predict.reindex(columns=model_features, fill_value=0)

print("\nMaking predictions on the last 5 time steps...")
predictions = model.predict(X_to_predict_aligned)

# --- 5. View Results ---
results = pd.DataFrame({
    'Actual_RUL': y_actual.values,
    'Predicted_RUL': predictions
})

print("\n--- Comparison of Actual vs. Predicted RUL ---")
print(results)

# calculate scores
mae = mean_absolute_error(y_actual, predictions)
mse = mean_squared_error(y_actual, predictions)
r2 = r2_score(y_actual, predictions)

print(f"\nMean Absolute Error: {mae}")
print(f"Mean Squared Error: {mse}")
print(f"R^2 Score: {r2}")