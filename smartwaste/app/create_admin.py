from sqlalchemy import select

from .database import Base, engine, SessionLocal
from .models import User
from .security import hash_password


def create_admin():
    # Create database tables if they do not exist
    Base.metadata.create_all(bind=engine)

    username = input("Enter admin username: ").strip()

    if not username:
        print("Username cannot be empty.")
        return

    password = input("Enter admin password (minimum 12 characters): ")

    if len(password) < 12:
        print("Password must contain at least 12 characters.")
        return

    confirm_password = input("Confirm admin password: ")

    if password != confirm_password:
        print("Passwords do not match.")
        return

    with SessionLocal() as db:
        existing_user = db.scalar(
            select(User).where(User.username == username)
        )

        if existing_user:
            print("This username already exists.")
            return

        admin = User(
            username=username,
            password_hash=hash_password(password),
            role="admin"
        )

        db.add(admin)
        db.commit()

        print("\nAdmin account created successfully!")
        print("Username:", username)
        print("Role: admin")
        print("You can now log in using your chosen credentials.")


if __name__ == "__main__":
    create_admin()