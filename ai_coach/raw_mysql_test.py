"""Raw MySQL Query - direkter Zugriff ohne Django ORM"""
import pymysql
import sys

# Connection Details
config = {
    'host': 'localhost',
    'port': 3307,  # Unser SSH Tunnel
    'user': 'fit',
    'password': 'ykvpC7N9pK6d$$va',
    'database': 'gym_',
    'charset': 'utf8mb4'
}

print(f"\n{'='*60}")
print(f"🔍 RAW MYSQL QUERY")
print(f"{'='*60}")
print(f"Host: {config['host']}:{config['port']}")
print(f"Database: {config['database']}")
print(f"User: {config['user']}")
print(f"{'='*60}\n")

try:
    # Connect
    conn = pymysql.connect(**config)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    # Query: All users
    cursor.execute("SELECT id, username, email, is_active FROM auth_user ORDER BY id")
    users = cursor.fetchall()
    
    print(f"👥 USERS in auth_user table ({len(users)}):")
    print(f"{'='*60}")
    for user in users:
        print(f"  ID {user['id']}: {user['username']} ({user['email']})")
    print(f"{'='*60}\n")
    
    # Query: Sessions per user
    cursor.execute("""
        SELECT user_id, COUNT(*) as session_count, MAX(datum) as last_session
        FROM core_trainingseinheit
        GROUP BY user_id
        ORDER BY user_id
    """)
    sessions = cursor.fetchall()
    
    print(f"📊 SESSIONS per User:")
    print(f"{'='*60}")
    for row in sessions:
        print(f"  User ID {row['user_id']}: {row['session_count']} Sessions (letztes: {row['last_session']})")
    print(f"{'='*60}\n")
    
    # Query: Alle Sessions von User 2
    cursor.execute("""
        SELECT id, datum, user_id
        FROM core_trainingseinheit
        WHERE user_id IN (1, 2)
        ORDER BY user_id, datum DESC
    """)
    all_sessions = cursor.fetchall()
    
    if all_sessions:
        print(f"📋 ALLE SESSIONS (User 1 & 2):")
        print(f"{'='*60}")
        for s in all_sessions:
            print(f"  Session ID {s['id']}: User {s['user_id']} - {s['datum']}")
        print(f"{'='*60}\n")
    
    cursor.close()
    conn.close()
    
    print("✅ Query erfolgreich!\n")
    
except Exception as e:
    print(f"❌ MySQL Error: {e}\n")
    sys.exit(1)
