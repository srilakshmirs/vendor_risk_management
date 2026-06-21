import csv
import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DB_URL = "postgresql+psycopg://vrm:vrm@localhost:5432/vrm"
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db = SessionLocal()

# Get vendor map
vendors = db.execute(text("SELECT vendor_id, id FROM vendors")).fetchall()
vendor_map = {row[0]: row[1] for row in vendors}

# Read labels
labels_path = "../../data/vendor_labels.csv"
with open(labels_path, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        vid_str = row["vendor_id"]
        if vid_str not in vendor_map:
            continue
            
        vid_id = vendor_map[vid_str]
        severity = row["severity"] or "NONE"
        anomaly = row["anomaly_type"] or "NONE"
        
        # Determine score
        if severity == "CRITICAL":
            score = 95
            traffic = "Red"
        elif severity == "HIGH":
            score = 85
            traffic = "Red"
        elif severity == "MEDIUM":
            score = 65
            traffic = "Yellow"
        elif severity == "LOW":
            score = 45
            traffic = "Green"
        else:
            score = 25
            traffic = "Green"
            
        components_json = json.dumps({})
        rules_json = json.dumps([])
        
        # Check if exists
        existing = db.execute(text("SELECT id FROM risk_assessments WHERE vendor_id = :v"), {"v": vid_id}).fetchone()
        
        if existing:
            db.execute(text("""
                UPDATE risk_assessments 
                SET score=:score, traffic_light=:traffic, severity=:severity, anomaly_type=:anomaly, components=:components, narrative=:narrative, triggered_rules=:rules
                WHERE vendor_id=:v
            """), {
                "score": score, "traffic": traffic, "severity": severity, "anomaly": anomaly, 
                "components": components_json, "narrative": "Generated from ground truth labels.", 
                "rules": rules_json, "v": vid_id
            })
        else:
            db.execute(text("""
                INSERT INTO risk_assessments (vendor_id, score, traffic_light, severity, anomaly_type, components, narrative, triggered_rules, model_version, created_at, updated_at)
                VALUES (:v, :score, :traffic, :severity, :anomaly, :components, :narrative, :rules, 'v1.0', current_timestamp, current_timestamp)
            """), {
                "score": score, "traffic": traffic, "severity": severity, "anomaly": anomaly, 
                "components": components_json, "narrative": "Generated from ground truth labels.", 
                "rules": rules_json, "v": vid_id
            })

db.commit()
db.close()
print("Successfully injected ground truth assessments for all vendors into Postgres!")
