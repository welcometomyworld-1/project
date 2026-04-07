import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def generate_dummy_data(n_samples=2000):
    case_types = ['Criminal', 'Civil', 'Family', 'Commercial', 'Traffic']
    legal_keywords = {
        'Urgent': ['murder', 'bail', 'rape', 'threat', 'kidnap', 'fraud', 'medical', 'emergency', 'protection'],
        'Complex': ['property', 'dispute', 'corporate', 'merger', 'tax', 'inheritance', 'intellectual', 'contract'],
        'Routine': ['fine', 'traffic', 'permit', 'noise', 'license', 'divorce', 'mutual']
    }
    
    data = []
    start_date = datetime(2018, 1, 1)
    
    for i in range(n_samples):
        case_id = f"CASE-{1000 + i}"
        case_type = random.choice(case_types)
        filing_date = start_date + timedelta(days=random.randint(0, 2000))
        
        # New feature: Keyword detection simulation
        category = random.choice(list(legal_keywords.keys()))
        keyword = random.choice(legal_keywords[category])
        case_description = f"Case related to {keyword} in {case_type} matters."
        
        # Impact features
        social_impact = random.randint(1, 5) # 5 = high social impact
        past_delays = random.randint(0, 10)
        
        # Duration logic: more complex
        base_dur = {'Criminal': 300, 'Civil': 400, 'Family': 200, 'Commercial': 500, 'Traffic': 60}[case_type]
        cat_multiplier = {'Urgent': 0.7, 'Complex': 1.5, 'Routine': 1.0}[category]
        
        duration = (base_dur * cat_multiplier) + (social_impact * 20) + (past_delays * 15) + random.randint(-50, 50)
        duration = max(30, int(duration))
        
        # Priority logic: more advanced
        urgency_score = 1 if category == 'Routine' else (3 if category == 'Complex' else 5)
        if social_impact >= 4: urgency_score += 1
        
        if urgency_score >= 5:
            priority = 'High'
        elif urgency_score >= 3:
            priority = 'Medium'
        else:
            priority = 'Low'
            
        data.append({
            'case_id': case_id,
            'case_type': case_type,
            'description': case_description,
            'urgency_level': urgency_score,
            'social_impact': social_impact,
            'past_delays': past_delays,
            'duration': duration,
            'priority': priority
        })
        
    df = pd.DataFrame(data)
    df.to_csv('backend/data/cases_v2.csv', index=False)
    print(f"Generated {n_samples} advanced samples in backend/data/cases_v2.csv")

if __name__ == "__main__":
    generate_dummy_data()
