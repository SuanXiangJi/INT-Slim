from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database settings
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    mysql_charset: str
    
    # JWT settings
    secret_key: str = "your-secret-key-here-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_days: int = 1
    
    # CORS settings
    backend_cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5177",
        "http://localhost:5178",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:5177",
        "http://127.0.0.1:5178",
    ]
    
    # Email settings
    smtp_server: str = "smtp.qq.com"  # QQ閭SMTP鏈嶅姟鍣?    smtp_port: int = 465  # QQ閭SMTP绔彛
    smtp_username: str = ""  # 鍙戜欢浜洪偖绠?    smtp_password: str = ""  # 鍙戜欢浜哄瘑鐮侊紙QQ閭闇€浣跨敤鎺堟潈鐮侊級
    email_from: str = ""  # 鍙戜欢浜洪偖绠憋紝涓巗mtp_username淇濇寔涓€鑷?    email_subject_prefix: str = "[XBots Agent] "  # 閭欢涓婚鍓嶇紑
    
    # Verification code settings
    verification_code_length: int = 6  # 楠岃瘉鐮侀暱搴?    verification_code_expire_minutes: int = 5  # 楠岃瘉鐮佹湁鏁堟湡锛堝垎閽燂級
    
    # LLM settings
    deepseek_api_key: str = ""  # DeepSeek API瀵嗛挜
    minimax_api_key: str = ""  # MiniMax API瀵嗛挜
    
    # Web search
    tavily_api_key: str = ""  # Tavily web search API key

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()