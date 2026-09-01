#!/usr/bin/env python3
"""
Download all VTI files from sweep results.
"""
from aiida import load_profile, orm
import pandas as pd
import os

load_profile()

# Read results
df = pd.read_csv('sweep_results.csv')

# Create output directory
os.makedirs('vti_files', exist_ok=True)

for idx, row in df.iterrows():
    vti_pk = row['vti_file_pk']
    vti = orm.load_node(vti_pk)
    
    # Create descriptive filename
    filename = (f"structure_cellR{row['cell_radius']}_"
                f"res{row['resolution']}_"
                f"seed{row['random_seed']}_"
                f"por{row['actual_porosity']:.4f}.vti")
    
    filepath = os.path.join('vti_files', filename)
    
    # Write VTI file
    with open(filepath, 'w') as f:
        f.write(vti.get_content())
    
    print(f"Downloaded: {filename}")

print(f"\nDownloaded {len(df)} VTI files to vti_files/")
