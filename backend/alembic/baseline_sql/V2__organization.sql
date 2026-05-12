-- V2: 組織結構（departments、projects）+ users 擴充。

CREATE TABLE departments (
    pid                 BIGSERIAL PRIMARY KEY,
    department_uid      UUID         NOT NULL UNIQUE,
    code                VARCHAR(32)  NOT NULL,
    name                VARCHAR(128) NOT NULL,
    description         TEXT,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted          BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX uq_departments_code ON departments (lower(code)) WHERE is_deleted = FALSE;

CREATE TRIGGER trg_departments_updated_at
BEFORE UPDATE ON departments
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE projects (
    pid                 BIGSERIAL PRIMARY KEY,
    project_uid         UUID         NOT NULL UNIQUE,
    department_uid      UUID         NOT NULL REFERENCES departments(department_uid),
    code                VARCHAR(64)  NOT NULL,
    name                VARCHAR(128) NOT NULL,
    description         TEXT,
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    is_deleted          BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX uq_projects_dept_code
    ON projects (department_uid, lower(code))
    WHERE is_deleted = FALSE;

CREATE TRIGGER trg_projects_updated_at
BEFORE UPDATE ON projects
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- users 擴充
ALTER TABLE users
    ADD COLUMN department_uid  UUID REFERENCES departments(department_uid),
    ADD COLUMN employee_id     VARCHAR(32),
    ADD COLUMN email           VARCHAR(255);

CREATE INDEX idx_users_department_uid
    ON users (department_uid)
    WHERE is_deleted = FALSE;
