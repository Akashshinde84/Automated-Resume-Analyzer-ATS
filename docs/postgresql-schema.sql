BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_private_history

CREATE TABLE analyses (
    id UUID NOT NULL,
    owner_id VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    file_type VARCHAR(8) NOT NULL,
    PRIMARY KEY (id)
);

CREATE INDEX ix_analyses_owner_created ON analyses (owner_id, created_at);

CREATE INDEX ix_analyses_expires_at ON analyses (expires_at);

CREATE TABLE structured_resumes (
    analysis_id UUID NOT NULL,
    parsed JSONB NOT NULL,
    extraction JSONB NOT NULL,
    PRIMARY KEY (analysis_id),
    FOREIGN KEY(analysis_id) REFERENCES analyses (id) ON DELETE CASCADE
);

CREATE TABLE job_descriptions (
    id UUID NOT NULL,
    analysis_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    text TEXT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(analysis_id) REFERENCES analyses (id) ON DELETE CASCADE
);

CREATE INDEX ix_job_descriptions_analysis_id ON job_descriptions (analysis_id);

CREATE TABLE match_results (
    id UUID NOT NULL,
    analysis_id UUID NOT NULL,
    job_description_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    result JSONB NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(analysis_id) REFERENCES analyses (id) ON DELETE CASCADE,
    UNIQUE (job_description_id),
    FOREIGN KEY(job_description_id) REFERENCES job_descriptions (id) ON DELETE CASCADE
);

CREATE INDEX ix_match_results_analysis_id ON match_results (analysis_id);

INSERT INTO alembic_version (version_num) VALUES ('0001_private_history') RETURNING alembic_version.version_num;

COMMIT;
