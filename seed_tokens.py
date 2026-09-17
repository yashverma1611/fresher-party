from database import get_db_connection
conn = get_db_connection()
conn.execute("UPDATE admins SET session_token = 'TOKEN-SCANNER-DEMO-GATE1' WHERE email = 'rahul.gate1@college.edu'")
conn.execute("UPDATE admins SET session_token = 'TOKEN-CREATOR-DEMO' WHERE email = 'frsher.party.2k.26@gmail.com'")
conn.commit()
conn.close()
print("Seeded demo session tokens.")
