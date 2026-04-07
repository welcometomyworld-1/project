import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
import joblib
import os

def train_models():
    # Load data
    df = pd.read_csv('backend/data/cases.csv')
    
    # Preprocessing
    # 1. Label encode case_type
    le_type = LabelEncoder()
    df['case_type_encoded'] = le_type.fit_transform(df['case_type'])
    
    # 2. Label encode priority
    le_priority = LabelEncoder()
    df['priority_encoded'] = le_priority.fit_transform(df['priority'])
    
    # Features for duration prediction
    X_duration = df[['case_type_encoded', 'urgency', 'complexity', 'past_delays']]
    y_duration = df['duration']
    
    # Features for priority scoring
    X_priority = df[['case_type_encoded', 'urgency', 'complexity']]
    y_priority = df['priority_encoded']
    
    # Split data
    X_train_dur, X_test_dur, y_train_dur, y_test_dur = train_test_split(X_duration, y_duration, test_size=0.2, random_state=42)
    X_train_pri, X_test_pri, y_train_pri, y_test_pri = train_test_split(X_priority, y_priority, test_size=0.2, random_state=42)
    
    # Train Duration Prediction Model (Random Forest Regressor)
    duration_model = RandomForestRegressor(n_estimators=100, random_state=42)
    duration_model.fit(X_train_dur, y_train_dur)
    
    # Train Priority Scoring Model (Random Forest Classifier)
    priority_model = RandomForestClassifier(n_estimators=100, random_state=42)
    priority_model.fit(X_train_pri, y_train_pri)
    
    # Save models and encoders
    if not os.path.exists('backend/models'):
        os.makedirs('backend/models')
        
    joblib.dump(duration_model, 'backend/models/duration_model.joblib')
    joblib.dump(priority_model, 'backend/models/priority_model.joblib')
    joblib.dump(le_type, 'backend/models/le_type.joblib')
    joblib.dump(le_priority, 'backend/models/le_priority.joblib')
    
    print("Models and encoders saved to backend/models/")
    print(f"Duration Model Score: {duration_model.score(X_test_dur, y_test_dur):.4f}")
    print(f"Priority Model Score: {priority_model.score(X_test_pri, y_test_pri):.4f}")

if __name__ == "__main__":
    train_models()
