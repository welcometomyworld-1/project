import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def generate_real_case_dataset(n_samples=2500):
    case_types = ['Criminal', 'Civil', 'Family', 'Commercial', 'Traffic']
    categories = ['High Stakes', 'Public Interest', 'Routine', 'Financial', 'Personal']
    
    data = []
    today = datetime.now()
    
    for i in range(n_samples):
        case_id = f"CASE-{2026}-{1000 + i}"
        case_type = random.choice(case_types)
        category = random.choice(categories)
        
        # Case Age: Random filing date from 1 to 3650 days ago
        days_ago = random.randint(1, 3650)
        filing_date = today - timedelta(days=days_ago)
        case_age_days = days_ago
        
        # Urgency Level (1-5)
        urgency = random.randint(1, 5)
        if case_type == 'Criminal' and urgency < 3: urgency += 1
        if case_age_days > 1825: urgency = min(5, urgency + 1) # Older cases become more urgent
        
        # Duration Logic
        base_dur = {
            'Criminal': 400, 'Civil': 500, 'Family': 300, 'Commercial': 600, 'Traffic': 90
        }[case_type]
        
        # Category influence on duration
        cat_mult = {
            'High Stakes': 1.4, 'Public Interest': 1.2, 'Routine': 0.8, 'Financial': 1.1, 'Personal': 0.9
        }[category]
        
        # Predicted Duration calculation
        duration = (base_dur * cat_mult) + (urgency * 30) - (case_age_days * 0.05) + random.randint(-50, 50)
        duration = max(30, int(duration))
        
        # Priority Logic (High/Medium/Low)
        if urgency >= 4 or (case_type == 'Criminal' and urgency >= 3) or case_age_days > 2500:
            priority = 'High'
        elif urgency >= 2 or case_age_days > 1000:
            priority = 'Medium'
        else:
            priority = 'Low'
            
        data.append({
            'case_id': case_id,
            'case_type': case_type,
            'category': category,
            'case_age_days': case_age_days,
            'urgency': urgency,
            'filing_date': filing_date.strftime('%Y-%m-%d'),
            'duration': duration,
            'priority': priority,
            'status': 'Pending' if random.random() > 0.2 else 'Resolved'
        })
        
    df = pd.DataFrame(data)
    df.to_csv('backend/data/cases_v3.csv', index=False)
    print(f"Generated {n_samples} real-study samples in backend/data/cases_v3.csv")

if __name__ == "__main__":
    generate_real_case_dataset()
