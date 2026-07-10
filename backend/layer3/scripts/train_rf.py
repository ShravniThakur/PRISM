import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib
import os

def train_central_brain():
    data_path = '../data/synthetic_rf_data.csv'
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Could not find dataset at {data_path}. Run generate_dataset.py first.")
        
    df = pd.read_csv(data_path)
    
    # Features and Target
    X = df[['text_threat_score', 'video_fake_score', 'audio_fake_score', 'domain_age_days', 'is_authenticated_sender']]
    y = df['is_malicious']
    
    # Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print("Training Random Forest Classifier...")
    # Initialize Random Forest
    rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    
    # Train
    rf.fit(X_train, y_train)
    
    # Evaluate
    y_pred = rf.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\nModel Accuracy: {accuracy:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['Safe', 'Malicious']))
    
    # Save Model
    os.makedirs('../models', exist_ok=True)
    model_path = '../models/rf_model.joblib'
    joblib.dump(rf, model_path)
    print(f"\nModel saved to {model_path}")

if __name__ == "__main__":
    train_central_brain()
