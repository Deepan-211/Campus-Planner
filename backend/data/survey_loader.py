"""
Survey Ingestion and Anonymization Module.
Loads Google Forms CSV survey exports, sanitizes PII (emails, names),
validates responses against valid stands, and computes empirical calibration priors.
"""
from pathlib import Path
from typing import Dict, List, Optional
import csv
import hashlib
import logging
import pandas as pd
from backend.config import load_stands, StandDefinition
from backend.db.session import SessionLocal
from backend.db.models import SurveyResponseModel

logger = logging.getLogger(__name__)


class SurveyProcessor:
    """
    Parses, validates, and anonymizes campus survey data for any configured campus.
    Extracts empirical OD transition probabilities and commute hour priors.
    """

    def __init__(
        self,
        valid_stands: Optional[List[StandDefinition]] = None,
        campus_id: Optional[str] = None,
    ):
        self.campus_id = campus_id
        self.stands = valid_stands or load_stands(campus_id=campus_id)
        self.valid_stand_ids = {s.id for s in self.stands}
        self.alias_map: Dict[str, str] = {}
        self._build_alias_map()

    def _build_alias_map(self):
        """Construct stand name alias map dynamically from stand IDs and names."""
        for s in self.stands:
            self.alias_map[s.id.lower()] = s.id
            self.alias_map[s.name.lower()] = s.id
            self.alias_map[s.name.lower().replace("&", "and")] = s.id
            self.alias_map[s.name.lower().replace("and", "&")] = s.id

        # V.S.B. Engineering College, Karur aliases
        vsb_aliases = {
            "main entrance": "VSB-01",
            "bus arch": "VSB-01",
            "main entrance & bus arch": "VSB-01",
            "bus stop": "VSB-01",
            "gate": "VSB-01",
            "entrance": "VSB-01",
            "admin": "VSB-02",
            "cse": "VSB-02",
            "it block": "VSB-02",
            "admin & cse/it block": "VSB-02",
            "computer science": "VSB-02",
            "admin block": "VSB-02",
            "mech": "VSB-03",
            "eee": "VSB-03",
            "mechanical": "VSB-03",
            "mechanical & eee block": "VSB-03",
            "electrical": "VSB-03",
            "library": "VSB-04",
            "central library": "VSB-04",
            "central library & audi": "VSB-04",
            "audi": "VSB-04",
            "auditorium": "VSB-04",
            "canteen": "VSB-05",
            "cafeteria": "VSB-05",
            "food court": "VSB-05",
            "cafeteria & food court": "VSB-05",
            "mess": "VSB-05",
            "hostel": "VSB-06",
            "hostel complex": "VSB-06",
            "hostel complex & depo": "VSB-06",
            "depo": "VSB-06",
            "dorm": "VSB-06",
            "boys hostel": "VSB-06",
            "girls hostel": "VSB-06",
        }
        for alias, stand_id in vsb_aliases.items():
            if stand_id in self.valid_stand_ids:
                self.alias_map[alias] = stand_id

        # Berkeley presets aliases
        berkeley_aliases = {
            "unit 1": "ST-01",
            "unit 1 residence halls": "ST-01",
            "bart downtown plaza": "ST-01",
            "unit 2": "ST-02",
            "unit 2 residence halls": "ST-02",
            "mlk student union": "ST-02",
            "foothill": "ST-03",
            "foothill / stern halls": "ST-03",
            "north gate hall": "ST-03",
            "soda": "ST-04",
            "soda & cory halls": "ST-04",
            "soda hall": "ST-04",
            "dwinelle": "ST-05",
            "dwinelle & wheeler halls": "ST-05",
            "wheeler hall": "ST-05",
            "moffitt": "ST-06",
            "moffitt & doe libraries": "ST-06",
            "doe library": "ST-06",
            "haas": "ST-07",
            "haas school of business": "ST-07",
            "unit 1 / underhill field": "ST-07",
        }
        for alias, stand_id in berkeley_aliases.items():
            if stand_id in self.valid_stand_ids:
                self.alias_map[alias] = stand_id

    def resolve_stand_id(self, raw_name: str) -> Optional[str]:
        cleaned = str(raw_name).strip().lower()
        if cleaned in self.alias_map:
            return self.alias_map[cleaned]
        for alias, stand_id in self.alias_map.items():
            if alias in cleaned or cleaned in alias:
                return stand_id
        return None

    def anonymize_id(self, raw_identifier: str) -> str:
        """Hash any raw ID with SHA-256 to ensure zero PII leaks."""
        h = hashlib.sha256(raw_identifier.strip().encode("utf-8")).hexdigest()[:12]
        return f"ANON-{h.upper()}"

    def parse_csv(self, file_path: Path) -> List[dict]:
        """
        Ingest and validate survey CSV rows.
        Expected columns: [RespondentId/Email, HomeStand, DestStand, MorningHour, EveningHour, CycleInRain, MaxWalkMins]
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Survey CSV file not found: {file_path}")

        df = pd.read_csv(file_path)
        valid_records = []

        for idx, row in df.iterrows():
            raw_id = str(row.get("email", row.get("id", f"row_{idx}")))
            anon_id = self.anonymize_id(raw_id)

            home_stand = self.resolve_stand_id(str(row.get("home_stand", "")))
            dest_stand = self.resolve_stand_id(str(row.get("dest_stand", "")))

            if not home_stand or not dest_stand:
                continue

            try:
                m_hour = int(row.get("morning_commute_hour", 8))
                e_hour = int(row.get("evening_commute_hour", 17))
                m_hour = max(6, min(12, m_hour))
                e_hour = max(14, min(22, e_hour))
            except (ValueError, TypeError):
                m_hour, e_hour = 8, 17

            rain_val = str(row.get("cycle_in_rain", "no")).strip().lower()
            cycle_in_rain = rain_val in ["yes", "true", "1", "y"]

            try:
                max_walk = float(row.get("acceptable_walk_minutes", 5.0))
                max_walk = max(1.0, min(30.0, max_walk))
            except (ValueError, TypeError):
                max_walk = 5.0

            valid_records.append({
                "anonymized_id": anon_id,
                "home_stand_id": home_stand,
                "primary_dest_stand_id": dest_stand,
                "morning_commute_hour": m_hour,
                "evening_commute_hour": e_hour,
                "cycle_in_rain": cycle_in_rain,
                "acceptable_walk_minutes": max_walk,
            })

        logger.info("Successfully ingested %d valid survey responses from %s", len(valid_records), file_path)
        return valid_records

    def compute_empirical_od_matrix(self, records: List[dict]) -> Dict[str, Dict[str, float]]:
        """Compute empirical origin-destination transition frequencies from survey."""
        matrix: Dict[str, Dict[str, float]] = {
            s: {d: 0.0 for d in self.valid_stand_ids if d != s}
            for s in self.valid_stand_ids
        }
        for rec in records:
            o, d = rec["home_stand_id"], rec["primary_dest_stand_id"]
            if o in matrix and d in matrix[o]:
                matrix[o][d] += 1.0

        # Normalize rows to probabilities
        for o in matrix:
            total = sum(matrix[o].values())
            if total > 0:
                for d in matrix[o]:
                    matrix[o][d] /= total
            else:
                uniform = 1.0 / len(matrix[o]) if matrix[o] else 0.0
                for d in matrix[o]:
                    matrix[o][d] = uniform

        return matrix

    def compute_empirical_commute_hours(self, records: List[dict]) -> Dict[str, Dict[int, float]]:
        """Compute morning and evening departure hour distribution from survey."""
        m_counts: Dict[int, float] = {}
        e_counts: Dict[int, float] = {}

        for rec in records:
            m = rec["morning_commute_hour"]
            e = rec["evening_commute_hour"]
            m_counts[m] = m_counts.get(m, 0.0) + 1.0
            e_counts[e] = e_counts.get(e, 0.0) + 1.0

        m_tot = sum(m_counts.values()) or 1.0
        e_tot = sum(e_counts.values()) or 1.0

        return {
            "morning": {h: round(c / m_tot, 3) for h, c in sorted(m_counts.items())},
            "evening": {h: round(c / e_tot, 3) for h, c in sorted(e_counts.items())},
        }

    def compute_rain_willingness_pct(self, records: List[dict]) -> float:
        """Compute percentage of riders willing to cycle in rainy conditions."""
        if not records:
            return 30.0
        rain_yes = sum(1 for r in records if r["cycle_in_rain"])
        return round((rain_yes / len(records)) * 100.0, 1)

    def save_to_db(self, records: List[dict]):
        """Persist anonymized records to SQLite."""
        db = SessionLocal()
        try:
            for rec in records:
                existing = db.query(SurveyResponseModel).filter_by(anonymized_id=rec["anonymized_id"]).first()
                if not existing:
                    db.add(SurveyResponseModel(**rec))
            db.commit()
        finally:
            db.close()


def generate_sample_survey_csv(
    output_path: Path,
    num_responses: int = 150,
    campus_id: str = "berkeley",
) -> Path:
    """
    Generates a realistic anonymized calibration survey CSV representing
    campus commuting patterns (supports V.S.B. Karur and UC Berkeley).
    """
    import random
    random.seed(42)

    if campus_id == "vsb_karur":
        residential_stands = ["Hostel Complex & Depo", "Main Entrance & Bus Arch"]
        academic_stands = [
            "Admin & CSE/IT Block",
            "Mechanical & EEE Block",
            "Central Library & Audi",
            "Cafeteria & Food Court",
        ]
        email_domain = "vsb.ac.in"
        m_hours = [8, 9]
        m_weights = [0.75, 0.25]
        e_hours = [16, 17, 18]
        e_weights = [0.55, 0.35, 0.10]
    else:
        residential_stands = ["Unit 1 Residence Halls", "Unit 2 Residence Halls", "Foothill / Stern Halls"]
        academic_stands = [
            "Soda & Cory Halls (EECS)",
            "Dwinelle & Wheeler Halls",
            "Moffitt & Doe Libraries",
            "Haas School of Business",
        ]
        email_domain = "berkeley.edu"
        m_hours = [8, 9, 10]
        m_weights = [0.5, 0.35, 0.15]
        e_hours = [16, 17, 18, 19]
        e_weights = [0.2, 0.45, 0.25, 0.1]

    records = []
    for i in range(num_responses):
        home = random.choice(residential_stands)
        dest = random.choice(academic_stands)
        m_hour = random.choices(m_hours, weights=m_weights)[0]
        e_hour = random.choices(e_hours, weights=e_weights)[0]
        rain = random.choices([False, True], weights=[0.72, 0.28])[0]
        walk_mins = random.choices([3.0, 5.0, 8.0, 10.0], weights=[0.25, 0.50, 0.15, 0.10])[0]

        records.append({
            "id": f"student_{i+1000}@{email_domain}",
            "home_stand": home,
            "dest_stand": dest,
            "morning_commute_hour": m_hour,
            "evening_commute_hour": e_hour,
            "cycle_in_rain": "yes" if rain else "no",
            "acceptable_walk_minutes": walk_mins
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

    return output_path
