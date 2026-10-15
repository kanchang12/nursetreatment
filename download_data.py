import os
import torch
import pandas as pd

# --- PATCH FOR PYTORCH 2.6+ WEIGHTS_ONLY CHANGE ---
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load
# --------------------------------------------------

DATA_DIR = "data"
RAW_DIR = os.path.join(DATA_DIR, "raw")
SYNTHEA_CSV_DIR = os.path.join(DATA_DIR, "synthea_csv")
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(SYNTHEA_CSV_DIR, exist_ok=True)

def download_ogbl_ddi():
    print("[-] Checking/Loading OGBL-DDI dataset via OGB library...")
    try:
        from ogb.linkproppred import LinkPropPredDataset
        dataset = LinkPropPredDataset(name='ogbl-ddi', root=os.path.join(DATA_DIR, 'ogb_ddi'))
        print("[+] OGBL-DDI graph dataset successfully loaded and ready.")
    except Exception as e:
        print(f"[!] Error loading OGBL-DDI: {e}")

def generate_local_synthetic_patients():
    print("[-] Generating structured local synthetic patient sample (Synthea-format)...")
    
    patients_data = {
        "Id": ["pat-001", "pat-002", "pat-003"],
        "BIRTHDATE": ["1948-04-12", "1955-09-23", "1941-01-15"],
        "FIRST": ["Arthur", "Margaret", "Clive"],
        "LAST": ["Pendleton", "Hughes", "Barker"],
        "GENDER": ["M", "F", "M"],
        "STATE": ["Leeds", "Leeds", "Leeds"]
    }
    
    medications_data = {
        "PATIENT": ["pat-001", "pat-001", "pat-002", "pat-003"],
        "MEDICATION": ["Aspirin", "Ibuprofen", "Lisinopril", "Warfarin"],
        "START": ["2023-01-01", "2024-05-10", "2022-11-01", "2023-08-20"]
    }

    df_patients = pd.DataFrame(patients_data)
    df_meds = pd.DataFrame(medications_data)
    
    df_patients.to_csv(os.path.join(SYNTHEA_CSV_DIR, "patients.csv"), index=False)
    df_meds.to_csv(os.path.join(SYNTHEA_CSV_DIR, "medications.csv"), index=False)
    
    print(f"[+] Local synthetic patient CSV bundles saved to {SYNTHEA_CSV_DIR}")

if __name__ == "__main__":
    print("=== Starting HealthTech Demo Data Setup ===")
    download_ogbl_ddi()
    generate_local_synthetic_patients()
    print("=== Data Setup Complete ===")