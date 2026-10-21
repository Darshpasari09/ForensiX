USE forensix;

CREATE TABLE USERS (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    badge_id VARCHAR(30) UNIQUE,
    role ENUM('ADMIN', 'INVESTIGATOR', 'FORENSIC_ANALYST', 'VIEWER')
         NOT NULL DEFAULT 'INVESTIGATOR',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE CASES (
    case_id INT AUTO_INCREMENT PRIMARY KEY,
    case_number VARCHAR(30) NOT NULL UNIQUE,
    case_title VARCHAR(150) NOT NULL,
    description TEXT,
    crime_type VARCHAR(100) NOT NULL,
    priority ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
             NOT NULL DEFAULT 'MEDIUM',
    status ENUM('OPEN', 'UNDER_INVESTIGATION', 'SOLVED', 'CLOSED')
            NOT NULL DEFAULT 'OPEN',
    incident_date DATE NOT NULL,
    report_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    lead_investigator_id INT,
    created_by INT NOT NULL,

    CONSTRAINT fk_case_lead
        FOREIGN KEY (lead_investigator_id)
        REFERENCES USERS(user_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    CONSTRAINT fk_case_creator
        FOREIGN KEY (created_by)
        REFERENCES USERS(user_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE TABLE PERSONS (
    person_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    date_of_birth DATE,
    gender VARCHAR(20),
    phone VARCHAR(20),
    email VARCHAR(100),
    address VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE CASE_PERSON (
    case_id INT NOT NULL,
    person_id INT NOT NULL,
    person_role ENUM('SUSPECT', 'VICTIM', 'WITNESS', 'INVESTIGATOR')
                NOT NULL,
    notes TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (case_id, person_id, person_role),

    CONSTRAINT fk_cp_case
        FOREIGN KEY (case_id)
        REFERENCES CASES(case_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_cp_person
        FOREIGN KEY (person_id)
        REFERENCES PERSONS(person_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

CREATE TABLE LOCATIONS (
    location_id INT AUTO_INCREMENT PRIMARY KEY,
    address VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100),
    postal_code VARCHAR(20),
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7),
    precinct VARCHAR(100)
);

CREATE TABLE CASE_LOCATIONS (
    case_id INT NOT NULL,
    location_id INT NOT NULL,
    location_type VARCHAR(50) DEFAULT 'INCIDENT',

    PRIMARY KEY (case_id, location_id),

    CONSTRAINT fk_cl_case
        FOREIGN KEY (case_id)
        REFERENCES CASES(case_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_cl_location
        FOREIGN KEY (location_id)
        REFERENCES LOCATIONS(location_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

CREATE TABLE PERSON_RELATIONSHIPS (
    relationship_id INT AUTO_INCREMENT PRIMARY KEY,
    person_id_1 INT NOT NULL,
    person_id_2 INT NOT NULL,
    relationship_type VARCHAR(50) NOT NULL,
    notes TEXT,

    CONSTRAINT fk_pr_person1
        FOREIGN KEY (person_id_1)
        REFERENCES PERSONS(person_id),

    CONSTRAINT fk_pr_person2
        FOREIGN KEY (person_id_2)
        REFERENCES PERSONS(person_id),

    CONSTRAINT chk_different_persons
        CHECK (person_id_1 <> person_id_2)
);

CREATE TABLE EVIDENCE (
    evidence_id INT AUTO_INCREMENT PRIMARY KEY,
    case_id INT NOT NULL,
    evidence_code VARCHAR(30) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    collection_datetime DATETIME,
    collected_by INT,
    status ENUM('COLLECTED', 'IN_LAB', 'STORED', 'RELEASED', 'DESTROYED')
            NOT NULL DEFAULT 'COLLECTED',
    storage_location VARCHAR(255),
    serial_number VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_evidence_case
        FOREIGN KEY (case_id)
        REFERENCES CASES(case_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    CONSTRAINT fk_evidence_collector
        FOREIGN KEY (collected_by)
        REFERENCES USERS(user_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

CREATE TABLE EVIDENCE_CUSTODY (
    custody_id INT AUTO_INCREMENT PRIMARY KEY,
    evidence_id INT NOT NULL,
    from_user_id INT,
    to_user_id INT NOT NULL,
    transfer_datetime DATETIME DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,

    CONSTRAINT fk_custody_evidence
        FOREIGN KEY (evidence_id)
        REFERENCES EVIDENCE(evidence_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    CONSTRAINT fk_custody_from_user
        FOREIGN KEY (from_user_id)
        REFERENCES USERS(user_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    CONSTRAINT fk_custody_to_user
        FOREIGN KEY (to_user_id)
        REFERENCES USERS(user_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE
);

CREATE TABLE FORENSIC_TESTS (
    test_id INT AUTO_INCREMENT PRIMARY KEY,
    evidence_id INT NOT NULL,
    test_type VARCHAR(100) NOT NULL,
    requested_by INT,
    analyst_id INT,
    status ENUM('REQUESTED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')
            NOT NULL DEFAULT 'REQUESTED',
    request_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_date DATETIME,
    result TEXT,
    conclusion TEXT,

    CONSTRAINT fk_test_evidence
        FOREIGN KEY (evidence_id)
        REFERENCES EVIDENCE(evidence_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    CONSTRAINT fk_test_requester
        FOREIGN KEY (requested_by)
        REFERENCES USERS(user_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE,

    CONSTRAINT fk_test_analyst
        FOREIGN KEY (analyst_id)
        REFERENCES USERS(user_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

CREATE TABLE DIGITAL_FILES (
    file_id INT AUTO_INCREMENT PRIMARY KEY,
    evidence_id INT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    file_type VARCHAR(50),
    file_size BIGINT,
    checksum VARCHAR(128),
    uploaded_by INT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_file_evidence
        FOREIGN KEY (evidence_id)
        REFERENCES EVIDENCE(evidence_id)
        ON DELETE RESTRICT
        ON UPDATE CASCADE,

    CONSTRAINT fk_file_uploader
        FOREIGN KEY (uploaded_by)
        REFERENCES USERS(user_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

CREATE TABLE CASE_TIMELINE (
    timeline_id INT AUTO_INCREMENT PRIMARY KEY,
    case_id INT NOT NULL,
    event_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    created_by INT,

    CONSTRAINT fk_timeline_case
        FOREIGN KEY (case_id)
        REFERENCES CASES(case_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_timeline_user
        FOREIGN KEY (created_by)
        REFERENCES USERS(user_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

CREATE TABLE INVESTIGATION_TASKS (
    task_id INT AUTO_INCREMENT PRIMARY KEY,
    case_id INT NOT NULL,
    assigned_to INT,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    priority ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
             NOT NULL DEFAULT 'MEDIUM',
    status ENUM('PENDING', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')
            NOT NULL DEFAULT 'PENDING',
    due_date DATE,
    completed_at DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_task_case
        FOREIGN KEY (case_id)
        REFERENCES CASES(case_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_task_user
        FOREIGN KEY (assigned_to)
        REFERENCES USERS(user_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

CREATE TABLE CASE_RELATIONSHIPS (
    relationship_id INT AUTO_INCREMENT PRIMARY KEY,
    case_id_1 INT NOT NULL,
    case_id_2 INT NOT NULL,
    relationship_type VARCHAR(100) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_cr_case1
        FOREIGN KEY (case_id_1)
        REFERENCES CASES(case_id),

    CONSTRAINT fk_cr_case2
        FOREIGN KEY (case_id_2)
        REFERENCES CASES(case_id),

    CONSTRAINT chk_different_cases
        CHECK (case_id_1 <> case_id_2)
);

CREATE TABLE AUDIT_LOGS (
    audit_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    table_name VARCHAR(100) NOT NULL,
    record_id INT,
    action VARCHAR(50) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_audit_user
        FOREIGN KEY (user_id)
        REFERENCES USERS(user_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);