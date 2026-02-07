import os
import datetime


class AppConfig:
    # ==============================
    #  ส่วนข้อมูลส่วนตัว (แก้ไขตรงนี้)
    # ==============================
    USERNAME = "xxxxx"
    PASSWORD = "xxxxx"  # <--- ใส่รหัสผ่านจริงที่นี่

    # Discord Webhook (ถ้าไม่ใช้ให้ใส่เป็น None หรือ "")
    DISCORD_WEBHOOK = "https://discord.com/api/webhooks/xxx/xxxxxx"

    # ==============================
    #  การตั้งค่าระบบ
    # ==============================
    COURSE_URL = "https://lms.psu.ac.th/course/view.php?id=1513"

    # ชื่อไฟล์รูปภาพ (ต้องวางไฟล์ไว้ที่เดียวกับ Script)
    IMAGE_FILENAME = "greenlove.jpg"

    # วันที่เริ่ม Challenge (Year, Month, Day)
    START_DATE = datetime.date(2026, 2, 6)

    # Log File Name
    LOG_FILE = "app.log"

    @classmethod
    def validate(cls):
        """ตรวจสอบความถูกต้องของค่า Config ก่อนเริ่มทำงาน"""
        if not cls.USERNAME or not cls.PASSWORD:
            raise ValueError(
                " Config Error: กรุณาใส่ USERNAME และ PASSWORD ในไฟล์ config.py"
            )

        if not os.path.exists(cls.IMAGE_FILENAME):
            raise FileNotFoundError(
                f" Config Error: ไม่พบไฟล์รูปภาพ '{cls.IMAGE_FILENAME}'"
            )
