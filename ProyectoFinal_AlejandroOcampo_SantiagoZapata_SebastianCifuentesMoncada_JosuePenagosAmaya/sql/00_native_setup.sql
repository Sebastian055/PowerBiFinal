-- Creación de usuario y base de datos para ejecución nativa (fuera de Docker)
CREATE USER solar_user WITH PASSWORD 'solar_pass';
CREATE DATABASE solar_db OWNER solar_user;
GRANT ALL PRIVILEGES ON DATABASE solar_db TO solar_user;