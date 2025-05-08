CREATE DATABASE IF NOT EXISTS prescription;
USE prescription;

CREATE TABLE IF NOT EXISTS patients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255),
    age INT,
    weight FLOAT,
    height FLOAT,
    allergies TEXT,
    medical_history TEXT
);

CREATE TABLE IF NOT EXISTS prescriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT,
    ai_summary TEXT,
    treatment_options TEXT,
    medication_recommendations TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(id)
);
