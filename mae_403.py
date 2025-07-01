import joblib
import pandas as pd
from sklearn.model_selection import train_test_split, RandomizedSearchCV
from xgboost import XGBRegressor
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
import os
import numpy as np

training_folder_path = 'training_data_csv'
validation_folder_path = 'validation_data_csv'

def preprocess_and_engineer_features(df, columns_to_drop, lags=3, rolling_windows=[5, 10, 20], diff_periods=[1, 3], ewma_spans=[10, 20]):
    processed_df = df.copy()

    if 'sample_id' not in processed_df.columns:
        print("Warning: 'sample_id' column not found. Time-series features will be applied globally, not per sample.")
        temp_sample_id_present = False
    else:
        temp_sample_id_present = True
        processed_df = processed_df.sort_values(by=['sample_id']).reset_index(drop=True)

    numerical_cols_for_fe = [
        col for col in processed_df.columns
        if pd.api.types.is_numeric_dtype(processed_df[col]) and
           col not in ['sample_id', 'remaining_useful_life_hours']
    ]

    print(f"Applying feature engineering for numerical columns: {numerical_cols_for_fe}")

    for col in numerical_cols_for_fe:
        # 1. Lagged Features
        for i in range(1, lags + 1):
            if temp_sample_id_present:
                processed_df[f'{col}_lag_{i}'] = processed_df.groupby('sample_id')[col].shift(i)
            else:
                processed_df[f'{col}_lag_{i}'] = processed_df[col].shift(i)

        # 2. Rolling Statistics
        for window in rolling_windows:
            if temp_sample_id_present:
                processed_df[f'{col}_rolling_mean_{window}'] = processed_df.groupby('sample_id')[col].rolling(window=window).mean().reset_index(level=0, drop=True)
                processed_df[f'{col}_rolling_std_{window}'] = processed_df.groupby('sample_id')[col].rolling(window=window).std().reset_index(level=0, drop=True)
                processed_df[f'{col}_rolling_min_{window}'] = processed_df.groupby('sample_id')[col].rolling(window=window).min().reset_index(level=0, drop=True)
                processed_df[f'{col}_rolling_max_{window}'] = processed_df.groupby('sample_id')[col].rolling(window=window).max().reset_index(level=0, drop=True)
            else:
                processed_df[f'{col}_rolling_mean_{window}'] = processed_df[col].rolling(window=window).mean()
                processed_df[f'{col}_rolling_std_{window}'] = processed_df[col].rolling(window=window).std()
                processed_df[f'{col}_rolling_min_{window}'] = processed_df[col].rolling(window=window).min()
                processed_df[f'{col}_rolling_max_{window}'] = processed_df[col].rolling(window=window).max()

        # 3. Rate of Change / Derivatives
        for period in diff_periods:
            if temp_sample_id_present:
                processed_df[f'{col}_diff_{period}'] = processed_df.groupby('sample_id')[col].diff(periods=period)
            else:
                processed_df[f'{col}_diff_{period}'] = processed_df[col].diff(periods=period)

        # 4. Exponentially Weighted Moving Averages (EWMA)
        for span in ewma_spans:
            if temp_sample_id_present:
                processed_df[f'{col}_ewma_{span}'] = processed_df.groupby('sample_id')[col].ewm(span=span, adjust=False).mean().reset_index(level=0, drop=True)
            else:
                processed_df[f'{col}_ewma_{span}'] = processed_df[col].ewm(span=span, adjust=False).mean()


    # Extract the target variable before dropping it from features
    if 'remaining_useful_life_hours' in processed_df.columns:
        y = processed_df['remaining_useful_life_hours']
    else:
        y = None # Handle error if RUL is expected but not found

    # Drop specified columns, including the target if it's in the list
    existing_columns_to_drop = [col for col in columns_to_drop if col in processed_df.columns]
    X = processed_df.drop(columns=existing_columns_to_drop, axis=1)

    # Handle any remaining non-numeric columns in X by converting to numeric or dropping
    for col in X.columns:
        if X[col].dtype == 'object':
            try:
                X[col] = pd.to_numeric(X[col])
                print(f"Converted column '{col}' to numeric.")
            except ValueError:
                print(f"Warning: Column '{col}' contains non-numeric values and could not be converted. Dropping it.")
                X = X.drop(columns=[col])

    # Drop rows with NaN values introduced by feature engineering (lags, rolling, diff, ewma)
    initial_rows = X.shape[0]
    if y is not None:
        # Align indices before concatenating to ensure correct row dropping
        X_aligned, y_aligned = X.align(y, join='inner', axis=0)
        combined_for_dropna = pd.concat([X_aligned, y_aligned], axis=1)
        combined_for_dropna.dropna(inplace=True)
        X = combined_for_dropna.drop(columns=['remaining_useful_life_hours'])
        y = combined_for_dropna['remaining_useful_life_hours']
    else:
        X.dropna(inplace=True)

    if X.shape[0] < initial_rows:
        print(f"Dropped {initial_rows - X.shape[0]} rows due to NaN values after advanced feature engineering and preprocessing.")

    return X, y


# Initialize an empty list to store dataframes for training
all_training_dataframes = []

print(f"Loading training data from: {training_folder_path}")
for filename in os.listdir(training_folder_path):
    if filename.endswith('.csv'):
        file_path = os.path.join(training_folder_path, filename)
        try:
            df = pd.read_csv(file_path)
            all_training_dataframes.append(df)
            print(f"Loaded {filename} for training.")
        except Exception as e:
            print(f"Error reading {filename} for training: {e}")

if all_training_dataframes:
    combined_training_df = pd.concat(all_training_dataframes, ignore_index=True)
    print(f"Successfully combined {len(all_training_dataframes)} training CSV files.")
    print(f"Combined Training DataFrame shape: {combined_training_df.shape}")

    columns_to_drop = [
        'sample_id', 'date', 'type_of_failure',
        'failure_imminent', 'failure_occurred',
        'remaining_useful_life_hours'
    ]

    # Apply advanced preprocessing and feature engineering to training data
    X_train_full, y_train_full = preprocess_and_engineer_features(
        combined_training_df,
        columns_to_drop,
        lags=3,
        rolling_windows=[5, 10, 20],
        diff_periods=[1, 3],
        ewma_spans=[10, 20]
    )

    print(f"\nFeatures (X_train_full) shape after preparation: {X_train_full.shape}")
    print(f"Target (y_train_full) shape after preparation: {y_train_full.shape}")

    if X_train_full.shape[0] != y_train_full.shape[0]:
        print("Error: Number of samples in training features (X_train_full) and target (y_train_full) do not match. Please check data preparation.")
    else:
        X_train, X_test, y_train, y_test = train_test_split(X_train_full, y_train_full, test_size=0.2, random_state=42)

        print("\nTraining Data Split Complete:")
        print(f"X_train shape: {X_train.shape}")
        print(f"X_test shape: {X_test.shape}")
        print(f"y_train shape: {y_train.shape}")
        print(f"y_test shape: {y_test.shape}")

        print("\nTraining XGBoost Regressor model with Hyperparameter Tuning...")

        xgb_model = XGBRegressor(random_state=42, n_jobs=-1)

        param_dist = {
            'n_estimators': [200, 400, 600, 800, 1000, 1200],
            'learning_rate': [0.01, 0.03, 0.05, 0.1, 0.15],
            'max_depth': [5, 6, 7, 8, 9, 10],
            'subsample': [0.7, 0.8, 0.9, 1.0],
            'colsample_bytree': [0.7, 0.8, 0.9, 1.0],
            'gamma': [0, 0.1, 0.2, 0.3],
            'reg_alpha': [0, 0.001, 0.005, 0.01, 0.05],
            'reg_lambda': [1, 0.5, 0.1, 0.05],
            'min_child_weight': [1, 3, 5, 7]
        }

        random_search = RandomizedSearchCV(
            estimator=xgb_model,
            param_distributions=param_dist,
            n_iter=6,
            cv=5,
            verbose=2,
            random_state=42,
            n_jobs=-1,
            scoring='neg_mean_squared_error'
        )

        random_search.fit(X_train, y_train)

        best_model = random_search.best_estimator_

        print("\nHyperparameter Tuning Complete.")
        print(f"Best parameters found: {random_search.best_params_}")
        print(f"Best cross-validation score (negative MSE): {random_search.best_score_:.4f}")

        print("\n--- Model Evaluation on Internal Test Set ---")
        y_pred_test = best_model.predict(X_test)

        r2_test = r2_score(y_test, y_pred_test)
        print(f"R-squared (R^2) on Test Set: {r2_test:.4f}")

        mae_test = mean_absolute_error(y_test, y_pred_test)
        print(f"Mean Absolute Error (MAE) on Test Set: {mae_test:.4f} hours")

        mse_test = mean_squared_error(y_test, y_pred_test)
        print(f"Mean Squared Error (MSE) on Test Set: {mse_test:.4f} (hours^2)")

        rmse_test = np.sqrt(mse_test)
        print(f"Root Mean Squared Error (RMSE) on Test Set: {rmse_test:.4f} hours")

        print("\n--- Validation Scoring with New Data ---")

        all_validation_dataframes = []

        print(f"Loading validation data from: {validation_folder_path}")
        for filename in os.listdir(validation_folder_path):
            if filename.endswith('.csv'):
                file_path = os.path.join(validation_folder_path, filename)
                try:
                    df_new = pd.read_csv(file_path)
                    all_validation_dataframes.append(df_new)
                    print(f"Loaded {filename} for validation.")
                except Exception as e:
                    print(f"Error reading {filename} for validation: {e}")

        if all_validation_dataframes:
            combined_validation_df = pd.concat(all_validation_dataframes, ignore_index=True)
            print(f"Successfully combined {len(all_validation_dataframes)} validation CSV files.")
            print(f"Combined Validation DataFrame shape: {combined_validation_df.shape}")

            # Apply advanced preprocessing and feature engineering to validation data
            X_new_processed, y_new_processed = preprocess_and_engineer_features(
                combined_validation_df,
                columns_to_drop,
                lags=3,
                rolling_windows=[5, 10, 20],
                diff_periods=[1, 3],
                ewma_spans=[10, 20]
            )

            # Align columns of X_new_processed with X_train to ensure consistent feature order and presence
            X_new_aligned = X_new_processed.reindex(columns=X_train.columns, fill_value=0)

            if not X_new_aligned.empty and not y_new_processed.empty:
                # Make predictions on the new data using the best found model
                y_pred_new = best_model.predict(X_new_aligned)

                r2_new = r2_score(y_new_processed, y_pred_new)
                print(f"R-squared (R^2) on New Data: {r2_new:.4f}")

                mae_new = mean_absolute_error(y_new_processed, y_pred_new)
                print(f"Mean Absolute Error (MAE) on New Data: {mae_new:.4f} hours")

                mse_new = mean_squared_error(y_new_processed, y_pred_new)
                print(f"Mean Squared Error (MSE) on New Data: {mse_new:.4f} (hours^2)")

                rmse_new = np.sqrt(mse_new)
                print(f"Root Mean Squared Error (RMSE) on New Data: {rmse_new:.4f} hours")
            else:
                print("No valid data found in the validation CSV files after preprocessing and feature engineering.")
        else:
            print(f"No CSV files found in the validation folder: {validation_folder_path}")
        
        model_filename = 'mae_403.joblib'
        try:
            joblib.dump(best_model, model_filename)
            print(f"Model saved successfully to {model_filename}")
        except Exception as e:
            print(f"Error saving model to {model_filename}: {e}")


else:
    print(f"No CSV files found in the training folder: {training_folder_path}")