import os
from dotenv import load_dotenv
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv("db.env")

engine = create_engine("postgresql://postgres.czqtntezxorxjbfaiknl:Ny4TsZkHMW6TrvNy@aws-1-ap-southeast-1.pooler.supabase.com:6543/postgres")

