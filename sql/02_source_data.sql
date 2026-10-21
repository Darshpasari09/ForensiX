USE forensix;

CREATE TABLE CHICAGO_CRIME_DATA (
    source_id BIGINT PRIMARY KEY,
    case_number VARCHAR(30),
    incident_date DATETIME,
    block VARCHAR(255),
    iucr VARCHAR(20),
    primary_type VARCHAR(100),
    description VARCHAR(255),
    location_description VARCHAR(255),
    arrest BOOLEAN,
    domestic BOOLEAN,
    beat VARCHAR(20),
    district VARCHAR(20),
    ward VARCHAR(20),
    community_area VARCHAR(20),
    fbi_code VARCHAR(20),
    x_coordinate DECIMAL(12,4),
    y_coordinate DECIMAL(12,4),
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7)
);