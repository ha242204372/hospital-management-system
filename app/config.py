"""Application configuration, directory paths, and role constants."""
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(ROOT_DIR, "database")
os.makedirs(DB_DIR, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, "hospital.db")
LEGACY_DB_PATH = os.path.join(ROOT_DIR, "hospital.db")

VIEWS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "views")
TEMPLATES_DIR = os.path.join(VIEWS_DIR, "templates")
STATIC_DIR = os.path.join(ROOT_DIR, "static")

HOSPITAL_NAME = "MediCare General Hospital"
ROLES = ["Admin", "Doctor", "Nurse", "Receptionist", "Pharmacist", "Lab Technician", "Accountant", "Patient"]
ALL = ROLES
GENDERS = ["Male", "Female", "Other"]
BLOODS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]


class ApiError(Exception):
    """Structured HTTP API exception."""
    def __init__(self, code, msg):
        self.code, self.msg = code, msg
