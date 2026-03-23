-- Standard access grants for new application services
CREATE ROLE new_app_service WITH LOGIN PASSWORD 'ChangeMe123!';
GRANT CONNECT ON DATABASE app_production TO new_app_service;
GRANT USAGE ON SCHEMA public TO new_app_service;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO new_app_service;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE ON TABLES TO new_app_service;