-- 1. One row per group (static, written once)
-- (will need to be modified to allow adding sources)
CREATE TABLE groups (
    group_id    SERIAL PRIMARY KEY,
    user_id     INT NOT NULL,
    name_gr     TEXT,
    ra_gr       DOUBLE PRECISION,
    dec_gr      DOUBLE PRECISION,
    ra_grid     BYTEA,
    dec_grid    BYTEA
);

-- 2. One row per source (static, written once)
CREATE TABLE members (
    member_id   SERIAL PRIMARY KEY,
    group_id    INT REFERENCES groups(group_id),
    member_idx  INT NOT NULL,       -- position within group
    ra_mem      DOUBLE PRECISION,
    dec_mem     DOUBLE PRECISION
);

-- 3. Mask arrays: 2 rows per group ('latest' + 'total'), overwritten daily
CREATE TABLE group_masks (
    group_id    INT REFERENCES groups(group_id),
    mask_type   TEXT NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    umask       BYTEA,
    gmask       BYTEA,
    rmask       BYTEA,
    imask       BYTEA,
    zmask       BYTEA,
    ymask       BYTEA,
    PRIMARY KEY (group_id, mask_type)
);


-- 4. Cumulative visit count per source (overwritten daily)
CREATE TABLE member_totals (
    time        DATE NOT NULL,
    member_id   INT REFERENCES members(member_id),
    uvisits    DOUBLE PRECISION DEFAULT 0,
    gvisits    DOUBLE PRECISION DEFAULT 0,
    rvisits    DOUBLE PRECISION DEFAULT 0,
    ivisits    DOUBLE PRECISION DEFAULT 0,
    zvisits    DOUBLE PRECISION DEFAULT 0,
    yvisits    DOUBLE PRECISION DEFAULT 0,
    PRIMARY KEY (time, member_id)
);
-- SELECT create_hypertable('member_daily_visits', 'time');

-- 5. One row per source per day (append-only time series)
CREATE TABLE member_daily_visits (
    time        DATE NOT NULL,
    member_id   INT REFERENCES members(member_id),
    uvisits    DOUBLE PRECISION DEFAULT 0,
    gvisits    DOUBLE PRECISION DEFAULT 0,
    rvisits    DOUBLE PRECISION DEFAULT 0,
    ivisits    DOUBLE PRECISION DEFAULT 0,
    zvisits    DOUBLE PRECISION DEFAULT 0,
    yvisits    DOUBLE PRECISION DEFAULT 0,
    PRIMARY KEY (time, member_id)
);

-- 6. One row per source per day (append-only time series)
CREATE TABLE member_observability (
    time        DATE NOT NULL,
    member_id   INT REFERENCES members(member_id),
    hrs_obs    DOUBLE PRECISION DEFAULT 0,
    PRIMARY KEY (time, member_id)
);

-- 7. One row per source per day (static, written once)
CREATE TABLE member_obs_flags (
    time        DATE NOT NULL,
    member_id   INT REFERENCES members(member_id),
    obs_flag    INT NOT NULL,
    PRIMARY KEY (time, member_id)
);