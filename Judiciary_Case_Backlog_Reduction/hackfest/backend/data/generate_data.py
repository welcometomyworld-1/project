import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def generate_dummy_data(n_samples=1000):
    case_types = ['Criminal', 'Civil', 'Family', 'Commercial', 'Traffic']
    priorities = ['Low', 'Medium', 'High']
    
    data = []
    
    start_date = datetime(2020, 1, 1)
    
    for i in range(n_samples):
        case_id = f"CASE-{1000 + i}"
        case_type = random.choice(case_types)
        filing_date = start_date + timedelta(days=random.randint(0, 1000))
        urgency = random.randint(1, 5)
        complexity = random.randint(1, 5)
        past_delays = random.randint(0, 5)
        
        # Calculate duration based on type, complexity, and urgency
        base_duration = {
            'Criminal': 300,
            'Civil': 400,
            'Family': 200,
            'Commercial': 500,
            'Traffic': 60
        }
        
        duration = base_duration[case_type] + (complexity * 50) - (urgency * 20) + (past_delays * 30) + random.randint(-50, 50)
        duration = max(30, duration) # Ensure at least 30 days
        
        # Determine priority based on type and urgency
        if urgency >= 4 or (case_type == 'Criminal' and urgency >= 3):
            priority = 'High'
        elif urgency >= 2:
            priority = 'Medium'
        else:
            priority = 'Low'
            
        data.append({
            'case_id': case_id,
            'case_type': case_type,
            'filing_date': filing_date.strftime('%Y-%m-%d'),
            'urgency': urgency,
            'complexity': complexity,
            'past_delays': past_delays,
            'duration': duration,
            'priority': priority
        })
        
    df = pd.DataFrame(data)
    df.to_csv('backend/data/cases.csv', index=False)
    print(f"Generated {n_samples} samples and saved to backend/data/cases.csv")

if __name__ == "__main__":
    generate_dummy_data()
