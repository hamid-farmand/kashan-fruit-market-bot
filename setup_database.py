from database import create_tables, seed_initial_data

if __name__ == "__main__":
    create_tables()
    seed_initial_data()
    print("دیتابیس آماده شد!")