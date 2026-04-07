import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
import joblib
import os

def train_advanced_models():
    # Load advanced data
    df = pd.read_csv('backend/data/cases_v2.csv')
    
    # Preprocessing
    le_type = LabelEncoder()
    df['case_type_encoded'] = le_type.fit_transform(df['case_type'])
    
    le_priority = LabelEncoder()
    df['priority_encoded'] = le_priority.fit_transform(df['priority'])
    
    # NLP Preprocessing (TF-IDF for description)
    tfidf = TfidfVectorizer(max_features=100)
    X_text = tfidf.fit_transform(df['description']).toarray()
    
    # Feature engineering for duration
    X_features = df[['case_type_encoded', 'urgency_level', 'social_impact', 'past_delays']].values
    X_combined = np.hstack((X_features, X_text))
    
    y_duration = df['duration']
    y_priority = df['priority_encoded']
    
    # Split
    X_train_dur, X_test_dur, y_train_dur, y_test_dur = train_test_split(X_combined, y_duration, test_size=0.2, random_state=42)
    X_train_pri, X_test_pri, y_train_pri, y_test_pri = train_test_split(X_combined, y_priority, test_size=0.2, random_state=42)
    
    # Advanced Regressor: Gradient Boosting for Duration
    duration_model = GradientBoostingRegressor(n_estimators=200, learning_rate=0.1, max_depth=5, random_state=42)
    duration_model.fit(X_train_dur, y_train_dur)
    
    # Advanced Classifier: RF with more depth for Priority
    priority_model = RandomForestClassifier(n_estimators=200, max_depth=10, random_state=42)
    priority_model.fit(X_train_pri, y_train_pri)
    
    # Save
    if not os.path.exists('backend/models'): os.makedirs('backend/models')
        
    joblib.dump(duration_model, 'backend/models/duration_model_v2.joblib')
    joblib.dump(priority_model, 'backend/models/priority_model_v2.joblib')
    joblib.dump(le_type, 'backend/models/le_type_v2.joblib')
    joblib.dump(le_priority, 'backend/models/le_priority_v2.joblib')
    joblib.dump(tfidf, 'backend/models/tfidf_v2.joblib')
    
    print("Advanced Models saved to backend/models/")
    print(f"Duration Model R2: {duration_model.score(X_test_dur, y_test_dur):.4f}")
    print(f"Priority Model Acc: {priority_model.score(X_test_pri, y_test_pri):.4f}")

if __name__ == "__main__":
    train_advanced_models()
