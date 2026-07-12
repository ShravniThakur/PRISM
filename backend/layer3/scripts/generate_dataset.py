import pandas as pd
import numpy as np
import os

def generate_synthetic_rf_data(num_samples=10000):
    np.random.seed(42)
    
    # 5 base profiles
    
    # 1. Perfectly Safe (30% of data)
    # Auth sender, old domain (or no URL), low scores
    n1 = int(num_samples * 0.3)
    safe_data = {
        'text_threat_score': np.random.uniform(0.0, 0.2, n1),
        'video_fake_score': np.random.uniform(0.0, 0.1, n1),
        'audio_fake_score': np.random.uniform(0.0, 0.1, n1),
        'domain_age_days': np.random.choice([np.random.randint(365, 3650), -1], size=n1, p=[0.7, 0.3]),
        'is_authenticated_sender': np.ones(n1),
        'is_malicious': np.zeros(n1)
    }
    
    # 2. Blatant Deepfake (20% of data)
    # High video/audio, high text, malicious. Often has NO url (-1) like a WhatsApp forward.
    n2 = int(num_samples * 0.2)
    deepfake_data = {
        'text_threat_score': np.random.uniform(0.6, 1.0, n2),
        'video_fake_score': np.random.uniform(0.8, 1.0, n2),
        'audio_fake_score': np.random.uniform(0.8, 1.0, n2),
        'domain_age_days': np.random.choice([np.random.randint(1, 100), -1], size=n2, p=[0.5, 0.5]),
        'is_authenticated_sender': np.random.choice([0, 1], size=n2, p=[0.8, 0.2]),
        'is_malicious': np.ones(n2)
    }
    
    # 3. Phishing Link (25% of data)
    # High text threat, new domain, no media
    n3 = int(num_samples * 0.25)
    phishing_data = {
        'text_threat_score': np.random.uniform(0.8, 1.0, n3),
        'video_fake_score': np.zeros(n3),
        'audio_fake_score': np.zeros(n3),
        'domain_age_days': np.random.randint(1, 30, n3),
        'is_authenticated_sender': np.zeros(n3),
        'is_malicious': np.ones(n3)
    }
    
    # 4. Hacked Account Phishing (15% of data)
    # Auth sender = 1, but high text threat and low domain age link
    n4 = int(num_samples * 0.15)
    hacked_data = {
        'text_threat_score': np.random.uniform(0.7, 1.0, n4),
        'video_fake_score': np.zeros(n4),
        'audio_fake_score': np.zeros(n4),
        'domain_age_days': np.random.randint(1, 30, n4),
        'is_authenticated_sender': np.ones(n4),
        'is_malicious': np.ones(n4)
    }
    
    # 5. Cheapfake / Partial Deepfake (10% of data)
    # Video high, but audio low (or vice versa), text medium
    n5 = num_samples - n1 - n2 - n3 - n4
    cheapfake_data = {
        'text_threat_score': np.random.uniform(0.3, 0.6, n5),
        'video_fake_score': np.random.uniform(0.7, 1.0, n5),
        'audio_fake_score': np.random.uniform(0.0, 0.3, n5),
        'domain_age_days': np.random.randint(1, 200, n5),
        'is_authenticated_sender': np.zeros(n5),
        'is_malicious': np.ones(n5)
    }
    
    # Combine all
    dfs = [pd.DataFrame(d) for d in [safe_data, deepfake_data, phishing_data, hacked_data, cheapfake_data]]
    final_df = pd.concat(dfs, ignore_index=True)
    
    # Shuffle
    final_df = final_df.sample(frac=1).reset_index(drop=True)
    
    # Add a bit of random noise to everything to prevent overfitting
    final_df['text_threat_score'] += np.random.normal(0, 0.05, num_samples)
    final_df['video_fake_score'] += np.random.normal(0, 0.05, num_samples)
    final_df['audio_fake_score'] += np.random.normal(0, 0.05, num_samples)
    
    # Clip scores between 0 and 1
    for col in ['text_threat_score', 'video_fake_score', 'audio_fake_score']:
        final_df[col] = final_df[col].clip(0, 1)
        
    os.makedirs('../data', exist_ok=True)
    output_path = '../data/synthetic_rf_data.csv'
    final_df.to_csv(output_path, index=False)
    print(f"Generated {num_samples} rows of synthetic training data at {output_path}")

if __name__ == "__main__":
    generate_synthetic_rf_data()
