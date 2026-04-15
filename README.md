Start the system
Make sure Docker Desktop is installed and running before starting the project.
```bash
docker compose up --build
```
Notes:
- The first startup may take a few minutes because Docker needs to build the Flask image and initialize the MySQL database.
- During the first creation of the MySQL container, init.sql is executed automatically to create the database schema and insert the initial sample data.
- The application uses port 3000 and the database uses port 3306, make sure these ports are available.

Open The Application
After the containers is started, open the application in a browser:
- http://localhost:3000
If localhost:3000 does not load, wait for MySQL initialization to finish

Default Database Configuration
The system uses the following default MySQL settings:
Database: comp7640
User: appuser
Password: apppassword

Reset the Database
To remove the existing database volume and recreate the database from init.sql:
First run docker compose down -v
Then run docker compose up --build