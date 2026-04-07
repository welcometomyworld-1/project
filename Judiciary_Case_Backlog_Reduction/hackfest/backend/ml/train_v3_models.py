import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import joblib
import os

def train_v3_models():
    # Load V3 data
    df = pd.read_csv('backend/data/cases_v3.csv')
    
    # Preprocessing Encoders
    le_type = LabelEncoder()
    df['case_type_encoded'] = le_type.fit_transform(df['case_type'])
    
    le_cat = LabelEncoder()
    df['category_encoded'] = le_cat.fit_transform(df['category'])
    
    le_priority = LabelEncoder()
    df['priority_encoded'] = le_priority.fit_transform(df['priority'])
    
    # Features: [type, category, age, urgency]
    X = df[['case_type_encoded', 'category_encoded', 'case_age_days', 'urgency']].values
    
    y_dur = df['duration']
    y_pri = df['priority_encoded']
    
    # Split
    X_train, X_test, y_train_dur, y_test_dur = train_test_split(X, y_dur, test_size=0.2, random_state=42)
    _, _, y_train_pri, y_test_pri = train_test_split(X, y_pri, test_size=0.2, random_state=42)
    
    # Model 1: Duration Predictor (Regressor)
    dur_model = RandomForestRegressor(n_estimators=200, random_state=42)
    dur_model.fit(X_train, y_train_dur)
    
    # Model 2: Priority Classifier
    pri_model = RandomForestClassifier(n_estimators=200, random_state=42)
    pri_model.fit(X_train, y_train_pri)
    
    # Save V3 Models
    if not os.path.exists('backend/models'): os.makedirs('backend/models')
    
    joblib.dump(dur_model, 'backend/models/duration_model_v3.joblib')
    joblib.dump(pri_model, 'backend/models/priority_model_v3.joblib')
    joblib.dump(le_type, 'backend/models/le_type_v3.joblib')
    joblib.dump(le_cat, 'backend/models/le_cat_v3.joblib')
    joblib.dump(le_priority, 'backend/models/le_priority_v3.joblib')
    
    print("V3 Models trained and saved successfully!")
    print(f"Duration Score: {dur_model.score(X_test, y_test_dur):.4f}")
    print(f"Priority Score: {pri_model.score(X_test, y_test_pri):.4f}")

if __name__ == "__main__":
    train_v3_models()
