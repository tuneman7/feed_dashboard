DO $$
DECLARE
    rec RECORD;
BEGIN
    -- Drop all user-defined schemas except system/internal ones
    FOR rec IN
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT ILIKE ALL (ARRAY[
            'pg_%',                 -- system schemas like pg_catalog, pg_toast
            'information_schema',   -- SQL standard system schema
            'public'                -- optionally preserved
        ])
    LOOP
        RAISE NOTICE 'Dropping schema: %', rec.schema_name;
        EXECUTE format('DROP SCHEMA IF EXISTS %I CASCADE;', rec.schema_name);
    END LOOP;
END
$$;
